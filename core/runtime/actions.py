"""Explicit Task Center action catalog; installation never starts execution."""
from __future__ import annotations

from importlib import import_module

ACTION_TARGETS = (
    "core.accounts.operation_handlers:register_actions",
    "core.accounts.liveness.service:register_actions",
    "core.accounts.plans.service:register_actions",
    "core.accounts.deactivation.mail_scan:register_actions",
    "core.accounts.email_change.service:register_actions",
    "core.accounts.inspection.service:register_actions",
    "core.extract_link.service:register_actions",
    "core.codex.operation_service:register_actions",
    "core.codex.token_refresh_actions:register_actions",
    "core.integrations.sub2api.monitor:register_actions",
    "core.integrations.sub2api.jobs:register_actions",
    "core.integrations.sub2api.manual_upload:register_actions",
    "core.integrations.c2a.manual_sync:register_actions",
    "core.integrations.c2a.monitor:register_actions",
    "core.maintenance.sentinel:register_actions",
)


def register_actions() -> None:
    """Install domain-owned actions for persisted tasks before serving routes."""
    for target in ACTION_TARGETS:
        module, function = target.split(":", 1)
        getattr(import_module(module), function)()
