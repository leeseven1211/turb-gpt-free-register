"""Read and resume bulk commands through their durable task and receipts."""
from core.operations import bulk_mutation_worker as worker, task_gateway
from core.storage.operations import bulk_mutations as commands, runtime

DEFAULT_PAGE_SIZE = 500
MAX_PAGE_SIZE = 5000
MAX_DB_ID = 2**63 - 1


def _public_identifiers(value, *, field=""):
    if isinstance(value, dict):
        return {key: _public_identifiers(item, field=key) for key, item in value.items()}
    if isinstance(value, list):
        identifier = field[:-1] if field.endswith("_ids") else ""
        return [_public_identifiers(item, field=identifier) for item in value]
    if type(value) is int and (field in {"id", "key", "command_id", "task_id", "run_id"}
                                or field.endswith("_id")):
        return str(value)
    return value


def public_submission(receipt: dict) -> dict:
    """Keep command and task IDs exact when JavaScript decodes the response."""
    return _public_identifiers(receipt)


def read_receipt(command_id: int, *, offset: int = 0, limit: int = DEFAULT_PAGE_SIZE) -> dict:
    if not 0 <= offset <= MAX_DB_ID or not 1 <= limit <= MAX_PAGE_SIZE:
        raise ValueError("invalid_bulk_pagination")
    if not 1 <= command_id <= MAX_DB_ID:
        raise LookupError("bulk_command_not_found")
    receipt = commands.read_receipt_page(command_id, offset=offset, limit=limit)
    next_offset = offset + len(receipt["items"])
    return _public_identifiers({
        **receipt,
        "offset": offset,
        "limit": limit,
        "next_offset": next_offset if next_offset < receipt["item_count"] else None,
    })


def resume_interrupted_commands() -> int:
    """Retry only after existing orphan recovery releases execution ownership."""
    operations = worker.registered_bulk_mutation_operations()
    if worker.TASK_TYPE not in task_gateway.registered_dispatch_types() or not operations:
        return 0
    queued = 0
    for command in commands.list_recoverable_commands(operations):
        run = runtime.retry_runtime_task(
            command["task_id"], expected_previous_run_id=command["run_id"], trigger="bulk_worker_restart",
        )
        queued += not run.get("dependency_stale", False)
    if queued:
        task_gateway.notify_dispatch()
    return queued


def worker_status(dispatcher: dict) -> dict:
    registered = (worker.TASK_TYPE in dispatcher.get("registered_task_types", ())
                  and bool(worker.registered_bulk_mutation_operations()))
    return {
        "started": registered and dispatcher.get("started") is True,
        "alive": registered and dispatcher.get("alive") is True,
        **commands.queue_counts(),
    }
