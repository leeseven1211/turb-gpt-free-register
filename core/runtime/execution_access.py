"""Execution-role boundary; entrypoints install managed context explicitly.

Unmanaged CLI compatibility is explicit here. Managed Web always persists requests
without creating execution carriers; managed workers require owner and admission.
"""
from __future__ import annotations


def _context():
    from core.runtime.process import get_runtime_context
    return get_runtime_context()


def _standalone_allowed() -> bool:
    from core.runtime.standalone import execution_allowed
    return execution_allowed()


def component_start_allowed() -> bool:
    context = _context()
    if context is None:
        return _standalone_allowed()
    return bool(context.executes)


def execution_allowed() -> bool:
    context = _context()
    if context is None:
        return _standalone_allowed()
    if not context.executes:
        return False
    from core.runtime.process import execution_admitted
    return bool(execution_admitted())


def execution_owner_valid() -> bool:
    """Existing work may settle during drain while the same owner is valid."""
    context = _context()
    if context is None:
        return _standalone_allowed()
    if not context.executes:
        return False
    from core.runtime.process import execution_owner_valid as owner_valid
    return bool(owner_valid())


def execution_support_allowed() -> bool:
    """Keep resources for active work available while managed claims drain."""
    context = _context()
    if context is None:
        return _standalone_allowed()
    if execution_allowed():
        return True
    reasons = set(context.admission.reasons())
    return ("draining" in reasons
            and not reasons.intersection({"startup", "startup_failed", "owner_lost"})
            and execution_owner_valid())


def require_execution_component() -> None:
    if not component_start_allowed():
        raise RuntimeError('web_execution_forbidden')
