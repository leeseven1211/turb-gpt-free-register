"""CPA 网页下载的脱敏网络计时与错误分类。"""

import logging
import time

from curl_cffi import CurlECode, CurlError, CurlInfo
from curl_cffi.requests.exceptions import CertificateVerifyError, SSLError

logger = logging.getLogger(__name__)

CURL_INFOS = [
    CurlInfo.NAMELOOKUP_TIME,
    CurlInfo.CONNECT_TIME,
    CurlInfo.APPCONNECT_TIME,
    CurlInfo.PRETRANSFER_TIME,
    CurlInfo.STARTTRANSFER_TIME,
    CurlInfo.TOTAL_TIME,
]

PHASE_LABELS = {
    "auth_files": "读取文件列表",
    "auth_file_download": "下载凭证文件",
}

NETWORK_ERRORS = {
    CurlECode.OPERATION_TIMEDOUT: ("cpa_timeout", "CPA 请求超时"),
    CurlECode.COULDNT_RESOLVE_HOST: ("cpa_dns_error", "CPA 地址解析失败"),
    CurlECode.COULDNT_RESOLVE_PROXY: ("cpa_proxy_error", "CPA 代理地址解析失败"),
    CurlECode.COULDNT_CONNECT: ("cpa_connect_error", "CPA 网络连接失败"),
    CurlECode.PROXY: ("cpa_proxy_error", "CPA 代理连接失败"),
    CurlECode.SEND_ERROR: ("cpa_send_error", "CPA 请求发送失败"),
    CurlECode.RECV_ERROR: ("cpa_receive_error", "CPA 响应接收失败"),
    CurlECode.GOT_NOTHING: ("cpa_empty_response", "CPA 未返回响应"),
}


class CpaDownloadError(RuntimeError):
    def __init__(self, code: str, message: str, phase: str):
        super().__init__(f"{message}（{PHASE_LABELS[phase]}）")
        self.code = code


def _network_error(exc: CurlError, phase: str) -> CpaDownloadError:
    if isinstance(exc, CertificateVerifyError) or exc.code == CurlECode.PEER_FAILED_VERIFICATION:
        return CpaDownloadError("cpa_tls_certificate_error", "CPA TLS 证书校验失败", phase)
    if isinstance(exc, SSLError) or exc.code == CurlECode.SSL_CONNECT_ERROR:
        return CpaDownloadError("cpa_tls_error", "CPA TLS 连接失败", phase)
    code, message = NETWORK_ERRORS.get(exc.code, ("cpa_transport_error", f"CPA 网络请求失败，curl 错误码 {exc.code}"))
    return CpaDownloadError(code, message, phase)


def error_payload(exc: CpaDownloadError) -> dict:
    return {"error": str(exc), "error_code": exc.code}


def _log_timing(start: float, phase: str, response, error: CpaDownloadError | None, curl_code: int):
    status = getattr(response, "status_code", 0)
    elapsed_ms = (time.perf_counter() - start) * 1000
    if error:
        log_level = logging.WARNING
    elif phase == "auth_files" or elapsed_ms >= 1000:
        log_level = logging.INFO
    else:
        log_level = logging.DEBUG
    if not logger.isEnabledFor(log_level):
        return

    infos = getattr(response, "infos", None) or {}
    dns, connect, tls, pretransfer, first_byte, total = [infos.get(field, 0.0) for field in CURL_INFOS]

    def ms(endpoint: float, predecessor: float = 0.0):
        return round(1000 * (endpoint - predecessor), 1) if endpoint > 0 and endpoint >= predecessor else "-"

    # 未收到 HTTP 回执时，代理或 TLS 数据也可能在 libcurl 内出现首字节时间。
    response_started = status > 0 and first_byte > 0
    logger.log(
        log_level,
        "CPA 下载网络阶段 phase=%s outcome=%s http_status=%s curl_code=%s "
        "dns_ms=%s connect_ms=%s tls_ms=%s response_wait_ms=%s body_ms=%s total_ms=%.1f",
        phase, error.code if error else "ok", status, curl_code, ms(dns), ms(connect, dns), ms(tls, connect),
        ms(first_byte, pretransfer) if response_started else "-", ms(total, first_byte) if response_started else "-",
        elapsed_ms,
    )


def send(session, method: str, url: str, *, phase: str, **kwargs):
    """只为 Web 下载入口记录传输阶段。"""
    if not phase:
        return session.request(method, url, **kwargs)
    started_at = time.perf_counter()
    try:
        response = session.request(method, url, **kwargs)
    except CurlError as exc:
        error = _network_error(exc, phase)
        _log_timing(started_at, phase, getattr(exc, "response", None), error, int(exc.code))
        raise error from exc
    if not 200 <= response.status_code < 300:
        error = CpaDownloadError("cpa_http_error", f"CPA 管理接口返回 HTTP {response.status_code}", phase)
        _log_timing(started_at, phase, response, error, 0)
        raise error
    _log_timing(started_at, phase, response, None, 0)
    return response
