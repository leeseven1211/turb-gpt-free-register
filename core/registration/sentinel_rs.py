"""Rust sentinel-rs 注册驱动的公开门面。"""
from __future__ import annotations

from core.kernels.rust.sentinel_rs import run_sentinel_rs_registration as run_sentinel_rs_registration

__all__ = ["run_sentinel_rs_registration"]
