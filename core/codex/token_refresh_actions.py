"""Durable Codex refresh controls, independent of Worker initialization."""
from core.operations import task_gateway


def register_actions() -> None:
    """Match the gateway defaults installed by the refresh execution handler."""
    task_gateway.register_operation_actions(
        "codex_token_refresh",
        retry_handler=task_gateway.default_operation_retry,
        cancel_handler=task_gateway.default_operation_cancel,
        terminate_handler=task_gateway.default_operation_terminate,
    )
