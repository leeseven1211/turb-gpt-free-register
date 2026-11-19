"""Fence explicit legacy CLI execution against a managed Worker for this instance."""
from __future__ import annotations

import atexit
import threading
from pathlib import Path

_LOCK = threading.RLock()
_OWNER = None
_BINDING = None
_LOST = threading.Event()


def execution_allowed() -> bool:
    """Retain offline compatibility, but fence an explicitly owned CLI forever on loss."""
    with _LOCK:
        if _LOST.is_set():
            return False
        if _OWNER is None:
            return True
        try:
            _OWNER.require_owner()
        except Exception:
            _LOST.set()
            return False
        return not _LOST.is_set()


def require_standalone_owner(*, bootstrap=None, schema=None, connect_dedicated=None) -> None:
    """Own the default instance, or one explicitly bound maintenance target."""
    from .process import get_runtime_context
    context = get_runtime_context()
    if context is not None:
        if not context.executes:
            raise RuntimeError('web_execution_forbidden')
        return
    explicit = any(value is not None for value in (bootstrap, schema, connect_dedicated))
    if explicit and any(value is None for value in (bootstrap, schema, connect_dedicated)):
        raise ValueError('standalone_owner_binding_incomplete')
    global _OWNER, _BINDING
    with _LOCK:
        if _LOST.is_set():
            raise RuntimeError('owner_lost')
        if bootstrap is not None:
            if bootstrap.mode == 'web':
                raise RuntimeError('web_execution_forbidden')
            binding = (bootstrap.instance_id, str(Path(bootstrap.runtime_dir).resolve()),
                       str(schema), connect_dedicated)
            if _OWNER is not None and binding != _BINDING:
                raise RuntimeError('standalone_owner_binding_mismatch')
        if _OWNER is None:
            from .instance_owner import ExecutionOwner
            if not explicit:
                from .bootstrap import RuntimeBootstrap
                from core.storage import postgres
                bootstrap = RuntimeBootstrap.from_environment(project_root=Path(__file__).resolve().parents[2])
                schema, connect_dedicated = postgres.schema_name(), postgres.connect_dedicated
            if bootstrap.mode == 'web':
                raise RuntimeError('web_execution_forbidden')
            owner = ExecutionOwner(mode='combined',instance_id=bootstrap.instance_id,
                schema=schema,stable_dir=bootstrap.runtime_dir,
                connect_dedicated=connect_dedicated,on_lost=_LOST.set)
            try:
                owner.start()
            except BaseException:
                owner.close(timeout=2)
                raise
            _OWNER = owner
            _BINDING = (bootstrap.instance_id, str(Path(bootstrap.runtime_dir).resolve()),
                        str(schema), connect_dedicated)
            # Export finalizers may run after this callback. Close admission
            # now, but retain the raw file fence until the process exits.
            atexit.register(_LOST.set)
        _OWNER.require_owner()
