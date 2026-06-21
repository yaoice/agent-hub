# -*- coding: utf-8 -*-
"""Provider 注册表与内置类型目录。

- _REGISTRY：type_key -> 已实现的 Provider 实现类。
- BUILTIN_PROVIDERS：内置类型目录元数据（用于 seed 与前端展示）。

说明：
- 私有化 ADP 即 tencent_lke（基于腾讯云 LKE，TC3-HMAC-SHA256），前端展示「私有化 ADP」。
- 公有云 ADP（adp_public）尚未实现，前端置灰、不可启用。
"""
from __future__ import annotations

from .base import BaseProvider
from .tencent_lke import TencentLKEProvider

# 已实现的 Provider 实现类
_REGISTRY: dict[str, type[BaseProvider]] = {
    TencentLKEProvider.type_name: TencentLKEProvider,  # tencent_lke = 私有化 ADP
}

# 内置类型目录（type_key / 展示名 / 是否已实现 / 描述）
BUILTIN_PROVIDERS = [
    {
        "type_key": "tencent_lke",
        "display_name": "私有化 ADP",
        "implemented": True,
        "description": "私有化 ADP（基于腾讯云 LKE，TC3-HMAC-SHA256 鉴权）",
    },
    {
        "type_key": "adp_public",
        "display_name": "公有云 ADP",
        "implemented": False,
        "description": "公有云 ADP（尚未实现，敬请期待）",
    },
]


def is_implemented(type_key: str) -> bool:
    return type_key in _REGISTRY


def build_provider(
    provider_type: str, secret_id: str, secret_key: str, host: str, region: str = "1"
) -> BaseProvider:
    cls = _REGISTRY.get(provider_type)
    if cls is None:
        raise ValueError(f"Provider 类型未实现：{provider_type}")
    return cls(secret_id=secret_id, secret_key=secret_key, host=host, region=region)
