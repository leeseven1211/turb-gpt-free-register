"""Offline fixtures exercise the actual OS sandbox; no account or CF traffic."""

import base64
import json
import os
from pathlib import Path
import tempfile
import threading
import time
from unittest import mock

import pytest

from core.auth.state_machine import CancellationRequested, StageBudget
from core.network import cloudflare_runtime as runtime


def payload(html, wait=350):
    return {"url": "https://chatgpt.com/auth/login", "html": html,
            "userAgent": "OfflineFixture/1", "browserIdentity": {"platform": "MacIntel"},
            "cookies": [{"name": "visible", "value": "yes", "path": "/", "secure": True,
                         "domain": "chatgpt.com", "hostOnly": True},
                        {"name": "secret", "value": "hidden", "httpOnly": True,
                         "domain": "chatgpt.com", "path": "/"}], "waitMs": wait}


def response(body="", url="https://chatgpt.com/cdn-cgi/challenge-platform/probe", cookies=()):
    return {"status": 200, "url": url, "headers": {"content-type": "text/javascript"},
            "body": base64.b64encode(body.encode()).decode(), "cookies": list(cookies)}


def require_sandbox():
    if runtime._sandbox_command() is None:
        pytest.skip("macOS sandbox-exec and Node >=20 with npm ci are required")


def test_fetch_xhr_scripts_and_cookie_visibility_use_python_bridge():
    require_sandbox()
    seen = []

    def bridge(request):
        seen.append(request)
        if request["url"].endswith("/script"):
            return response("window.fromScript = 7", request["url"], [{"name": "visible", "value": "yes",
                            "domain": "chatgpt.com", "path": "/", "hostOnly": True, "secure": True}])
        if request["url"].endswith("/first"):
            return response("reply", request["url"], [{"name": "visible", "value": "yes",
                            "domain": "chatgpt.com", "path": "/", "hostOnly": True, "secure": True},
                            {"name": "server", "value": "new",
                            "domain": "chatgpt.com", "path": "/", "secure": True}])
        return response("", request["url"])

    html = """<script src='/cdn-cgi/challenge-platform/script'></script><script>
    (async () => {
      const r = await fetch('/cdn-cgi/challenge-platform/first');
      const x = new XMLHttpRequest();
      x.open('POST', '/cdn-cgi/challenge-platform/result');
      x.send(JSON.stringify({text: await r.text(), cookie: document.cookie,
                            script: window.fromScript, ua: navigator.userAgent}));
    })();</script>"""
    assert runtime.run_runtime(payload(html), bridge, StageBudget.start(5)) is True
    assert [r["kind"] for r in seen] == ["script", "fetch", "xhr"]
    result = json.loads(seen[-1]["body"])
    assert result == {"text": "reply", "cookie": "visible=yes; server=new", "script": 7,
                      "ua": "OfflineFixture/1"}


def test_iframe_executes_real_fixture_and_exchanges_messages_with_parent():
    require_sandbox()
    seen = []

    def bridge(request):
        seen.append(request)
        if request["kind"] == "iframe":
            return response("""<script>
              addEventListener('message', e => {
                if(e.origin === 'https://chatgpt.com' && e.data === 'pong')
                  fetch('/cdn-cgi/challenge-platform/child-ack', {method:'POST',
                    body: document.cookie || 'empty'});
              });
              parent.postMessage('ping', 'https://chatgpt.com');
            </script>""", request["url"])
        return response("", request["url"])

    html = """<script>
      addEventListener('message', e => {
        if(e.origin === 'https://challenges.cloudflare.com' &&
           e.source === document.querySelector('iframe').contentWindow && e.data === 'ping')
          e.source.postMessage('pong', e.origin);
      });
      const f = document.createElement('iframe');
      f.src = 'https://challenges.cloudflare.com/cdn-cgi/challenge-platform/frame';
      document.body.appendChild(f);
    </script>"""
    assert runtime.run_runtime(payload(html), bridge, StageBudget.start(5)) is True
    assert len(seen) == 2
    assert seen[1]["url"] == "https://challenges.cloudflare.com/cdn-cgi/challenge-platform/child-ack"
    assert seen[1]["body"] == "empty"


def test_os_sandbox_blocks_vm_escape_file_network_process_and_environment():
    require_sandbox()
    seen = []
    with tempfile.NamedTemporaryFile(mode="w", prefix="turb-runtime-secret-") as secret:
        secret.write("fixture secret")
        secret.flush()
        html = """<script>(async () => {
          const p = this.constructor.constructor('return process')();
          const require = p.getBuiltinModule;
          let file = false, write = false, child = false, selfChild = false;
          try { require('fs').readFileSync(__SECRET_PATH__); file = true; } catch (_) {}
          try { require('fs').writeFileSync(__SECRET_PATH__ + '.written', 'bad'); write = true; } catch (_) {}
          try { require('child_process').execFileSync('/bin/echo', ['bad']); child = true; } catch (_) {}
          try { require('child_process').execFileSync(p.execPath, ['-e', '']); selfChild = true; } catch (_) {}
          const network = await new Promise(resolve => {
            const s = require('net').connect({host: '127.0.0.1', port: 9});
            s.once('connect', () => {s.destroy(); resolve('connected')});
            s.once('error', error => resolve(error.code));
          });
          await fetch('/cdn-cgi/challenge-platform/report', {method: 'POST',
            body: JSON.stringify({file, write, child, selfChild, network, env: p.env.CF_TEST_SECRET || null})});
        })();</script>""".replace("__SECRET_PATH__", json.dumps(secret.name))
        with mock.patch.dict(os.environ, {"CF_TEST_SECRET": "must-not-leak"}):
            assert runtime.run_runtime(payload(html, 600), lambda r: seen.append(r) or response(),
                                       StageBudget.start(5)) is True
        assert not Path(secret.name + ".written").exists()
    assert json.loads(seen[0]["body"]) == {"file": False, "write": False, "child": False,
                                           "selfChild": False, "network": "EPERM", "env": None}


def test_dynamic_script_binary_response_and_wrong_target_origin():
    require_sandbox()
    seen = []

    def bridge(request):
        seen.append(request)
        if request["kind"] == "script":
            return response("window.dynamic = 11", request["url"])
        return {**response(url=request["url"]), "body": "AP9B"}

    html = """<script>
      addEventListener('message', () => fetch('/cdn-cgi/challenge-platform/unwanted'));
      postMessage('ignore', 'https://other.invalid');
      const script = document.createElement('script');
      script.src = '/cdn-cgi/challenge-platform/dynamic';
      script.onload = async () => {
        const r = await fetch('/cdn-cgi/challenge-platform/binary');
        await fetch('/cdn-cgi/challenge-platform/result', {method:'POST',
          body:JSON.stringify({dynamic, bytes:Array.from(new Uint8Array(await r.arrayBuffer()))})});
      };
      document.body.appendChild(script);
    </script>"""
    assert runtime.run_runtime(payload(html), bridge, StageBudget.start(5)) is True
    assert [r["url"].rsplit("/", 1)[-1] for r in seen] == ["dynamic", "binary", "result"]
    assert json.loads(seen[-1]["body"]) == {"dynamic": 11, "bytes": [0, 255, 65]}


@pytest.mark.parametrize("body", ["!invalid-base64!", base64.b64encode(b"x" * (1024 * 1024 + 1)).decode()],
                         ids=["bad-base64", "oversized-response"])
def test_bad_bridge_body_is_rejected_and_child_reaped(body):
    require_sandbox()
    assert runtime.run_runtime(payload("<script>fetch('/cdn-cgi/challenge-platform/check')</script>"),
                               lambda r: {**response(), "body": body}, StageBudget.start(5)) is False


def test_cookie_domain_path_secure_and_script_writes_are_dom_local():
    require_sandbox()
    seen = []
    data = payload("""<script>
      document.cookie = 'local=value; Secure; Path=/';
      fetch('/cdn-cgi/challenge-platform/report', {method:'POST', body:document.cookie});
    </script>""")
    data["cookies"] += [{"name": "wrongPath", "value": "hidden", "domain": "chatgpt.com", "path": "/else"},
                        {"name": "wrongDomain", "value": "hidden", "domain": "other.invalid", "path": "/"}]
    assert runtime.run_runtime(data, lambda r: seen.append(r) or response(), StageBudget.start(5)) is True
    assert seen == [{"kind": "fetch", "method": "POST", "url": "https://chatgpt.com/cdn-cgi/challenge-platform/report",
                     "headers": {}, "body": "visible=yes; local=value"}]


def test_server_cookie_deletion_reconciles_only_visible_scopes():
    require_sandbox()
    seen = []
    data = payload("""<script>(async () => {
      await fetch('/cdn-cgi/challenge-platform/expire');
      await fetch('/cdn-cgi/challenge-platform/report', {method:'POST', body:document.cookie});
      const iframe = document.createElement('iframe');
      iframe.src = '/else/frame'; document.body.appendChild(iframe);
    })();</script>""")
    data["cookies"] += [{"name": "otherPath", "value": "kept", "domain": "chatgpt.com", "path": "/else"}]

    def bridge(request):
        seen.append(request)
        if request["kind"] == "iframe":
            return response("<script>fetch('/cdn-cgi/challenge-platform/frame-report', {method:'POST', body:document.cookie})</script>",
                            request["url"], [{"name": "otherPath", "value": "kept", "domain": "chatgpt.com", "path": "/else"}])
        return response("", request["url"])

    assert runtime.run_runtime(data, bridge, StageBudget.start(5)) is True
    assert seen[1]["body"] == ""
    assert seen[-1]["body"] == "otherPath=kept"


def test_dom_lifecycle_events_fire_once_after_external_scripts():
    require_sandbox()
    seen = []

    def bridge(request):
        seen.append(request)
        if request["kind"] == "script":
            return response("window.scriptReady = true", request["url"])
        return response("", request["url"])

    html = """<script>
      let loaded = 0, contentLoaded = 0;
      addEventListener('load', () => loaded++);
      document.addEventListener('DOMContentLoaded', () => contentLoaded++);
      setTimeout(() => fetch('/cdn-cgi/challenge-platform/report', {method:'POST',
        body:JSON.stringify({loaded, contentLoaded, ready:window.scriptReady})}), 80);
    </script><script src='/cdn-cgi/challenge-platform/script'></script>"""
    assert runtime.run_runtime(payload(html), bridge, StageBudget.start(5)) is True
    assert json.loads(seen[-1]["body"]) == {"loaded": 1, "contentLoaded": 1, "ready": True}


def test_infinite_script_stops_at_deadline_and_reaps_process_group():
    require_sandbox()
    processes = []
    popen = runtime.subprocess.Popen

    def capture(*args, **kwargs):
        child = popen(*args, **kwargs)
        processes.append(child)
        return child

    started = time.monotonic()
    with mock.patch.object(runtime.subprocess, "Popen", side_effect=capture):
        assert runtime.run_runtime(payload("<script>while(true){}</script>", 10000),
                                   lambda r: response(), StageBudget.start(.5)) is False
    assert time.monotonic() - started < 2
    assert processes and processes[-1].poll() is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(processes[-1].pid, 0)


def test_cancellation_propagates_and_reaps_child():
    require_sandbox()
    processes = []
    popen = runtime.subprocess.Popen

    def capture(*args, **kwargs):
        child = popen(*args, **kwargs)
        processes.append(child)
        return child

    cancelled = threading.Event()
    timer = threading.Timer(.2, cancelled.set)
    timer.start()
    try:
        with mock.patch.object(runtime.subprocess, "Popen", side_effect=capture), \
             pytest.raises(CancellationRequested):
            runtime.run_runtime(payload("<script>while(true){}</script>", 10000),
                                lambda r: response(), StageBudget.start(4, cancel=cancelled.is_set))
    finally:
        timer.cancel()
    assert processes and processes[-1].poll() is not None
    with pytest.raises(ProcessLookupError):
        os.killpg(processes[-1].pid, 0)


@pytest.mark.parametrize("output", ["not json\n", '{"type":"request","id":1}\n', "x" * (400 * 1024)],
                         ids=["invalid-json", "invalid-shape", "oversized-line"])
def test_malformed_or_oversized_subprocess_protocol_is_bounded(output):
    require_sandbox()
    # Corrupt runner is injected at the launch boundary; OS isolation stays real.
    original = runtime._sandbox_command()
    command = original[:-1] + ["-e", "process.stdin.resume();process.stdout.write(" + json.dumps(output) + ");setInterval(()=>{},1000)"]
    started = time.monotonic()
    with mock.patch.object(runtime, "_sandbox_command", return_value=command):
        assert runtime.run_runtime(payload(""), lambda r: pytest.fail("invalid request bridged"),
                                   StageBudget.start(2)) is False
    assert time.monotonic() - started < 2.5


def test_sandbox_unavailable_fails_fast_without_unisolated_fallback():
    with mock.patch.object(runtime, "_sandbox_command", return_value=None), \
         mock.patch.object(runtime.subprocess, "Popen") as popen:
        assert runtime.run_runtime(payload(""), lambda r: response(), StageBudget.start(2)) is False
    popen.assert_not_called()
