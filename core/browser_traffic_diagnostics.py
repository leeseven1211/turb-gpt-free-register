# -*- coding: utf-8 -*-
"""可选浏览器资源与 JS 诊断，仅保存有界的脱敏元数据。"""
from __future__ import annotations

import logging
import re
import threading
from urllib.parse import urlsplit

logger = logging.getLogger(__name__)


def _number(value):
    try:
        return max(0, min(2**63 - 1, int(value or 0)))
    except (ValueError, TypeError, OverflowError):
        return 0


def safe_resource_url(value):
    try:
        parsed = urlsplit(str(value or ""))
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return "<非网络资源>"
        path = parsed.path or "/"
        path = re.sub(r"/[^/]*@[^/]*", "/<邮箱>", path)
        path = re.sub(r"/[A-Za-z0-9_-]{24,}(?=/|$)", "/<标识>", path)
        return (parsed.hostname.lower() + path)[:240]
    except (ValueError, TypeError):
        return "<未知资源>"


def _safe_label(value):
    value = str(value or "")
    return safe_resource_url(value if "://" in value else "https://" + value)


def sanitize_diagnostics(value):
    """普通流量表拒绝正文、Header 和逐函数数据，只存固定的诊断摘要。"""
    result = {}
    if isinstance(value.get("resource_details"), list):
        result["resource_details"] = [dict(
            url=_safe_label(row.get("url")),
            resource_type=re.sub(r"[^a-z_]", "", str(row.get("resource_type") or "other").lower())[:30],
            **{key: _number(row.get(key)) for key in ("upload_bytes", "download_bytes", "total_bytes", "http_status")},
            byte_semantics="browser_cdp_observed",
        ) for row in value["resource_details"][:10000] if isinstance(row, dict)]
    coverage = value.get("js_coverage")
    if isinstance(coverage, dict):
        result["js_coverage"] = dict(
            enabled=bool(coverage.get("enabled")),
            **{key: _number(coverage.get(key)) for key in ("target_count", "collected_target_count", "unsupported_target_count")},
            scripts=[dict(url=_safe_label(row.get("url")), function_count=_number(row.get("function_count")),
                          executed_function_count=_number(row.get("executed_function_count")),
                          observed_execution=bool(row.get("observed_execution")))
                     for row in (coverage.get("scripts") or [])[:10000] if isinstance(row, dict)],
            note="未观察到执行仅用于诊断，不能证明资源可安全拦截",
        )
    return result


class BrowserTrafficDiagnostics:
    def __init__(self):
        from config import browser as cfg
        self.detail_enabled = bool(cfg.BROWSER_TRAFFIC_DETAIL_LOG)
        self.coverage_enabled = bool(cfg.BROWSER_JS_COVERAGE_LOG)
        self.detail_limit = max(1, min(10000, _number(cfg.BROWSER_TRAFFIC_DETAIL_MAX_ENTRIES)))
        self.coverage_limit = max(1, min(10000, _number(cfg.BROWSER_JS_COVERAGE_MAX_ENTRIES)))
        self._lock = threading.RLock()
        self.details = []
        self.scripts = []
        self.functions = []
        self.target_count = 0
        self.collected_count = 0
        self.unsupported_count = 0

    def record_resource(self, item, upload, download):
        if not self.detail_enabled or not upload + download:
            return
        if item.get("cache_source") == "local" or item.get("_data_saver_blocked"):
            return
        with self._lock:
            entry = dict(url=safe_resource_url(item.get("url")),
                         resource_type=re.sub(r"[^a-z_]", "", str(item.get("resource_type") or "other").lower())[:30],
                         upload_bytes=upload, download_bytes=download, total_bytes=upload + download,
                         http_status=_number(item.get("status")), byte_semantics="browser_cdp_observed")
            self.details.append(entry)
            # 保留消耗最高的有界明细，零字节和本地回放不进入列表。
            self.details.sort(key=lambda row: row["total_bytes"], reverse=True)
            del self.details[self.detail_limit:]

    def target_started(self):
        with self._lock:
            self.target_count += 1

    def record_coverage(self, payload, *, supported=True):
        if not self.coverage_enabled:
            return
        with self._lock:
            if not supported:
                self.unsupported_count += 1
                return
            self.collected_count += 1
            for script in payload.get("result", []) if isinstance(payload, dict) else []:
                if not isinstance(script, dict) or len(self.scripts) >= self.coverage_limit:
                    continue
                url = safe_resource_url(script.get("url"))
                executed_functions = 0
                function_count = 0
                for function in script.get("functions", []):
                    if not isinstance(function, dict):
                        continue
                    function_count += 1
                    ranges = [(max(0, _number(row.get("startOffset"))), _number(row.get("endOffset")), _number(row.get("count")))
                              for row in function.get("ranges", [])[:100] if isinstance(row, dict)]
                    executed = any(count > 0 for _, _, count in ranges)
                    executed_functions += int(executed)
                    if executed and len(self.functions) < self.coverage_limit:
                        name = str(function.get("functionName") or "<匿名>")
                        if not re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$.: \[\]<>-]{0,100}", name):
                            name = "<匿名>"
                        self.functions.append(dict(url=url, function=name, ranges=ranges,
                                                   call_count=max((row[2] for row in ranges), default=0)))
                self.scripts.append(dict(url=url, function_count=function_count,
                                         executed_function_count=executed_functions,
                                         observed_execution=executed_functions > 0))

    def snapshot(self):
        with self._lock:
            result = {}
            if self.detail_enabled:
                result["resource_details"] = [dict(row) for row in self.details]
            if self.coverage_enabled:
                result["js_coverage"] = dict(enabled=True, target_count=self.target_count,
                                             collected_target_count=self.collected_count,
                                             unsupported_target_count=self.unsupported_count,
                                             scripts=[dict(row) for row in self.scripts],
                                             note="未观察到执行仅用于诊断，不能证明资源可安全拦截")
            return result

    def log(self):
        with self._lock:
            for row in self.details:
                logger.info("[资源流量] url=%s type=%s upload=%s download=%s total=%s（页面可观测口径）",
                            row["url"], row["resource_type"], row["upload_bytes"], row["download_bytes"], row["total_bytes"])
            if self.coverage_enabled:
                logger.info("[JS执行汇总] targets=%s collected=%s unsupported=%s scripts=%s；未观察到执行不能证明可安全拦截",
                            self.target_count, self.collected_count, self.unsupported_count, len(self.scripts))
            for row in self.functions:
                logger.info("[JS执行] url=%s function=%s count=%s ranges=%s",
                            row["url"], row["function"], row["call_count"], row["ranges"])
