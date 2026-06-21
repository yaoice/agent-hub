# -*- coding: utf-8 -*-
"""用户管理路由（仅管理员）。"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import require_admin
from ..models import User
from ..repositories import (
    get_project_member_repository,
    get_project_repository,
    get_user_repository,
)
from ..schemas import (
    UserCreate,
    UserDetailOut,
    UserMembership,
    UserOut,
    UserStatusUpdate,
    UserUpdate,
)
from ..security import hash_password, verify_password

router = APIRouter(prefix="/api/users", tags=["users"])

VALID_ROLES = {"admin", "user"}


def _project_count(db: Session, user_id: int) -> int:
    return len(get_project_member_repository(db).list_by_user(user_id))


def _to_out(db: Session, u: User) -> UserOut:
    return UserOut(
        id=u.id,
        username=u.username,
        role=u.role,
        is_active=u.is_active,
        created_at=u.created_at,
        project_count=_project_count(db, u.id),
    )


@router.get("", response_model=list[UserOut])
def list_users(
    search: Optional[str] = Query(default=None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    users = get_user_repository(db).list(search=search)
    return [_to_out(db, u) for u in users]


@router.get("/{user_id}", response_model=UserDetailOut)
def get_user(
    user_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    repo = get_user_repository(db)
    user = repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    member_repo = get_project_member_repository(db)
    project_repo = get_project_repository(db)
    memberships = []
    for m in member_repo.list_by_user(user_id):
        project = project_repo.get(m.project_id)
        if project:
            memberships.append(
                UserMembership(
                    project_id=project.id,
                    project_name=project.name,
                    project_role=m.project_role,
                )
            )
    base = _to_out(db, user)
    return UserDetailOut(**base.model_dump(), memberships=memberships)


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate, _: User = Depends(require_admin), db: Session = Depends(get_db)
):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="非法角色")
    repo = get_user_repository(db)
    if repo.get_by_username(body.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    user = repo.add(
        username=body.username.strip(),
        password_hash=hash_password(body.password),
        role=body.role,
    )
    return _to_out(db, user)


@router.put("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = get_user_repository(db)
    user = repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    if body.role is not None and body.role != user.role:
        if body.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="非法角色")
        # 保护：不可降级最后一个在用管理员
        if user.role == "admin" and body.role != "admin":
            if repo.count_admins(active_only=True) <= 1:
                raise HTTPException(status_code=400, detail="系统需保留至少一名管理员")
        user.role = body.role

    if body.password:
        # 二次鉴权：校验操作者（当前登录管理员）的原密码
        if not verify_password(body.current_password or "", current.password_hash):
            raise HTTPException(status_code=400, detail="原密码不正确")
        user.password_hash = hash_password(body.password)

    repo.save(user)
    return _to_out(db, user)


@router.patch("/{user_id}/status", response_model=UserOut)
def set_user_status(
    user_id: int,
    body: UserStatusUpdate,
    current: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = get_user_repository(db)
    user = repo.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current.id and not body.is_active:
        raise HTTPException(status_code=400, detail="不能禁用自己")
    # 保护：不可禁用最后一个在用管理员
    if user.role == "admin" and not body.is_active and repo.count_admins(active_only=True) <= 1:
        raise HTTPException(status_code=400, detail="系统需保留至少一名启用的管理员")
    user.is_active = body.is_active
    repo.save(user)
    return _to_out(db, user)
