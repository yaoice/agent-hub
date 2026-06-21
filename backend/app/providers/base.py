# -*- coding: utf-8 -*-
"""Provider 抽象基类：定义统一的运营指标拉取接口。

不同来源（腾讯云 LKE、ADP 等）实现该接口后即可被看板统一聚合。
"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field


@dataclass
class AppItem:
    name: str
    status_code: int  # 1=未上线 2=运行中
    app_biz_id: str = ""


@dataclass
class SpaceItem:
    space_id: str
    space_name: str
    apps: list[AppItem] = field(default_factory=list)


@dataclass
class TokenItem:
    name: str
    value: int
    percentage: float = 0.0


@dataclass
class ConversationItem:
    """一条对话/消息记录（来自 DescribeMsgLogList 等接口）。"""

    record_id: str
    session_id: str = ""
    user_biz_id: str = ""
    user_nickname: str = ""
    question: str = ""
    answer: str = ""
    intent_category: str = ""
    create_time: str = ""
    raw: dict = field(default_factory=dict)


class ProviderError(Exception):
    """Provider 调用异常（触发 Mock 回退）。"""


class BaseProvider(abc.ABC):
    """统一 Provider 接口。"""

    #: Provider 类型标识
    type_name: str = "base"

    def __init__(self, secret_id: str, secret_key: str, host: str, region: str = "1"):
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.host = host
        self.region = region

    @abc.abstractmethod
    def fetch_spaces(self) -> list[SpaceItem]:
        """拉取空间及其挂载的应用。"""

    @abc.abstractmethod
    def fetch_token_top(self, dimension: int) -> list[TokenItem]:
        """按维度拉取 Token 消耗排行（1=空间 2=应用 3=模型）。"""

    def fetch_conversations(
        self, app_biz_id: str, begin: str, end: str, max_records: int = 500
    ) -> list["ConversationItem"]:
        """拉取指定应用在时间范围内的对话记录（含分页）。

        默认未实现，需要支持的 Provider 覆写此方法。
        """
        raise ProviderError("该 Provider 不支持对话记录拉取")

    def has_credentials(self) -> bool:
        bad_markers = ("请在此处替换", "<SECRET", "")
        if not self.secret_id or not self.secret_key:
            return False
        return not any(m and m in self.secret_id for m in bad_markers if m)
