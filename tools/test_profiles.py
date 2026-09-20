"""Profile selection helpers for the guarded pytest runner."""
from __future__ import annotations

PROFILES = ("default", "extended", "all")


def marker_expression(profile: str) -> str | None:
    """Return the pytest marker expression for a supported profile."""
    if profile == "default":
        return "not extended"
    if profile == "extended":
        return "extended"
    if profile == "all":
        return None
    raise ValueError(f"未知测试 profile: {profile!r}")


def apply_profile(arguments: list[str], profile: str) -> list[str]:
    """Add the profile selector to pytest arguments without duplicating ``--``."""
    expression = marker_expression(profile)
    values = list(arguments)
    if values and values[0] == "--":
        values.pop(0)
    if any(value in {"-m", "--markexpr"} for value in values):
        raise ValueError("测试 profile 不能与 pytest -m/--markexpr 同时使用")
    if expression is not None:
        values.extend(["-m", expression])
    return values
