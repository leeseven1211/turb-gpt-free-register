"""Canonical execution startup order; descriptions do not import any component."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ComponentSpec:
    name: str
    kind: str
    target: str
    required: bool = True
    with_logger: bool = False
    stop_target: str | None = None


# Owner acquisition is performed by the controller before this sequence.
# T5 adds config observation explicitly; T3/T4/T6 wire this context's admission
# gate into every claim/producer path before this plan is activated.
COMPONENTS = (
    ComponentSpec("operation_storage", "initializer", "core.operation_task_store:init"),
    ComponentSpec("settlement", "service", "core.operations.settlement:start_runtime",
                  stop_target="core.operations.settlement:stop_runtime"),
    ComponentSpec("bulk_storage", "initializer", "core.storage.operations.bulk:init"),
    ComponentSpec("config_observer", "service", "core.runtime.config_observer:create_config_observer"),
    ComponentSpec("recover_before_handlers", "recovery", "core.operations.reconciliation:recover_before_handlers", with_logger=True),
    ComponentSpec("proxy_pool", "service", "core.proxy.pool:start", required=False),
    ComponentSpec("maintenance_handlers", "handlers", "core.accounts.liveness.service:register_maintenance_operation_handlers"),
    ComponentSpec("account_handlers", "handlers", "core.accounts.operation_handlers:register_runtime_handlers"),
    ComponentSpec("codex_retry_handler", "handlers", "core.codex.operation_service:register_handler"),
    ComponentSpec("codex_refresh_handler", "handlers", "core.codex.token_refresh_service:_register_worker"),
    ComponentSpec("sentinel_handler", "handlers", "core.maintenance.sentinel:register_handler"),
    ComponentSpec("sub2api_monitor_handler", "handlers", "core.integrations.sub2api.monitor:register_handler"),
    ComponentSpec("sub2api_upload_handler", "handlers", "core.integrations.sub2api.manual_upload:register_handler"),
    ComponentSpec("c2a_sync_handler", "handlers", "core.integrations.c2a.manual_sync:register_handler"),
    ComponentSpec("verify_handlers", "check", "core.operations.task_gateway:registered_dispatch_types"),
    ComponentSpec("recover_before_dispatchers", "recovery", "core.operations.reconciliation:recover_before_dispatchers", with_logger=True),
    ComponentSpec("projection_worker", "service", "core.operation_task_store:start_projection_worker"),
    ComponentSpec("registration_dispatcher", "service", "core.registration.service:start_dispatcher",
                  stop_target="core.registration.service:stop_dispatcher"),
    ComponentSpec("operation_dispatcher", "service", "core.operations.task_gateway:start_dispatcher",
                  stop_target="core.operations.task_gateway:stop_dispatcher"),
    ComponentSpec("dependency_handler", "handlers", "core.accounts.completion_dependencies:submit_ready_completion_dependency"),
    ComponentSpec("dependency_dispatcher", "service", "core.operations.task_gateway:start_dependency_dispatcher",
                  stop_target="core.operations.task_gateway:stop_dependency_dispatcher"),
    ComponentSpec("bulk_workers", "service", "core.bulk_operations.service:start_workers"),
    ComponentSpec("butler_import_dispatcher", "service", "core.email.email_butler.manual_import:start_dispatcher",
                  stop_target="core.email.email_butler.manual_import:stop_dispatcher"),
    ComponentSpec("recover_ready_dependencies", "recovery", "core.operations.reconciliation:recover_ready_dependencies", with_logger=True),
    ComponentSpec("recover_local_artifacts", "recovery", "core.operations.reconciliation:recover_local_artifacts", with_logger=True),
    ComponentSpec("sms_cancel_worker", "service", "core.sms.provider:start_cancel_worker"),
    ComponentSpec("recover_account_background_state", "recovery", "core.operations.reconciliation:recover_account_background_state", with_logger=True),
    ComponentSpec("deactivation_scanner", "service", "core.accounts.deactivation.mail_scan:start_periodic_scanner"),
    ComponentSpec("at_refresher", "service", "core.accounts.token_refresh:start_periodic_refresher"),
    ComponentSpec("codex_refresher", "service", "core.codex.token_refresh_service:start_periodic_refresher"),
    ComponentSpec("sub2api_sync", "service", "core.integrations.sub2api.jobs:start_periodic_sync"),
    ComponentSpec("sub2api_monitor", "service", "core.integrations.sub2api.monitor:start_periodic_monitor"),
    ComponentSpec("auth_context_cleanup", "service", "core.accounts.auth_context_cleanup:start_periodic_cleanup"),
    ComponentSpec("task_retention", "service", "core.operations.retention:start_periodic_cleanup"),
    ComponentSpec("email_usage_reports", "service", "core.email.email_butler.usage_reports:start_worker", required=False),
    ComponentSpec("email_service_sync", "service", "core.email.email_butler.service_facts:start_worker", required=False),
)


# Web consumes the same application definitions but executes none of these
# callbacks. Both execution modes use exactly this one registration catalog.
HANDLER_COMPONENTS = tuple(spec.name for spec in COMPONENTS if spec.kind == "handlers")

REQUIRED_DISPATCH_TYPES = frozenset({
    "account_setup_retry", "password_setup", "password_change", "twofa_setup", "twofa_change",
    "account_completion", "registration_resume", "account_inspection", "live_check", "token_refresh",
    "plan_check", "deactivation_mail", "extract_link", "email_change", "codex_retry",
    "codex_token_refresh", "sentinel_maintenance_check", "sub2api_scan", "sub2api_manual_upload",
    "c2a_session_reimport",
})
