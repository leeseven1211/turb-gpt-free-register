# Optional isolated DOM experiment

This package is independent of `sentinel/sentinel-runner.js`. Install its locked
dependencies with `npm ci --ignore-scripts --no-audit --no-fund` in this directory.
It requires Node >=20 and macOS `/usr/bin/sandbox-exec`. Other platforms return
unsupported; there is deliberately no unisolated fallback.

`core.network.cloudflare_runtime.run_runtime(payload, bridge, budget)` sends the
HTML through anonymous pipes to a one-shot Node process. Its default-deny OS
profile allows reading this runtime's files and system/installed dylib code. It
denies network, user-file contents, writes and child-process creation. The parent
uses a minimal environment, limits protocol messages/bytes and kills/reaps the
whole process group on every exit. The Python policy coordinator owns destination,
method, cookie, redirect and network timeout enforcement; callbacks must respect
the shared budget. HTML and challenge bodies are never written to temporary files.

The focused DOM implementation is original project code, using jsdom 26.1.0
(MIT) and its separately locked dependencies. No code from the attachment's
`cloudflare-ctf` implementation is vendored. Package license notices remain in the
installed dependencies.

Supported offline behavior includes classic inline/external/dynamic scripts,
UTF-8 fetch/XHR requests, binary responses, separate parent/iframe documents,
asynchronous postMessage exchange with source/origin and targetOrigin checks,
and one shared CookieJar with domain/path/secure isolation. HttpOnly cookies are
excluded from input; bridge-observed non-HttpOnly cookies refresh DOM visibility.
`document.cookie` writes stay inside the DOM and do not manufacture transport
cookies. Workers, module scripts, service workers, browser navigation, synchronous
XHR and full browser fingerprint/rendering APIs are unsupported. A completed DOM
experiment is not evidence that a real challenge is solved: the coordinator must
independently verify its single approved anonymous page. No online effectiveness
claim is made from fixtures.
