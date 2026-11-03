"""One-shot, OS-isolated DOM experiment. It never opens an HTTP transport.

The callback must enforce request policy and its shared StageBudget (as the
coordinator does). Completing this runtime is not evidence of clearance or of a
verified page. Unsupported hosts/dependencies fail closed at this boundary.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import time
from typing import Any, Callable

from core.auth.challenge import AuthCancelledError


_RUNTIME_DIR = Path(__file__).resolve().parents[2] / "sentinel" / "cloudflare"
_MAX_LINE = 384 * 1024
_MAX_INPUT = 2 * 1024 * 1024
_MAX_OUTPUT = 4 * 1024 * 1024
_MAX_BODY = 256 * 1024
_MAX_RESPONSE = 1024 * 1024


def _sandbox_command() -> list[str] | None:
    """Return an isolated launch, never an unisolated portability fallback.

    The only readable application data is this independent runtime package.
    System libraries and installed Homebrew dylibs are executable dependencies;
    user files, writes, network, process creation, and other executables are not
    permitted. Metadata reads support Node's module resolution without exposing
    file contents outside this allowlist.
    """
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        return None
    node = shutil.which("node", path="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin")
    if not node or not (_RUNTIME_DIR / "node_modules" / "jsdom" / "package.json").is_file():
        return None
    node_path = str(Path(node).resolve())
    quote = lambda value: json.dumps(str(value))
    profile = """(version 1)
(deny default)
(allow process-exec (literal NODE))
(allow process-info* (target self))
(allow signal (target self))
(allow sysctl-read)
(allow file-read-metadata)
(allow file-read* (literal "/") (literal NODE) (subpath RUNTIME)
 (subpath "/usr/lib") (subpath "/System/Library")
 (literal "/dev/null") (literal "/dev/random") (literal "/dev/urandom")
 (regex #"^/usr/local/Cellar/[^/]+/[^/]+/lib(/|$)")
 (regex #"^/opt/homebrew/Cellar/[^/]+/[^/]+/lib(/|$)"))
""".replace("NODE", quote(node_path)).replace("RUNTIME", quote(_RUNTIME_DIR))
    return ["/usr/bin/sandbox-exec", "-p", profile, node_path,
            "--max-old-space-size=192", str(_RUNTIME_DIR / "runtime.cjs")]


def _message(request: Any, previous_id: int) -> tuple[int, dict[str, Any]]:
    if not isinstance(request, dict) or request.get("type") != "request":
        raise ValueError("invalid runtime message")
    request_id = request.get("id")
    body = request.get("request")
    if type(request_id) is not int or request_id != previous_id + 1 or request_id > 12:
        raise ValueError("invalid runtime request sequence")
    if not isinstance(body, dict) or set(body) != {"kind", "method", "url", "headers", "body"}:
        raise ValueError("invalid runtime request shape")
    if body["kind"] not in {"fetch", "xhr", "script", "iframe"}:
        raise ValueError("invalid runtime request kind")
    if body["method"] not in {"GET", "POST"} or not isinstance(body["url"], str):
        raise ValueError("invalid runtime request target")
    if body["body"] is not None and (not isinstance(body["body"], str) or
                                        len(body["body"].encode()) > _MAX_BODY):
        raise ValueError("oversized runtime request body")
    headers = body["headers"]
    if not isinstance(headers, dict) or len(headers) > 64 or any(
        not isinstance(k, str) or not isinstance(v, str) for k, v in headers.items()
    ):
        raise ValueError("invalid runtime headers")
    return request_id, body


def _reply(value: Any, request_id: int) -> bytes:
    if not isinstance(value, dict) or type(value.get("status")) is not int:
        raise ValueError("invalid bridge response")
    if not isinstance(value.get("body"), str):
        raise ValueError("invalid bridge body")
    if len(value["body"]) > 4 * ((_MAX_RESPONSE + 2) // 3):
        raise ValueError("oversized bridge response")
    if len(base64.b64decode(value["body"], validate=True)) > _MAX_RESPONSE:
        raise ValueError("oversized bridge response")
    encoded = json.dumps({"type": "response", "id": request_id, "response": value},
                         ensure_ascii=True, separators=(",", ":")).encode() + b"\n"
    if len(encoded) > _MAX_INPUT:
        raise ValueError("oversized bridge message")
    return encoded


def _terminate(process: subprocess.Popen) -> None:
    # Kill the whole session even if a corrupted runner already exited. No
    # descendants may survive a successful return, deadline or cancellation.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except PermissionError:
        # macOS can report EPERM for a group containing only an unreaped
        # sandboxed zombie. poll() reaps it; a live child must still be killed.
        if process.poll() is None:
            process.kill()
    process.wait(timeout=1)
    if process.stdin:
        process.stdin.close()
    if process.stdout:
        process.stdout.close()


def run_runtime(payload: dict, bridge: Callable[[dict], dict], budget: Any) -> bool:
    """Run a local DOM fixture/challenge with all I/O delegated to ``bridge``.

    Exceptions from cancellation propagate. Infrastructure/protocol failures
    return False, allowing the coordinator to preserve the original response.
    JS Cookie writes are DOM-local; only transport-observed server cookies may
    update the real session.
    """
    budget.check_cancelled()
    remaining = min(12.0, budget.remaining())
    if remaining <= 0:
        return False
    command = _sandbox_command()
    if command is None:
        return False
    process = None
    try:
        if not isinstance(payload, dict) or not isinstance(payload.get("html"), str):
            return False
        initial = dict(payload)
        initial["waitMs"] = min(10000, max(1, int(initial.get("waitMs", 10000))))
        outgoing = bytearray(json.dumps({"type": "init", "payload": initial},
                                       ensure_ascii=True).encode() + b"\n")
        if len(outgoing) > _MAX_INPUT:
            return False
        # No HOME, proxy, Node preload/search options, credentials or inherited
        # application variables. Challenges are kept on anonymous pipes only.
        environment = {"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C", "TZ": "UTC",
                       "OPENSSL_CONF": "/dev/null"}
        deadline = time.monotonic() + remaining
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.DEVNULL, cwd=_RUNTIME_DIR,
                                   env=environment, start_new_session=True, close_fds=True)
        assert process.stdin and process.stdout
        os.set_blocking(process.stdin.fileno(), False)
        os.set_blocking(process.stdout.fileno(), False)
        incoming = bytearray()
        output_bytes = 0
        previous_id = 0
        with selectors.DefaultSelector() as selector:
            selector.register(process.stdout, selectors.EVENT_READ)
            selector.register(process.stdin, selectors.EVENT_WRITE)
            write_registered = True
            while True:
                budget.check_cancelled()
                left = min(deadline - time.monotonic(), budget.remaining())
                if left <= 0:
                    return False
                for key, _ in selector.select(min(.05, left)):
                    if key.fileobj is process.stdin:
                        if outgoing:
                            count = os.write(process.stdin.fileno(), outgoing[:65536])
                            del outgoing[:count]
                        if not outgoing:
                            selector.unregister(process.stdin)
                            write_registered = False
                        continue
                    block = os.read(process.stdout.fileno(), 65536)
                    if not block:
                        return False
                    incoming.extend(block)
                    output_bytes += len(block)
                    if output_bytes > _MAX_OUTPUT:
                        return False
                    while b"\n" in incoming:
                        raw, _, rest = incoming.partition(b"\n")
                        incoming = bytearray(rest)
                        if len(raw) > _MAX_LINE:
                            return False
                        message = json.loads(raw)
                        if isinstance(message, dict) and message.get("type") == "done":
                            return message == {"type": "done", "ok": True} and not incoming
                        previous_id, request = _message(message, previous_id)
                        budget.check_cancelled()
                        reply = _reply(bridge(request), previous_id)
                        budget.check_cancelled()
                        if time.monotonic() >= deadline or budget.remaining() <= 0:
                            return False
                        outgoing.extend(reply)
                        if len(outgoing) > _MAX_INPUT:
                            return False
                        if not write_registered:
                            selector.register(process.stdin, selectors.EVENT_WRITE)
                            write_registered = True
                    if len(incoming) > _MAX_LINE:
                        return False
    except AuthCancelledError:
        raise
    except (OSError, ValueError, TypeError, RuntimeError, subprocess.SubprocessError):
        return False
    finally:
        if process is not None:
            _terminate(process)
