# -*- coding: utf-8 -*-
"""应用配置：所有敏感项均通过环境变量注入（env-only）。"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # 应用密钥（JWT 签名 + Provider 密钥加密派生）
    app_secret: str = "please-change-me-to-a-long-random-secret-string"
    access_token_expire_minutes: int = 720
    jwt_algorithm: str = "HS256"

    # 默认管理员（仅首次初始化建库时写入）
    default_admin_username: str = "admin"
    default_admin_password: str = "admin"

    # 数据库（切换 MySQL：mysql+pymysql://user:pwd@host:3306/agent_hub?charset=utf8mb4）
    database_url: str = "sqlite:///./agent_hub.db"

    # 仓储后端实现（当前内置 sqlalchemy；新增实现后可在此切换）
    repository_backend: str = "sqlalchemy"

    # SSRF 防护开关
    allow_internal_hosts: bool = False

    # 对话同步最小间隔（秒）：手动同步限频，两次之间至少间隔该时长；0 表示不限制
    conv_sync_min_interval_seconds: int = 300

    # 对话同步：相邻应用拉取之间的限速间隔（毫秒），仅对实时拉取生效，避免触发云端 QPS 限制
    conv_sync_app_delay_ms: int = 100

    # 是否存储对话原始报文（raw 字段）：默认关闭以节省存储空间，排障时可临时开启
    conv_store_raw: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
