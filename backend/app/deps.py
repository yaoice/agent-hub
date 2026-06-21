# -*- coding: utf-8 -*-
"""FastAPI 鉴权依赖。"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import get_db
from .models import Project, User
from .repositories import get_project_member_repository, get_project_repository
from .security import decode_access_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/auth/login")


def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    cred_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="登录态无效或已过期",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if not payload:
        raise cred_exc
    username = payload.get("sub")
    if not username:
        raise cred_exc
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise cred_exc
    # 禁用用户即时失效：已签发的 token 也无法继续使用
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员"
        )
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user


def list_visible_projects(db: Session, user: User) -> list[Project]:
    """返回用户可见的项目：admin 可见全部，普通用户仅可见其所属项目。"""
    repo = get_project_repository(db)
    if user.role == "admin":
        return repo.list_all()
    return repo.list_for_user(user.id)


def _get_project_or_404(db: Session, project_id: int) -> Project:
    project = get_project_repository(db).get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


def require_project_access(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    """可见性：admin 全可见；普通用户须为该项目成员。"""
    project = _get_project_or_404(db, project_id)
    if user.role == "admin":
        return project
    member = get_project_member_repository(db).get(project_id, user.id)
    if not member:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权访问该项目")
    return project


def require_project_admin(
    project_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Project:
    """写权限：全局 admin，或该项目的 project_admin。"""
    project = _get_project_or_404(db, project_id)
    if user.role == "admin":
        return project
    member = get_project_member_repository(db).get(project_id, user.id)
    if not member or member.project_role != "project_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="需要项目管理员权限"
        )
    return project
