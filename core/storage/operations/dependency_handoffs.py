"""Rollback only an admitted dependency whose business callback never started."""
from core.bulk_operations import execution as bulk_execution
from core.storage.operations import common


def requeue_dependency(dependency_id: int, *, permit_id: str, execution_id: str,
                       attempts: int, reason: str) -> bool:
    # Dependencies have no execution_id column. The existing unreleased permit
    # plus the exact claimed attempt fences this transition without new DDL.
    with common._connect() as conn, conn.cursor() as cur, bulk_execution.dependency_update(
            conn, dependency_id=int(dependency_id)):
        cur.execute(
            f"""SELECT permit_id FROM {common._table('operation_execution_permits')}
                WHERE permit_id=%s AND execution_id=%s AND execution_key=%s
                  AND released_at IS NULL FOR UPDATE""",
            (str(permit_id), str(execution_id), f"operation_dependency:{int(dependency_id)}"),
        )
        if cur.fetchone() is None:
            return False
        cur.execute(
            f"""UPDATE {common._table('operation_task_dependencies')}
                SET status='ready', attempts=GREATEST(attempts - 1, 0),
                    next_attempt_at=NULL, last_error=%s, updated_at=now()
                WHERE id=%s AND status='running' AND attempts=%s""",
            (str(reason)[:500], int(dependency_id), int(attempts)),
        )
        return cur.rowcount > 0
