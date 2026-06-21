# -*- coding: utf-8 -*-
"""Provider 类型目录路由：只读列表 + 启用/禁用。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import User
from ..repositories import get_provider_repository
from ..schemas import ProviderOut, ProviderUpdate

router = APIRouter(prefix="/api/providers", tags=["providers"])


@router.get("", response_model=list[ProviderOut])
def list_providers(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """所有登录用户可读类型目录（供项目表单展示）。"""
    return get_provider_repository(db).list_all()


@router.patch("/{type_key}", response_model=ProviderOut)
def update_provider(
    type_key: str,
    body: ProviderUpdate,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    repo = get_provider_repository(db)
    provider = repo.get_by_key(type_key)
    if not provider:
        raise HTTPException(status_code=404, detail="Provider 类型不存在")
    if body.enabled and not provider.implemented:
        raise HTTPException(status_code=400, detail="该 Provider 尚未实现，无法启用")
    provider.enabled = body.enabled
    repo.save(provider)
    return provider
