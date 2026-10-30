"""可信认证页面的明确整页错误，不根据路由或超时猜测远端结果。"""
from __future__ import annotations

from collections.abc import Mapping
import re
import unicodedata
from urllib.parse import urlsplit


AUTH_PAGE_ERROR_MARKERS = {
    "auth_operation_timeout": (
        "operation timed out",
        "操作超时",
        "操作逾時",
    ),
    "auth_context_missing": (
        "इस पेज पर आगे बढ़ने के लिए ज़रूरी जानकारी नहीं है",
        "इस पेज पर आगे बढ़ने के लिए जरूरी जानकारी नहीं है",
        "this page is missing information needed to continue",
        "this page is missing the information needed to continue",
        "this page is missing information required to continue",
        "this page is missing required information",
        "此页面缺少继续操作所需的信息",
        "此页面缺少继续所需的信息",
        "这个页面缺少继续操作所需的信息",
        "此頁面缺少繼續操作所需的資訊",
    ),
}
_ERROR_DETAILS = {
    "auth_operation_timeout": ("AUTH_ERROR", "认证页面操作超时"),
    "auth_context_missing": ("LOGGED_OUT", "登录上下文缺失，需要重新发起登录"),
}
_AUTH_HOSTS = frozenset({"auth.openai.com", "chatgpt.com", "chat.openai.com"})


class AuthPageError(RuntimeError):
    """只携带固定页面原因；提交是否派发由原回执单独记录。"""

    def __init__(self, code: str):
        self.code = code
        self.page_state, message = _ERROR_DETAILS[code]
        super().__init__(message)


def _normalized_text(value: object) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(value or "")).casefold()).strip()


def auth_page_error(snapshot: object) -> AuthPageError | None:
    """只解释可信页面的明确正文或固定错误码，不发请求、不决定恢复。"""
    if not isinstance(snapshot, Mapping):
        return None
    try:
        location = urlsplit(str(snapshot.get("url") or ""))
        if (location.scheme != "https" or location.hostname not in _AUTH_HOSTS
                or location.port not in (None, 443) or location.username or location.password):
            return None
    except ValueError:
        return None
    errors = snapshot.get("errors")
    errors = errors if isinstance(errors, (list, tuple)) else []
    text_parts = [snapshot.get("title"), snapshot.get("text")]
    codes = set()
    for error in errors:
        if isinstance(error, Mapping):
            codes.add(str(error.get("code") or error.get("error_code") or ""))
            text_parts.extend((error.get("message"), error.get("description")))
        else:
            text_parts.append(error)
    markers = snapshot.get("error_markers")
    if isinstance(markers, (list, tuple)):
        codes.update(item for item in markers if isinstance(item, str) and item in _ERROR_DETAILS)
    text = _normalized_text(" ".join(str(part or "") for part in text_parts))
    for code, variants in AUTH_PAGE_ERROR_MARKERS.items():
        if code in codes or any(_normalized_text(marker) in text for marker in variants):
            return AuthPageError(code)
    return None
