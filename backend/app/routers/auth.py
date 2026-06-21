# -*- coding: utf-8 -*-
"""认证路由：登录、获取当前用户（含可见项目）。"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, list_visible_projects
from ..models import User
from ..repositories import get_project_member_repository
from ..schemas import ProjectBrief, TokenResponse, UserInfo
from ..security import create_access_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


def build_user_info(db: Session, user: User) -> UserInfo:
    """组装当前用户信息，附带可见项目列表（含项目角色）。"""
    member_repo = get_project_member_repository(db)
    role_map = {m.project_id: m.project_role for m in member_repo.list_by_user(user.id)}
    projects = [
        ProjectBrief(
            id=p.id,
            name=p.name,
            provider_type_key=p.provider_type_key,
            project_role=role_map.get(p.id, "admin" if user.role == "admin" else None),
        )
        for p in list_visible_projects(db, user)
    ]
    return UserInfo(
        id=user.id,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        projects=projects,
    )


@router.post("/login", response_model=TokenResponse)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form.username).first()
    if not user or not verify_password(form.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误"
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用，请联系管理员"
        )
    token = create_access_token(subject=user.username, role=user.role)
    return TokenResponse(access_token=token, username=user.username, role=user.role)


@router.get("/me", response_model=UserInfo)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return build_user_info(db, user)
