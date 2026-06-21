# -*- coding: utf-8 -*-
"""ADP（Agent Development Platform）Provider。

ADP 与腾讯云 LKE 同样采用 TC3-HMAC-SHA256 鉴权，此处通过继承复用签名/调用逻辑，
仅以独立类型标识接入，体现「灵活接入不同 Provider」的可扩展设计。
如未来 ADP 接口字段出现差异，只需在此覆写对应方法即可，不影响其它 Provider。
"""
from __future__ import annotations

from .tencent_lke import TencentLKEProvider


class ADPProvider(TencentLKEProvider):
    type_name = "adp"
