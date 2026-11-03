#!/usr/bin/env python3
"""Explicit anonymous probe; never reads account credentials or task queues."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", action="store_true", help="显式执行一次匿名登录页探针；默认不联网")
    parser.add_argument("--transport", choices=("curl", "wreq"), default="curl")
    parser.add_argument("--proxy", default="", help="显式测试代理；留空直连，不读取业务代理池")
    parser.add_argument("--timeout", type=float, default=12.0)
    args = parser.parse_args(argv)
    if not 0.01 <= args.timeout <= 12:
        parser.error("timeout must be between 0.01 and 12 seconds")
    if not args.run:
        print(json.dumps({"status": "not_run", "reason": "explicit --run required"}))
        return 0

    from core.auth.state_machine import StageBudget
    from core.network.cloudflare import ANONYMOUS_LOGIN_URL, solve_challenge
    from core.network.cloudflare_adapters import BrowserChallengeTransport, WreqChallengeTransport

    budget = StageBudget.start(args.timeout)
    close = None
    try:
        if args.transport == "curl":
            from core.auth.protocol.session import BrowserSession
            owner = BrowserSession(proxy=args.proxy, detect_exit_geo=False)
            close = owner.close
            transport = BrowserChallengeTransport(owner)
            headers = owner.get_chatgpt_navigate_headers(referer="")
            profile = dict(owner.browser_profile)
        else:
            from core.registration.protocol_oss_2.upstream.http_client_wreq import create_http_session
            ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/152.0.0.0 Safari/537.36"
            raw = create_http_session(proxy=args.proxy, impersonate="chrome152", user_agent=ua)
            close = raw.close
            transport = WreqChallengeTransport(raw, {"capture": None})
            headers = {"user-agent": ua, "accept": "text/html", "accept-language": "en-US,en;q=0.9",
                       "sec-ch-ua": '"Chromium";v="152", "Google Chrome";v="152", "Not.A/Brand";v="99"',
                       "sec-ch-ua-platform": '"macOS"', "sec-ch-ua-mobile": "?0",
                       "sec-fetch-site": "none", "sec-fetch-dest": "document", "sec-fetch-mode": "navigate"}
            profile = {key.replace("-", "_"): value for key, value in headers.items()}
        response = transport.request("GET", ANONYMOUS_LOGIN_URL, headers=headers, stream=True,
                                     allow_redirects=False, timeout=budget.require("匿名预检"))
        try:
            size = 0
            for chunk in response.iter_content(chunk_size=16384):
                budget.require("匿名预检正文")
                size += len(chunk)
                if size > 1024 * 1024:
                    raise ValueError("probe response exceeds limit")
        finally:
            response.close()
        result = solve_challenge(transport, response, url=ANONYMOUS_LOGIN_URL, headers=headers,
                                 profile=profile, budget=budget)
        print(json.dumps({"status": result.status, "reason": result.reason,
                          "http_status": response.status_code, "request_count": result.request_count}, ensure_ascii=False))
        healthy_unchanged = result.status == "unchanged" and 200 <= int(response.status_code) < 300
        return 0 if result.status == "verified" or healthy_unchanged else 2
    except Exception as exc:
        # URLs/proxy/exception text may contain private data; only emit class.
        print(json.dumps({"status": "not_verified", "reason": type(exc).__name__}))
        return 2
    finally:
        if close is not None:
            close()


if __name__ == "__main__":
    raise SystemExit(main())
