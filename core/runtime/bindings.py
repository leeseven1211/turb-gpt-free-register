"""Lazy calls into existing domain implementations; no alternate handlers."""
from __future__ import annotations

from collections.abc import Callable
from importlib import import_module
import time
from typing import Any

from .composition import ComponentHooks
from .manifest import COMPONENTS, REQUIRED_DISPATCH_TYPES


def build_components(
    *, resolve: Callable[[str], Any] = import_module,
) -> dict[str, ComponentHooks]:
    def lookup(target: str):
        module_name, attr = target.split(":", 1)
        return getattr(resolve(module_name), attr)

    def starter(spec):
        def start(context):
            target = lookup(spec.target)
            if spec.name == "settlement":
                domain = resolve("core.storage.operations.permits")._settlement_domain()
                if target(domain=domain, admission=context.admission) is not True:
                    raise RuntimeError("settlement_start_unconfirmed")
                return True
            if spec.name == "proxy_pool":
                return target(prewarm=True)
            if spec.name == "dependency_handler":
                return resolve("core.operations.task_gateway").set_dependency_ready_handler(target)
            if spec.name == "verify_handlers":
                if not REQUIRED_DISPATCH_TYPES <= set(target()):
                    raise RuntimeError("runtime_handlers_incomplete")
                return None
            if spec.with_logger:
                return target(context.logger)
            return target()
        return start

    def stopper(spec):
        def stop(_context, remaining):
            target = lookup(spec.stop_target)
            if spec.name == "settlement":
                deadline = time.monotonic() + max(0., remaining)
                # Startup rollback also retains the carrier if a callback or
                # physical cleanup is still owned by this execution process.
                module_name, _attr = spec.stop_target.split(":", 1)
                if getattr(resolve(module_name), "drain_runtime")(deadline) is not True:
                    return False
                if resolve("core.operations.concurrency").stop_release_runtime(deadline) is not True:
                    return False
                return target(deadline)
            return target(timeout=remaining)
        return stop

    # Missing/unsafe stop contracts remain unsupported until T6 supplies
    # truthful bounded stop hooks. Never turn None into "stopped".
    return {
        spec.name: ComponentHooks(
            starter(spec),
            stopper(spec) if spec.stop_target else None,
        )
        for spec in COMPONENTS
    }
