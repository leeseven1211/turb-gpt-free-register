"""Recognize the existing trusted registration profile form."""
import re
from urllib.parse import urlsplit


def registration_profile_form_ready(driver, *, snapshot) -> bool:
    """注册恢复已到可信资料表单时，交给资料阶段，不借 URL 空壳跳过认证。"""
    snapshot = snapshot(driver)
    if not isinstance(snapshot, dict) or snapshot.get("error"):
        return False
    try:
        current = urlsplit(str(snapshot.get("url") or ""))
        if (current.scheme != "https" or current.hostname != "auth.openai.com"
                or current.port not in (None, 443) or current.username or current.password
                or current.path not in {"/about-you", "/profile", "/signup/profile", "/create-account/profile"}):
            return False
    except ValueError:
        return False

    inputs = snapshot.get("inputs")
    widgets = snapshot.get("widgets")
    if not isinstance(inputs, list):
        return False
    fields = [item for item in inputs if isinstance(item, dict)
              and item.get("visible") is True
              and str(item.get("type") or "").lower() in {"", "text", "number", "date", "tel"}]

    def attributes(item):
        return " ".join(str(item.get(key) or "") for key in (
            "name", "id", "autocomplete", "aria", "placeholder",
        )).casefold()

    has_name = any(
        str(item.get("type") or "").lower() in {"", "text"}
        and re.search(r"(?:^|[^a-z])(?:name|full[_ -]?name|first[_ -]?name|last[_ -]?name)(?:[^a-z]|$)", attributes(item))
        for item in fields
    )
    has_age_or_birth = any(
        str(item.get("type") or "").lower() == "date"
        or re.search(r"(?:^|[^a-z])(?:age|birth(?:day|date)?|bday)(?:[^a-z]|$)", attributes(item))
        for item in fields
    ) or any(
        isinstance(item, dict) and item.get("visible") is True
        and item.get("role") == "spinbutton" and item.get("dataType") in {"month", "day", "year"}
        for item in (widgets if isinstance(widgets, list) else [])
    )
    return bool(has_name and has_age_or_birth)
