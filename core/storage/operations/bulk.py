# -*- coding: utf-8 -*-
"""批量管理仓储公开入口。"""

from core.storage.operations.bulk_schema import init, reset_ready
from core.storage.operations.bulk_common import BulkError, BUCKETS
from core.storage.operations.bulk_selections import (
    create_selection,
    freeze_selection,
    get_selection,
    fail_selection,
    find_selection_request,
)
from core.storage.operations.bulk_batches import (
    create_batch,
    get_batch,
    list_batches,
    list_active_batches,
    create_round,
    freeze_round,
    materialize_targets,
    list_targets,
    get_round,
    list_rounds,
    fail_round,
)
from core.storage.operations.bulk_runtime import (
    prepare_targets,
    submit_targets,
    process_batch,
    lock_managed_target,
    ensure_managed_claim,
    record_managed_change,
    inherit_managed_run,
)
from core.storage.operations.bulk_projection import project_pending, project_batch
from core.storage.operations.bulk_report import get_plan_report
from core.storage.operations.bulk_control import (
    request_control,
    settle_control,
    claim_work,
    renew_work,
    expire_selections,
)


__all__ = [
    "init",
    "reset_ready",
    "BulkError",
    "BUCKETS",
    "create_selection",
    "freeze_selection",
    "get_selection",
    "fail_selection",
    "find_selection_request",
    "create_batch",
    "get_batch",
    "list_batches",
    "list_active_batches",
    "create_round",
    "freeze_round",
    "materialize_targets",
    "list_targets",
    "get_round",
    "list_rounds",
    "fail_round",
    "prepare_targets",
    "submit_targets",
    "process_batch",
    "lock_managed_target",
    "ensure_managed_claim",
    "record_managed_change",
    "inherit_managed_run",
    "project_pending",
    "project_batch",
    "get_plan_report",
    "request_control",
    "settle_control",
    "claim_work",
    "renew_work",
    "expire_selections",
]
