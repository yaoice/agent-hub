# -*- coding: utf-8 -*-
"""内置 Mock 演示数据：当未配置有效密钥或真实调用失败时回退，保证看板开箱即用。"""
from __future__ import annotations

import hashlib

from .base import AppItem, ConversationItem, SpaceItem, TokenItem

_SPACE_DEFS = [
    ("space-cs", "客服智能体空间", [("智能客服助手", 2), ("工单自动分类", 2), ("售后知识问答", 2), ("投诉情绪识别", 1)]),
    ("space-mkt", "营销增长空间", [("活动文案生成", 2), ("私域运营助手", 2), ("商品推荐官", 1)]),
    ("space-hr", "人力资源空间", [("简历筛选助手", 2), ("入职答疑机器人", 2)]),
    ("space-fin", "财务风控空间", [("发票核验助手", 2), ("费用合规审查", 1), ("风险预警分析", 2)]),
    ("space-dev", "研发效能空间", [("代码评审助手", 2), ("接口文档生成", 2), ("故障根因分析", 2), ("测试用例生成", 1)]),
    ("space-ops", "运营数据空间", [("经营日报助手", 2), ("数据查询机器人", 2)]),
    ("space-legal", "法务合规空间", []),
    ("space-edu", "培训学习空间", [("课程问答助手", 2)]),
]

_TOKEN_APP = [
    ("智能客服助手", 8_420_000), ("代码评审助手", 6_310_000), ("活动文案生成", 5_180_000),
    ("数据查询机器人", 3_960_000), ("故障根因分析", 3_220_000), ("简历筛选助手", 2_540_000),
    ("接口文档生成", 1_870_000), ("风险预警分析", 1_330_000), ("课程问答助手", 920_000),
    ("入职答疑机器人", 610_000),
]
_TOKEN_MODEL = [
    ("hunyuan-turbo", 18_600_000), ("hunyuan-pro", 9_200_000), ("hunyuan-standard", 5_400_000),
    ("deepseek-v3", 3_100_000), ("hunyuan-lite", 1_400_000),
]
_TOKEN_SPACE = [
    ("研发效能空间", 11_200_000), ("客服智能体空间", 9_800_000), ("营销增长空间", 6_900_000),
    ("财务风控空间", 4_600_000), ("运营数据空间", 3_100_000), ("人力资源空间", 1_900_000),
]


def _with_pct(rows: list[tuple[str, int]]) -> list[TokenItem]:
    total = sum(v for _, v in rows) or 1
    return [TokenItem(name=n, value=v, percentage=round(v / total * 100, 1)) for n, v in rows]


def mock_spaces() -> list[SpaceItem]:
    spaces: list[SpaceItem] = []
    for sid, name, apps in _SPACE_DEFS:
        spaces.append(
            SpaceItem(
                space_id=sid,
                space_name=name,
                apps=[
                    AppItem(name=an, status_code=st, app_biz_id=hashlib.md5(an.encode()).hexdigest()[:12])
                    for an, st in apps
                ],
            )
        )
    return spaces


def mock_token_top(dimension: int) -> list[TokenItem]:
    if dimension == 1:
        return _with_pct(_TOKEN_SPACE)
    if dimension == 3:
        return _with_pct(_TOKEN_MODEL)
    return _with_pct(_TOKEN_APP)


_MOCK_QA = [
    ("怎么修改我的预订信息？", "您可在「我的订单」中选择对应订单点击修改，或联系在线客服协助处理。"),
    ("航班延误了能退票吗？", "因航班延误产生的退票通常可免费办理，具体以航司政策为准，我已为您发起核实。"),
    ("如何开具发票？", "登录后进入「订单详情-开具发票」，填写抬头信息即可在线开具电子发票。"),
    ("行李额度是多少？", "经济舱通常为 20kg，具体以您所购客票舱位与航线规则为准。"),
    ("可以预选座位吗？", "支持，值机开放后可在「在线值机」中预选座位，部分座位可能需额外付费。"),
]


def mock_conversations(app_biz_id: str, app_name: str = "", count: int = 5) -> list[ConversationItem]:
    """生成确定性的 Mock 对话记录（同一应用多次调用结果稳定，便于去重测试）。"""
    items: list[ConversationItem] = []
    base = int(hashlib.md5(app_biz_id.encode()).hexdigest()[:6], 16)
    n = min(count, len(_MOCK_QA))
    for i in range(n):
        q, a = _MOCK_QA[i]
        seed = f"{app_biz_id}|{i}"
        record_id = hashlib.md5(seed.encode()).hexdigest()
        minute = (base + i) % 60
        items.append(
            ConversationItem(
                record_id=record_id,
                session_id=f"sess-{record_id[:8]}",
                user_biz_id=f"user-{(base + i) % 1000:03d}",
                user_nickname=f"访客{(base + i) % 100:02d}",
                question=q,
                answer=a,
                intent_category=app_name or "通用咨询",
                create_time=f"2026-06-21 10:{minute:02d}:00",
                raw={"mock": True},
            )
        )
    return items
