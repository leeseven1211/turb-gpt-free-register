"""Application composition for the local mutations accepted by Web and Worker."""
from core.operations import bulk_mutation_worker as worker, bulk_terminate_command, task_gateway
from core.storage.accounts import bulk_mutations as accounts
from core.storage.codex import bulk_mutations as codex
from core.storage.email import bulk_mutations as email
from core.extract_link import workbench_bulk as extract

_DOMAINS = (accounts, codex, email, extract)


def register_commands() -> None:
    """Install the domain command definitions without enabling execution."""
    for domain in _DOMAINS:
        domain.register_handlers(worker.register_bulk_mutation_definition)
    bulk_terminate_command.register_commands()
    task_gateway.register_operation_actions(
        worker.TASK_TYPE,
        retry_handler=task_gateway.default_operation_retry,
        cancel_handler=task_gateway.default_operation_cancel,
        terminate_handler=task_gateway.default_operation_terminate,
        source_systems=("native_operations",),
    )


def register_worker() -> None:
    for domain in _DOMAINS:
        domain.register_handlers()
    worker.register_runtime_handler()
    bulk_terminate_command.register_worker()
