# -*- coding: utf-8 -*-
"""Pydantic 请求/响应模型。"""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, model_validator


# ---------- Auth ----------
class ProjectBrief(BaseModel):
    """登录用户可见项目的精简信息（用于看板切换）。"""

    id: int
    name: str
    provider_type_key: str
    project_role: Optional[str] = None  # 当前用户在该项目中的角色


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class UserInfo(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool = True
    projects: list[ProjectBrief] = Field(default_factory=list)

    class Config:
        from_attributes = True


# ---------- User 管理 ----------
class UserCreate(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=4, max_length=128)
    role: str = Field(default="user")


class UserUpdate(BaseModel):
    role: Optional[str] = None
    # 留空表示不重置密码；一旦设置新密码，必须提供原密码与确认密码
    password: Optional[str] = Field(default=None, min_length=4, max_length=128)
    # 原密码（用于二次鉴权：编辑自己=本人旧密码，编辑他人=管理员本人密码）
    current_password: Optional[str] = None
    # 新密码二次确认
    confirm_password: Optional[str] = None

    @model_validator(mode="after")
    def _check_password_change(self) -> "UserUpdate":
        if self.password is not None:
            if not self.current_password:
                raise ValueError("修改密码需输入原密码")
            if self.confirm_password is None:
                raise ValueError("请再次输入新密码进行确认")
            if self.password != self.confirm_password:
                raise ValueError("两次输入的新密码不一致")
        return self


class UserStatusUpdate(BaseModel):
    is_active: bool


class UserMembership(BaseModel):
    project_id: int
    project_name: str
    project_role: str


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool
    created_at: datetime
    project_count: int = 0

    class Config:
        from_attributes = True


class UserDetailOut(UserOut):
    memberships: list[UserMembership] = Field(default_factory=list)


# ---------- Provider 类型目录 ----------
class ProviderOut(BaseModel):
    id: int
    type_key: str
    display_name: str
    enabled: bool
    implemented: bool
    description: str

    class Config:
        from_attributes = True


class ProviderUpdate(BaseModel):
    enabled: bool


# ---------- Project ----------
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    provider_type_key: str = Field(..., min_length=1, max_length=32)
    host: str = Field(..., min_length=1, max_length=255)
    region: str = Field(default="1")
    is_active: bool = True


class ProjectCreate(ProjectBase):
    secret_id: str = Field(..., min_length=1)
    secret_key: str = Field(..., min_length=1)


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    provider_type_key: Optional[str] = None
    host: Optional[str] = None
    region: Optional[str] = None
    is_active: Optional[bool] = None
    secret_id: Optional[str] = None
    # 留空表示不修改密钥
    secret_key: Optional[str] = None


class ProjectOut(ProjectBase):
    id: int
    provider_display_name: str = ""
    secret_id_masked: str
    secret_key_masked: str
    member_count: int = 0
    last_sync_at: Optional[datetime] = None
    last_sync_source: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ---------- Project Member ----------
class ProjectMemberCreate(BaseModel):
    user_id: int
    project_role: str = Field(default="member")


class ProjectMemberOut(BaseModel):
    id: int
    user_id: int
    username: str
    project_role: str
    created_at: datetime


class SyncRequest(BaseModel):
    # 同步范围子集：app_count / token / conversations；留空默认 [app_count, token]
    scopes: Optional[list[str]] = None
    # 对话同步可选时间范围与上限
    conv_begin: Optional[str] = None
    conv_end: Optional[str] = None
    max_records_per_app: int = Field(default=500, ge=1, le=5000)


class SyncResult(BaseModel):
    ok: bool
    source: str  # live / mock
    message: str
    synced_at: datetime
    scopes: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


# ---------- 对话记录 ----------
class ConversationSyncRequest(BaseModel):
    # 时间范围（"YYYY-MM-DD HH:MM:SS"）；留空默认最近 7 天
    begin: Optional[str] = None
    end: Optional[str] = None
    max_records_per_app: int = Field(default=500, ge=1, le=5000)


class ConversationSyncResult(BaseModel):
    source: str  # live / mock
    app_count: int
    fetched: int
    inserted: int
    message: str
    synced_at: datetime


class ConversationOut(BaseModel):
    id: int
    app_biz_id: str
    session_id: str
    user_biz_id: str
    user_nickname: str
    question: str
    answer: str
    intent_category: str
    create_time: str = Field(alias="msg_create_time")
    synced_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class ConversationPage(BaseModel):
    total: int
    items: list[ConversationOut]


class TrendPoint(BaseModel):
    date: str
    count: int


class IntentSlice(BaseModel):
    name: str
    count: int


class ConversationStats(BaseModel):
    trend: list[TrendPoint]
    intents: list[IntentSlice]
    total: int


# ---------- Dashboard ----------
class DashboardResponse(BaseModel):
    project_id: int
    project_name: str
    source: str  # live / mock
    updated_at: Optional[datetime] = None
    data: dict[str, Any]
