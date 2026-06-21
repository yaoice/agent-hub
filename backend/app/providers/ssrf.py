# -*- coding: utf-8 -*-
"""SSRF 防护：禁止解析到内网/私有地址的 Host。

安全规则：默认拒绝访问私有/保留网段（含 9./10./11./21./30. 等）。
如确需访问内网网关，可通过 ALLOW_INTERNAL_HOSTS=true 显式放开。
"""
import ipaddress
import socket
from urllib.parse import urlparse

from ..config import settings

# 额外按规则要求拦截的网段前缀（即便不属于标准私有网段也拒绝）
_EXTRA_BLOCKED_PREFIXES = ("9.", "10.", "11.", "21.", "30.")


def _is_blocked_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True  # 无法解析视为不安全
    if (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
    ):
        return True
    return any(ip.startswith(p) for p in _EXTRA_BLOCKED_PREFIXES)


def assert_safe_host(host: str) -> None:
    """校验目标 Host 是否安全；不安全则抛出 ValueError。"""
    if settings.allow_internal_hosts:
        return

    # 兼容传入带协议的 URL
    hostname = host
    if "://" in host:
        hostname = urlparse(host).hostname or host
    hostname = hostname.split(":")[0].strip()

    if not hostname:
        raise ValueError("Host 不能为空")
    if hostname.lower() in ("localhost", "localhost.localdomain"):
        raise ValueError("出于安全考虑，禁止访问本机/内网地址")

    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise ValueError(f"无法解析 Host: {hostname} ({exc})") from exc

    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            raise ValueError(
                f"出于安全考虑（SSRF 防护），禁止访问内网/私有地址：{hostname} -> {ip}"
            )
