"""Normalize only this target round's durable plan/refresh evidence for reports."""
from __future__ import annotations

from collections.abc import Mapping, Sequence

from core.accounts.plans.promotion import normalize_percentage

_TERMINAL = {"success", "partial_success", "failed", "not_executed", "cancelled"}
_KINDS = {"none", "free_trial", "discount", "other_promo"}


def _mapping(value) -> dict:
    return dict(value) if isinstance(value, Mapping) else {}


def _promotions(value) -> list[dict]:
    return [dict(row) for row in value if isinstance(row, Mapping)] if isinstance(value, list) else []


def _fresh(row: Mapping) -> bool:
    return row.get("stale") in (None, False) and row.get("expired") in (None, False)


def _country_complete(result: Mapping) -> bool:
    snapshot = _mapping(result.get("promotion_query_snapshot"))
    if result.get("ok") is not True or snapshot.get("truncated") is not False:
        return False
    rows = _promotions(result.get("account_promotions"))
    for plan in ("go", "plus"):
        items = [row for row in rows if row.get("plan") == plan]
        if not items or any(not _fresh(row) or row.get("kind") not in _KINDS for row in items):
            return False
        if any(row.get("eligible") is not (row.get("kind") != "none") for row in items):
            return False
    return True


def promotion_evidence_complete(result: Mapping) -> bool:
    """Require every requested country to have complete current Go and Plus evidence."""
    countries = result.get("plan_check_countries")
    if not isinstance(countries, list) or not countries:
        return _country_complete(result)
    if (result.get("ok") is not True or result.get("plan_check_partial")
            or result.get("country_success_count") != len(countries)):
        return False
    rows = _promotions(result.get("plan_check_country_results"))
    if len(rows) != len(countries) or {row.get("country") for row in rows} != set(countries):
        return False
    return all(row.get("status") == "success" and _country_complete(_mapping(row.get("result"))) for row in rows)


def _root_runs(runs: Sequence[Mapping]) -> list[dict]:
    return sorted((_mapping(run) for run in runs
                   if run.get("relation") in (None, "owned_root", "owned_continuation")),
                  key=lambda run: (int(run.get("generation") or 0), int(run.get("id") or run.get("run_id") or 0)))


def _offer_groups(rows: Sequence[Mapping]) -> dict[str, set[str]]:
    offers: dict[str, set[str]] = {}
    for row in rows:
        name = str(row.get("plan") or "").strip().lower()
        kind = row.get("kind")
        if not name or len(name) > 64 or not _fresh(row) or row.get("eligible") is not True:
            continue
        if kind not in {"free_trial", "discount", "other_promo"}:
            continue
        if kind == "discount":
            kind = "half_price" if normalize_percentage(row.get("discount_percentage")) == 50 else "other_discount"
        offers.setdefault(name, set()).add(kind)
    return offers


def plan_report_snapshot(result: Mapping) -> dict:
    """Compact facts survive generic run-summary depth and list-length limits."""
    rows = _promotions(result.get("account_promotions"))
    offers = _offer_groups(rows) if result.get("ok") is True else {}
    complete = promotion_evidence_complete(result)
    none = (complete and bool(rows) and not offers
            and all(_fresh(row) and row.get("kind") == "none" and row.get("eligible") is False for row in rows))
    return {"version": 1, "promotion_complete": complete, "at_refresh_observed": True,
            "offers_by_plan": {name: sorted(kinds) for name, kinds in sorted(offers.items())}, "confirmed_none": none}


def _historical_snapshot(summary: Mapping, records) -> dict:
    """The loader supplies the latest response per country from this exact Run."""
    rows = _promotions(records)
    if not rows:
        return {}
    countries = summary.get("plan_check_countries")
    normalized = []
    for record in rows:
        result = dict(record)
        result["promotion_query_snapshot"] = {"truncated": _mapping(record.get("promotion_query_snapshot")).get("truncated", record.get("truncated"))}
        normalized.append({"country": record.get("country") or "", "status": "success" if record.get("ok") is True else "failed", "result": result})
    if isinstance(countries, list) and countries:
        expected = set(countries)
        if {row["country"] for row in normalized} != expected:
            return {}
        source = {"ok": summary.get("ok"), "plan_check_countries": countries,
                  "country_success_count": sum(row["status"] == "success" for row in normalized),
                  "plan_check_country_results": normalized,
                  "account_promotions": [{**promotion, "country": row["country"]}
                      for row in normalized if row["status"] == "success"
                      for promotion in _promotions(row["result"].get("account_promotions"))]}
    else:
        if len(normalized) != 1:
            return {}
        source = normalized[0]["result"]
    return plan_report_snapshot(source)


def normalize_plan_report_evidence(runs: Sequence[Mapping], *, state: str, projected_result: Mapping) -> dict:
    """No account snapshots, unrelated runs, old projections or free-text guesses."""
    roots = _root_runs(runs)
    run = roots[-1] if roots else {}
    summary = _mapping(run.get("result_summary"))
    confirmed_query = state in {"success", "partial_success"} and summary.get("ok") is True
    plan = str(summary.get("current_plan_type") or "").strip().lower() if confirmed_query else ""
    # Unsupported/novel names remain visible as bounded text; never include raw response objects.
    plan = plan if plan and len(plan) <= 64 else None
    rows = _promotions(summary.get("account_promotions")) if confirmed_query else []
    meta = _mapping(summary.get("plan_report_evidence"))
    if confirmed_query and not meta:
        meta = _historical_snapshot(summary, run.get("promotion_query_records"))
    offers = _offer_groups(rows)
    compact = meta.get("version") == 1 and isinstance(meta.get("offers_by_plan"), Mapping)
    if confirmed_query and compact:
        offers = {name: {kind for kind in kinds if isinstance(kind, str)} & {"free_trial", "half_price", "other_discount", "other_promo"}
                  for name, kinds in meta["offers_by_plan"].items()
                  if isinstance(name, str) and 0 < len(name) <= 64 and isinstance(kinds, list)}
        offers = {name: kinds for name, kinds in offers.items() if kinds}
    if compact:
        none_evidence = meta.get("confirmed_none") is True and meta.get("promotion_complete") is True
    else:
        none_evidence = (not summary.get("plan_check_countries") and _country_complete(summary)
                         and all(_fresh(row) and row.get("kind") == "none" and row.get("eligible") is False for row in rows))
    confirmed_none = confirmed_query and not offers and none_evidence
    at = dict.fromkeys(("expired", "invalid", "missing_token", "attempted", "succeeded", "failed",
                        "pending", "not_needed", "unknown", "not_executed"), False)
    witnessed = []
    observed = False
    for owned in roots:
        own_summary = _mapping(owned.get("result_summary"))
        data = _mapping(owned.get("data"))
        run_id = owned.get("id") or owned.get("run_id")
        candidates = [_mapping(data.get("plan_auto_refresh_at")), _mapping(own_summary.get("auto_refresh_at"))]
        refresh = next((item for item in candidates if item and
                        (item.get("run_id") is None or str(item["run_id"]) == str(run_id))), {})
        if refresh.get("attempted") is True:
            witnessed.append(refresh)
        observed |= (_mapping(own_summary.get("plan_report_evidence")).get("at_refresh_observed") is True
                     or "auto_refresh_at" in own_summary and own_summary["auto_refresh_at"] in (None, {}))
        failures = own_summary.get("country_failures")
        codes = {item.get("code") or item.get("error_code") for item in failures if isinstance(item, Mapping)} if isinstance(failures, list) else set()
        if own_summary.get("http_status") == 401:
            codes.add("token_http_401")
        codes.add(own_summary.get("plan_at_issue"))
        codes.add(owned.get("error_code"))
        codes.add(own_summary.get("cause_code"))
        at["expired"] |= "token_local_expired" in codes
        at["invalid"] |= "token_http_401" in codes
        at["missing_token"] |= "token_missing" in codes
    for item in witnessed:
        at["expired"] |= item.get("reason") == "token_local_expired"
        at["invalid"] |= item.get("reason") == "token_http_401"
        at["missing_token"] |= item.get("reason") == "token_missing"
    if witnessed:
        at["attempted"] = True
        latest = witnessed[-1]
        at["succeeded"] = latest.get("ok") is True and latest.get("status") == "success" and not latest.get("reconcile_required")
        at["failed"] = latest.get("ok") is False and latest.get("status") == "failed"
        at["pending"] = not at["succeeded"] and not at["failed"] and state not in _TERMINAL
        at["unknown"] = not any(at[key] for key in ("succeeded", "failed", "pending"))
    elif not roots or (state in {"not_executed", "cancelled"} and not any(row.get("started_at") for row in roots)):
        at["not_executed"] = True
    elif state not in _TERMINAL:
        at["unknown"] = True
    elif observed:
        at["not_needed"] = True
    else:
        at["unknown"] = True
    return {"plan": plan, "offer": {"has_offer": bool(offers), "confirmed_none": confirmed_none,
            "by_plan": [{"plan": name, "kinds": sorted(kinds)} for name, kinds in sorted(offers.items())]}, "at_refresh": at}
