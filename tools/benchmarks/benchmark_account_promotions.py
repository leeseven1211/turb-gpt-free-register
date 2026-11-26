#!/usr/bin/env python3
"""在隔离 PostgreSQL 中比较优惠 JSON 谓词与独立投影查询。

脚本默认启动一个经过 ``build_isolated_environment`` 清洗的子进程。正式采样
只应在没有其他测试或构建运行时执行；脚本本身不访问远端服务，也不会读取
项目 ``.env``。
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import uuid
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_BENCHMARK_SCHEMA_PREFIX = "test_promotion_bench_"
_DEFAULT_DATABASE = "turb_test"
_DEFAULT_JSON_BYTES = 8192
_MIN_JSON_BYTES = 1024


@dataclass(frozen=True)
class OfferDefinition:
    """一个合成活动；同一活动可在多个国家重复出现。"""

    name: str
    plan: str
    kind: str
    percentage: int
    periods: int
    period: str = "month"

    def as_record(self, country: str) -> dict[str, Any]:
        return {
            "plan": self.plan,
            "kind": self.kind,
            "eligible": True,
            "country": country,
            "campaign_id": f"synthetic-{self.name}",
            "title": f"合成 {self.name}",
            "discount_percentage": self.percentage,
            "duration_num_periods": self.periods,
            "duration_period": self.period,
        }


@dataclass(frozen=True)
class Scenario:
    name: str
    values: tuple[str, ...]
    old_values: tuple[str, ...] | None = None
    compatibility_required: bool = True


def synthetic_offer_definitions() -> tuple[OfferDefinition, ...]:
    """返回九个真实优惠记录，不把动态 facet 数量硬编码成九。"""
    return (
        OfferDefinition("team_free_1m", "team", "free_trial", 100, 1),
        OfferDefinition("go_free_1m", "go", "free_trial", 100, 1),
        OfferDefinition("go_half_1m", "go", "discount", 50, 1),
        OfferDefinition("go_half_2m", "go", "discount", 50, 2),
        OfferDefinition("go_half_3m", "go", "discount", 50, 3),
        OfferDefinition("plus_free_1m", "plus", "free_trial", 100, 1),
        OfferDefinition("plus_half_1m", "plus", "discount", 50, 1),
        OfferDefinition("plus_half_2m", "plus", "discount", 50, 2),
        OfferDefinition("plus_half_3m", "plus", "discount", 50, 3),
    )


def synthetic_expected_offer_names(
    definitions: Sequence[OfferDefinition] | None = None,
) -> tuple[str, ...]:
    """返回合成输入名，便于纯函数测试和报告记录。"""
    return tuple(item.name for item in definitions or synthetic_offer_definitions())


def _numeric(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _percentage_code(value: Any) -> str:
    percentage = _numeric(value)
    if percentage == 100:
        return "100"
    if percentage == 50:
        return "50"
    return "other"


def _periods_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if str(parsed) == str(value).strip() else None


def legacy_offer_codes(
    json_offers: Sequence[dict[str, Any]] | None,
    *,
    legacy_kind: str | None = None,
    legacy_percentage: Any = None,
    legacy_periods: Any = None,
    legacy_period: str | None = None,
) -> list[str]:
    """按旧 JSON/Plus 列语义返回筛选代码。

    ``None`` 表示 ``account_promotions`` 字段缺失，才允许落到旧 Plus 列；
    显式空数组仍表示已确认没有优惠。
    """
    if json_offers is not None:
        result: list[str] = []
        for offer in json_offers:
            if not isinstance(offer, dict) or offer.get("eligible") is not True:
                continue
            plan = str(offer.get("plan") or "").strip().lower()
            kind = str(offer.get("kind") or "").strip().lower()
            if plan == "team":
                if kind in {"free_trial", "discount", "other_promo"}:
                    result.append("team_eligible")
                continue
            if plan not in {"plus", "go"}:
                continue
            percentage = _numeric(offer.get("discount_percentage"))
            if percentage is None or not 0 < percentage <= 100:
                continue
            result.append(f"{plan}_{_percentage_code(percentage)}")
            periods = _periods_int(offer.get("duration_num_periods"))
            period = str(offer.get("duration_period") or "").strip().lower()
            if (
                plan == "plus"
                and percentage == 50
                and periods in {1, 2, 3}
                and period in {"month", "months", "月"}
            ):
                result.append(f"plus_50_{periods}m")
        return list(dict.fromkeys(result))

    kind = str(legacy_kind or "").strip().lower()
    if kind not in {"free_trial", "discount", "other_promo"}:
        return []
    percentage = _numeric(legacy_percentage)
    if percentage is None or not 0 < percentage <= 100:
        return []
    result = [f"plus_{_percentage_code(percentage)}"]
    periods = _periods_int(legacy_periods)
    period = str(legacy_period or "").strip().lower()
    if percentage == 50 and periods in {1, 2, 3} and period in {"month", "months", "月"}:
        result.append(f"plus_50_{periods}m")
    return result


def percentile(values: Sequence[float], fraction: float) -> float:
    if not values:
        raise ValueError("没有可统计的样本")
    ordered = sorted(float(value) for value in values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * fraction / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def summarize_samples(samples: Sequence[dict[str, Any]]) -> dict[str, Any]:
    """汇总有效样本；少于 30 个时明确不生成 P95 字段。"""
    if not samples:
        return {"samples": 0}
    values = [float(item["milliseconds"]) for item in samples]
    summary: dict[str, Any] = {
        "samples": len(values),
        "p50_ms": round(percentile(values, 50), 3),
        "max_ms": round(max(values), 3),
    }
    if len(values) >= 30:
        summary["p95_ms"] = round(percentile(values, 95), 3)
    return summary


def _git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


def _json_digest(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _random_payload(seed: int, size: int) -> str:
    """生成可复现、低重复度的 ASCII 伪随机字符串，避免压缩造成假提速。"""
    chunks: list[str] = []
    counter = 0
    while sum(len(item) for item in chunks) < size:
        chunks.append(hashlib.sha256(f"promotion-benchmark:{seed}:{counter}".encode()).hexdigest())
        counter += 1
    return "".join(chunks)[:size]


def _offer_records(index: int, definitions: Sequence[OfferDefinition]) -> list[dict[str, Any]] | None:
    """分布式构造单国、多选、多国重复和无优惠账号。"""
    if index % 19 == 0:
        return None
    if index % 23 == 0:
        return []
    records: list[dict[str, Any]] = []
    primary = definitions[index % len(definitions)]
    records.append(primary.as_record("JP" if index % 2 else "US"))
    if index % 7 == 0:
        records.append(primary.as_record("VN"))
    if index % 11 == 0:
        secondary = definitions[(index + 3) % len(definitions)]
        records.append(secondary.as_record("US"))
    if index % 17 == 0:
        secondary = definitions[(index + 5) % len(definitions)]
        records.append(secondary.as_record("JP"))
    return records


def _legacy_columns(
    index: int,
    records_for_account: Sequence[dict[str, Any]] | None,
) -> dict[str, Any]:
    plus = next(
        (
            item
            for item in records_for_account or ()
            if str(item.get("plan") or "").strip().lower() == "plus"
        ),
        None,
    )
    if plus is None and index % 19 != 0:
        return {
            "plus_promo_kind": "none",
            "plus_promo_eligible": False,
            "plus_discount_eligible": False,
        }
    if plus is not None:
        return {
            "plus_promo_kind": str(plus.get("kind") or "unknown"),
            "plus_promo_eligible": True,
            "plus_discount_eligible": str(plus.get("kind") or "").lower()
            in {"discount", "other_discount"},
            "plus_promo_discount_percentage": plus.get("discount_percentage"),
            "plus_promo_duration_num_periods": plus.get("duration_num_periods"),
            "plus_promo_duration_period": plus.get("duration_period"),
        }
    return {
        "plus_promo_kind": "discount",
        "plus_promo_eligible": True,
        "plus_discount_eligible": True,
        "plus_promo_discount_percentage": 50,
        "plus_promo_duration_num_periods": 2,
        "plus_promo_duration_period": "month",
    }


def _old_offer_sql(alias: str = "a") -> str:
    """f298c9c8 的旧 JSON/legacy Plus 细分类等价表达式。"""
    offers = f"{alias}.data->'account_promotions'"
    percentage = "offer->'discount_percentage'"
    period = "lower(COALESCE(offer->>'duration_period', ''))"
    periods = "COALESCE(offer->>'duration_num_periods', '')"
    legacy_period = f"lower(COALESCE({alias}.plus_promo_duration_period, ''))"
    kind = f"""CASE
        WHEN LOWER(COALESCE({alias}.plus_promo_kind, '')) IN
             ('free_trial', 'discount', 'other_promo', 'none', 'unknown')
          THEN LOWER({alias}.plus_promo_kind)
        WHEN {alias}.plus_discount_eligible IS TRUE THEN 'discount'
        WHEN {alias}.plus_promo_eligible IS TRUE OR {alias}.plus_trial_eligible IS TRUE
          THEN 'unknown'
        ELSE 'none'
    END"""
    return f"""CASE WHEN jsonb_typeof({offers}) = 'array' THEN ARRAY(
        SELECT code FROM jsonb_array_elements({offers}) AS offer
        CROSS JOIN LATERAL (VALUES
            (CASE WHEN offer->>'plan' = 'team' THEN 'team_eligible'
                  ELSE (offer->>'plan') || '_' || CASE {percentage}
                    WHEN '100'::jsonb THEN '100'
                    WHEN '50'::jsonb THEN '50'
                    ELSE 'other' END END),
            (CASE WHEN offer->>'plan' = 'plus' AND {percentage} = '50'::jsonb
                   AND {period} IN ('month', 'months', '月')
                   AND {periods} ~ '^[123]$'
                  THEN 'plus_50_' || {periods} || 'm' END)
        ) AS v(code)
        WHERE offer->'eligible' = 'true'::jsonb
          AND ((offer->>'plan' IN ('plus', 'go')
                AND jsonb_typeof({percentage}) = 'number'
                AND {percentage} > '0'::jsonb AND {percentage} <= '100'::jsonb)
               OR (offer->>'plan' = 'team'
                   AND offer->>'kind' IN ('free_trial', 'discount', 'other_promo')))
          AND v.code IS NOT NULL
    ) WHEN {kind} IN ('free_trial', 'discount', 'other_promo')
         AND {alias}.plus_promo_discount_percentage > 0
         AND {alias}.plus_promo_discount_percentage <= 100
    THEN ARRAY_REMOVE(ARRAY[
        CASE {alias}.plus_promo_discount_percentage
            WHEN 100 THEN 'plus_100'
            WHEN 50 THEN 'plus_50'
            ELSE 'plus_other' END,
        CASE WHEN {alias}.plus_promo_discount_percentage = 50
               AND {legacy_period} IN ('month', 'months', '月')
               AND {alias}.plus_promo_duration_num_periods IN (1, 2, 3)
              THEN 'plus_50_' || {alias}.plus_promo_duration_num_periods::text || 'm' END
    ], NULL)
    ELSE ARRAY[]::text[] END"""


def _expanded_promotion_values(values: Sequence[str]) -> list[str]:
    aliases = {
        "eligible": ["free_trial"],
        "ineligible": ["none"],
        "discount": ["half_price", "other_discount"],
    }
    return list(
        dict.fromkeys(item for value in values for item in aliases.get(value, [value]))
    )


def _old_offer_filter_values(values: Sequence[str]) -> list[str]:
    category_values = {
        "free_trial",
        "half_price",
        "other_discount",
        "none",
        "unknown",
        "pending",
        "failed",
        "not_applicable",
    }
    return [
        value for value in _expanded_promotion_values(values)
        if value not in category_values
    ]


def _promotion_filter_sql(
    values: Sequence[str],
    *,
    alias: str = "a",
    offer_expression: str | None = None,
    promotion_expression: str | None = None,
) -> tuple[str, list[Any]]:
    if not values:
        return "TRUE", []
    expanded = _expanded_promotion_values(values)
    category_values = {
        "free_trial",
        "half_price",
        "other_discount",
        "none",
        "unknown",
        "pending",
        "failed",
        "not_applicable",
    }
    categories = [value for value in expanded if value in category_values]
    offer_codes = [value for value in expanded if value not in category_values]
    parts: list[str] = []
    params: list[Any] = []
    if categories:
        category_value = promotion_expression or f"""CASE
                WHEN LOWER(COALESCE({alias}.plan_check_status, '')) IN ('queued', 'running')
                  THEN 'pending'
                ELSE {alias}.account_promotion_value
            END"""
        parts.append(f"({category_value} = ANY(%s))")
        params.append(categories)
    if offer_codes:
        parts.append(
            f"({offer_expression or _old_offer_sql(alias)} && %s::text[])"
        )
        params.append(offer_codes)
    return f"({' OR '.join(parts)})", params


def _make_scenarios(
    expected_codes: Sequence[str], *, names: Sequence[str] | None = None
) -> tuple[Scenario, ...]:
    definitions = synthetic_offer_definitions()
    old_by_key = {
        _offer_key(definition): (
            "plus_50" if definition.plan == "plus" and definition.percentage == 50
            else f"{definition.plan}_{_percentage_code(definition.percentage)}"
        )
        for definition in definitions
    }
    for definition in definitions:
        key = _offer_key(definition)
        if definition.plan == "plus" and definition.percentage == 50:
            old_by_key[key] = f"plus_50_{definition.periods}m"
        elif definition.plan == "team":
            old_by_key[key] = "team_eligible"

    scenarios = [Scenario("无筛选", ())]
    for value in expected_codes:
        definition = next(
            item for item in definitions if _offer_key(item) == value
        )
        old_value = old_by_key[value]
        scenarios.append(
            Scenario(
                f"具体优惠:{value}",
                (value,),
                (old_value,),
                compatibility_required=not (
                    definition.plan == "go" and definition.percentage == 50
                ),
            )
        )
    scenarios.extend(
        (
            Scenario("Team", ("team_eligible",)),
            Scenario(
                "多选:Team+Plus",
                ("team_eligible", expected_codes[6]),
                ("team_eligible", "plus_50_1m"),
            ),
            Scenario(
                "多选:Go+Plus",
                ("go_100", expected_codes[7]),
                ("go_100", "plus_50_2m"),
            ),
            Scenario("兼容:free_trial", ("free_trial",)),
            Scenario("兼容:half_price", ("half_price",)),
        )
    )
    seen: set[tuple[str, ...]] = set()
    result: list[Scenario] = []
    for scenario in scenarios:
        if scenario.values not in seen:
            seen.add(scenario.values)
            result.append(scenario)
    if names is None:
        return tuple(result)
    selected = set(names)
    unknown = selected.difference(scenario.name for scenario in result)
    if unknown:
        raise ValueError(f"未知基准场景：{', '.join(sorted(unknown))}")
    return tuple(scenario for scenario in result if scenario.name in selected)


def _normalize_facets(payload: Any) -> dict[str, int]:
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("promotion", [])
    if isinstance(raw, dict):
        raw = raw.get("values", [])
    result: dict[str, int] = {}
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            value = str(item.get("value") or "").strip().lower()
            count = int(item.get("count") or 0)
        else:
            value, count = str(item).strip().lower(), 0
        if value:
            result[value] = count
    return result


def _normalize_all_facets(payload: Any) -> dict[str, dict[str, int]]:
    if not isinstance(payload, dict):
        return {}
    result: dict[str, dict[str, int]] = {}
    for facet, rows in payload.items():
        values: dict[str, int] = {}
        for item in rows if isinstance(rows, list) else []:
            if not isinstance(item, dict):
                continue
            value = str(item.get("value") or "").strip().lower()
            if value:
                values[value] = int(item.get("count") or 0)
        result[str(facet)] = values
    return result


def _offer_key(definition: OfferDefinition) -> str:
    from core.storage.accounts.promotion_offers import offer_key

    return str(
        offer_key(
            definition.plan,
            definition.kind,
            definition.percentage,
            definition.periods,
            definition.period,
        )
    )


def synthetic_offer_truth(
    accounts: int,
    definitions: Sequence[OfferDefinition] | None = None,
) -> dict[str, set[int]]:
    """从合成输入本身计算每个动态优惠应命中的账号序号。"""
    if accounts < 1:
        raise ValueError("合成账号数必须为正整数")
    definitions = tuple(definitions or synthetic_offer_definitions())
    truth = {_offer_key(definition): set() for definition in definitions}
    by_record = {
        (
            definition.plan,
            definition.kind,
            definition.percentage,
            definition.periods,
            definition.period,
        ): _offer_key(definition)
        for definition in definitions
    }
    for index in range(1, accounts + 1):
        records = _offer_records(index, definitions)
        for record in records or ():
            key = by_record.get(
                (
                    str(record.get("plan") or ""),
                    str(record.get("kind") or ""),
                    int(record.get("discount_percentage") or 0),
                    int(record.get("duration_num_periods") or 0),
                    str(record.get("duration_period") or ""),
                )
            )
            if key:
                truth[key].add(index)
        if records is None:
            legacy = _legacy_columns(index, records)
            legacy_key = by_record.get(
                (
                    "plus",
                    str(legacy.get("plus_promo_kind") or ""),
                    int(legacy.get("plus_promo_discount_percentage") or 0),
                    int(legacy.get("plus_promo_duration_num_periods") or 0),
                    str(legacy.get("plus_promo_duration_period") or ""),
                )
            )
            if legacy_key:
                truth[legacy_key].add(index)
    return truth


def map_account_ids_to_ordinals(
    account_ids: Iterable[int],
    id_to_ordinal: Mapping[int, int],
) -> set[int]:
    """把数据库 ID 映射为合成序号，不假设 ID 连续或从 1 开始。"""
    return {
        int(id_to_ordinal[account_id])
        for account_id in account_ids
        if account_id in id_to_ordinal
    }


def validate_dynamic_facet_truth(
    promotion_counts: Mapping[str, int],
    expected_truth: Mapping[str, set[int]],
) -> bool:
    """严格校验动态 facet 的完整 key 集合和每个 key 的精确账号数。"""
    expected_keys = set(expected_truth)
    actual_counts = {
        key: int(value)
        for key, value in promotion_counts.items()
        if str(key).startswith("offer_v1_")
    }
    if set(actual_counts) != expected_keys:
        raise AssertionError(
            f"动态 facet key 集合不等价: missing={sorted(expected_keys - set(actual_counts))}, "
            f"extra={sorted(set(actual_counts) - expected_keys)}"
        )
    wrong = {
        key: (actual_counts[key], len(expected_truth[key]))
        for key in expected_keys
        if actual_counts[key] != len(expected_truth[key])
    }
    if wrong:
        raise AssertionError(f"动态 facet count 不等价: {wrong}")
    return True


def _expected_codes(definitions: Sequence[OfferDefinition]) -> tuple[str, ...]:
    """从 Task 1 的规范化 key 反查动态 facet，避免复制摘要算法。"""
    keys = [_offer_key(item) for item in definitions]
    return tuple(dict.fromkeys(keys))


def _spec(values: Sequence[str]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "entity": "account",
        "archived": "0",
        "plan": [],
        "q": "",
        "date_from": "",
        "date_to": "",
        "filters": {"promotion": list(values)},
        "order": [{"field": "id", "direction": "desc"}],
        "limit": 100000,
    }


def _require_isolated_environment() -> tuple[str, str]:
    from tools.test_isolated import parse_conninfo, validate_test_database_url

    database_url = str(os.environ.get("DATABASE_URL") or "")
    label = validate_test_database_url(database_url)
    conninfo = parse_conninfo(database_url)
    if os.environ.get("PGSERVICE") or os.environ.get("PGSERVICEFILE"):
        raise RuntimeError("基准拒绝通过 PGSERVICE/PGSERVICEFILE 选择连接")
    if conninfo.get("service") or conninfo.get("servicefile"):
        raise RuntimeError("基准拒绝通过 DSN service/servicefile 选择连接")
    database = str(conninfo.get("dbname") or "")
    if database != _DEFAULT_DATABASE:
        raise RuntimeError("本基准仅允许 turb_test 数据库")
    for hostaddr in (
        str(conninfo.get("hostaddr") or "").strip(),
        str(os.environ.get("PGHOSTADDR") or "").strip(),
    ):
        if hostaddr and hostaddr not in {"127.0.0.1", "::1", "localhost"}:
            raise RuntimeError("本基准拒绝非 loopback hostaddr")
    schema = str(os.environ.get("TURB_DB_SCHEMA") or "")
    if not schema.startswith(_BENCHMARK_SCHEMA_PREFIX):
        raise RuntimeError("基准必须使用自行生成的 test_promotion_bench_ schema")
    if os.environ.get("TURB_ALLOW_PRODUCTION_DB") != "0":
        raise RuntimeError("基准禁止生产库放行")
    if os.environ.get("PYTHON_DOTENV_DISABLED") != "1":
        raise RuntimeError("基准必须禁用 dotenv")
    return label, schema


def _assert_fresh_schema(schema: str) -> None:
    from core.storage import postgres

    if not schema.startswith(_BENCHMARK_SCHEMA_PREFIX):
        raise RuntimeError("拒绝使用非本基准生成的 schema")
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)",
            (schema,),
        )
        if cur.fetchone()[0]:
            raise RuntimeError("基准 schema 已存在，拒绝复用或覆盖")


def _qualified(postgres: Any, name: str) -> str:
    return postgres.qualified(name)


def _seed_accounts(accounts: int, json_bytes: int, definitions: Sequence[OfferDefinition]) -> dict[str, Any]:
    from core.storage import postgres, records

    records.init()
    from core.storage.accounts import promotion_offers

    with postgres.connect() as conn:
        promotion_offers.ensure_schema(conn)
    table = _qualified(postgres, records.ACCOUNTS.name)
    rows_written = 0
    logical_total = 0
    logical_min: int | None = None
    logical_max = 0
    batch_size = 500
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT pg_get_serial_sequence(%s, 'id')",
            (f"{postgres.schema_name()}.{records.ACCOUNTS.name}",),
        )
        sequence = cur.fetchone()[0]
        if not sequence:
            raise RuntimeError("找不到 registered_accounts.id 序列")
        # 让 smoke 明确覆盖数据库 ID 不从 1 开始时的 ordinal 映射。
        cur.execute("SELECT setval(%s::regclass, %s, TRUE)", (sequence, 1000))
        for start in range(1, accounts + 1, batch_size):
            batch: list[tuple[Any, ...]] = []
            for index in range(start, min(accounts + 1, start + batch_size)):
                records_for_account = _offer_records(index, definitions)
                legacy = _legacy_columns(index, records_for_account)
                data: dict[str, Any] = {
                    "synthetic": True,
                    "account_ordinal": index,
                    "account_promotions": records_for_account,
                    "extra_json": _random_payload(index, max(256, json_bytes - 256)),
                }
                if records_for_account is None:
                    data.pop("account_promotions")
                data_json = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
                logical_length = len(data_json.encode("utf-8"))
                logical_total += logical_length
                logical_min = logical_length if logical_min is None else min(logical_min, logical_length)
                logical_max = max(logical_max, logical_length)
                batch.append(
                    (
                        f"promotion-benchmark-{index}@example.test",
                        "2026-11-26T00:00:00",
                        "2026-11-26T00:00:00",
                        False,
                        "synthetic",
                        "free",
                        "success",
                        True,
                        legacy.get("plus_promo_kind"),
                        legacy.get("plus_promo_eligible"),
                        legacy.get("plus_discount_eligible"),
                        legacy.get("plus_promo_discount_percentage"),
                        legacy.get("plus_promo_duration_num_periods"),
                        legacy.get("plus_promo_duration_period"),
                        data_json,
                    )
                )
            cur.executemany(
                f"""INSERT INTO {table}
                    (email,created_at,updated_at,archived,email_source,current_plan_type,
                     plan_check_status,plan_check_ok,plus_promo_kind,plus_promo_eligible,
                     plus_discount_eligible,plus_promo_discount_percentage,
                     plus_promo_duration_num_periods,plus_promo_duration_period,data)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                batch,
            )
            rows_written += len(batch)
            if rows_written == accounts or rows_written % 10000 == 0:
                print(json.dumps({"合成账号": rows_written}, ensure_ascii=False), flush=True)
        cur.execute(f"ANALYZE {table}")
        cur.execute(
            f"ANALYZE {postgres.qualified('account_promotion_offers')}"
        )
        cur.execute(
            f"SELECT COUNT(*) AS accounts, COUNT(*) FILTER (WHERE data ? 'account_promotions') AS with_json "
            f"FROM {table}"
        )
        counts = cur.fetchone()
        cur.execute(f"SELECT MIN(id), MAX(id) FROM {table}")
        id_min, id_max = cur.fetchone()
        if id_min != 1001 or id_max != 1000 + rows_written:
            raise RuntimeError(
                f"合成账号 ID 未按 smoke 起点生成: min={id_min}, max={id_max}"
            )
    return {
        "rows_written": rows_written,
        "id_range": {"min": int(id_min), "max": int(id_max)},
        "table_counts": {"accounts": int(counts[0]), "with_json": int(counts[1])},
        "json_logical_bytes": {
            "min": logical_min or 0,
            "max": logical_max,
            "average": round(logical_total / rows_written, 2) if rows_written else 0,
            "total": logical_total,
        },
    }


def _relation_sizes(postgres: Any, relation: str) -> dict[str, Any]:
    qualified = _qualified(postgres, relation)
    schema = postgres.schema_name()
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(
            """SELECT c.reltoastrelid::regclass::text, pg_relation_size(c.oid),
                      pg_total_relation_size(c.oid), pg_indexes_size(c.oid)
               FROM pg_class c
               JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname=%s AND c.relname=%s""",
            (schema, relation),
        )
        row = cur.fetchone()
        if not row:
            raise RuntimeError(f"找不到基准表 {qualified}")
        toast_name, relation_bytes, total_bytes, index_bytes = row
        toast_bytes = 0
        if toast_name:
            cur.execute("SELECT pg_total_relation_size(%s::regclass)", (toast_name,))
            toast_bytes = int(cur.fetchone()[0] or 0)
    return {
        "relation": qualified,
        "relation_bytes": int(relation_bytes),
        "total_bytes": int(total_bytes),
        "index_bytes": int(index_bytes),
        "toast_relation": toast_name,
        "toast_total_bytes": toast_bytes,
    }


def _old_ids(values: Sequence[str]) -> list[int]:
    from core.storage import postgres, records

    table = _qualified(postgres, records.ACCOUNTS.name)
    predicate, params = _promotion_filter_sql(values)
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT a.id FROM {table} a WHERE a.archived IS FALSE AND {predicate} ORDER BY a.id", params)
        return [int(row[0]) for row in cur.fetchall()]


def _new_query_sql(values: Sequence[str]) -> tuple[str, list[Any]]:
    from core.accounts.query import compile_query

    return compile_query(_spec(values), strict=False)


def _new_ids(values: Sequence[str]) -> list[int]:
    from core.storage import postgres, records

    table = _qualified(postgres, records.ACCOUNTS.name)
    where, params = _new_query_sql(values)
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT a.id FROM {table} a WHERE {where} ORDER BY a.id", params)
        return [int(row[0]) for row in cur.fetchall()]


def _old_count(values: Sequence[str]) -> int:
    from core.storage import postgres, records

    table = _qualified(postgres, records.ACCOUNTS.name)
    predicate, params = _promotion_filter_sql(values)
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table} a WHERE a.archived IS FALSE AND {predicate}", params)
        return int(cur.fetchone()[0])


def _new_count(values: Sequence[str]) -> int:
    from core.storage import admin_repository

    return int(admin_repository.account_query_count(_spec(values)))


def _old_facets_query(values: Sequence[str] = ()) -> tuple[str, list[Any]]:
    from core.storage import admin_repository, postgres, records

    table = _qualified(postgres, records.ACCOUNTS.name)
    expressions = admin_repository._account_facet_expressions()
    base_expressions = ", ".join(
        f"{expression} AS {key}" for key, expression in expressions.items()
    )
    facet_values = ", ".join(
        f"('{key}', b.{key})" for key in expressions
    )
    old_offer_values = _old_offer_filter_values(values)
    predicate, params = _promotion_filter_sql(
        values,
        alias="b",
        offer_expression="b.promotion_offers" if old_offer_values else None,
        promotion_expression="b.promotion",
    )
    offer_projection = (
        f", {_old_offer_sql('a')} AS promotion_offers"
        if old_offer_values
        else ""
    )
    # 复刻 f298c9c8 的 account_query_facets 形状：只有旧 offer 值筛选
    # 才物化 JSON 优惠数组；无筛选或纯 legacy 分类筛选不读取 JSON。
    return (
        f"""WITH base AS MATERIALIZED (
                SELECT {base_expressions}{offer_projection}
                  FROM {table} a
                 WHERE a.archived IS FALSE
            )
            SELECT f.facet, f.value, COUNT(*) AS count
              FROM base b
         CROSS JOIN LATERAL (VALUES {facet_values}) AS f(facet, value)
             WHERE NULLIF(f.value, '') IS NOT NULL
               AND (f.facet = 'promotion' OR ({predicate}))
          GROUP BY f.facet, f.value""",
        params,
    )


def _old_facets(values: Sequence[str] = ()) -> dict[str, dict[str, int]]:
    from core.storage import postgres

    sql, params = _old_facets_query(values)
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()
    result: dict[str, dict[str, int]] = {}
    for facet, value, count in rows:
        normalized = str(value or "").strip().lower()
        if normalized:
            result.setdefault(str(facet), {})[normalized] = int(count)
    return result


def _new_facets(values: Sequence[str]) -> dict[str, dict[str, int]]:
    from core.storage import admin_repository

    return _normalize_all_facets(admin_repository.account_query_facets(_spec(values)))


def _actual_offer_truth() -> dict[str, set[int]]:
    from core.storage import postgres

    accounts = postgres.qualified("registered_accounts")
    offers = postgres.qualified("account_promotion_offers")
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT p.offer_key, (a.data->>'account_ordinal')::integer
                  FROM {offers} p
                  JOIN {accounts} a ON a.id = p.account_id
                 GROUP BY p.offer_key, a.data->>'account_ordinal'
                 ORDER BY p.offer_key, 2"""
        )
        truth: dict[str, set[int]] = {}
        for key, ordinal in cur.fetchall():
            truth.setdefault(str(key), set()).add(int(ordinal))
        return truth


def _account_ordinal_ids() -> dict[int, int]:
    from core.storage import postgres

    accounts = postgres.qualified("registered_accounts")
    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(
            f"""SELECT id, (data->>'account_ordinal')::integer
                  FROM {accounts}
                 WHERE data ? 'account_ordinal'"""
        )
        return {int(ordinal): int(account_id) for account_id, ordinal in cur.fetchall()}


def _explain(sql: str, params: Sequence[Any]) -> Any:
    from core.storage import postgres

    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute(f"EXPLAIN (FORMAT JSON, COSTS TRUE, BUFFERS TRUE) {sql}", params)
        row = cur.fetchone()
    return row[0] if row else None


def _explain_plans(scenarios: Sequence[Scenario]) -> dict[str, Any]:
    from core.storage import postgres, records

    table = _qualified(postgres, records.ACCOUNTS.name)
    plans: dict[str, Any] = {}
    for scenario in scenarios:
        key = scenario.name
        old_predicate, old_params = _promotion_filter_sql(
            scenario.old_values if scenario.old_values is not None else scenario.values
        )
        new_where, new_params = _new_query_sql(scenario.values)
        old_facet_sql, old_facet_params = _old_facets_query(
            scenario.old_values if scenario.old_values is not None else scenario.values
        )
        offers_table = postgres.qualified("account_promotion_offers")
        plans[key] = {
            "old_count": _explain(
                f"SELECT COUNT(*) FROM {table} a WHERE a.archived IS FALSE AND {old_predicate}",
                old_params,
            ),
            "new_count": _explain(
                f"SELECT COUNT(*) FROM {table} a WHERE {new_where}",
                new_params,
            ),
            "old_complete_id_list": _explain(
                f"SELECT a.id FROM {table} a WHERE a.archived IS FALSE AND {old_predicate} "
                "ORDER BY a.id LIMIT 100 OFFSET 0",
                old_params,
            ),
            "new_complete_id_list": _explain(
                f"SELECT a.id FROM {table} a WHERE {new_where} "
                "ORDER BY a.id LIMIT 100 OFFSET 0",
                new_params,
            ),
            "old_facets_real_semantics": _explain(old_facet_sql, old_facet_params),
            "new_dynamic_facets_cost": _explain(
                f"""SELECT p.offer_key, COUNT(DISTINCT p.account_id)
                      FROM {offers_table} p
                     GROUP BY p.offer_key
                     ORDER BY p.offer_key""",
                [],
            ),
        }
    return plans


def _measure(
    operation: str,
    values: Sequence[str],
    *,
    variant: str,
    old_values: Sequence[str] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter_ns()
    if operation == "list":
        result = (
            _old_ids(old_values if old_values is not None else values)
            if variant == "old_json"
            else _new_ids(values)
        )
        output = {"rows": len(result), "digest": _json_digest(result)}
    elif operation == "count":
        result = (
            _old_count(old_values if old_values is not None else values)
            if variant == "old_json"
            else _new_count(values)
        )
        output = {"rows": int(result), "digest": _json_digest(result)}
    elif operation == "facets":
        result = (
            _old_facets(old_values if old_values is not None else values)
            if variant == "old_json"
            else _new_facets(values)
        )
        output = {"rows": len(result), "facets": result, "digest": _json_digest(result)}
    else:
        raise ValueError(f"未知基准操作 {operation}")
    output.update(
        {
            "milliseconds": round((time.perf_counter_ns() - started) / 1_000_000, 6),
            "variant": variant,
            "operation": operation,
        }
    )
    return output


def _compare_scenario(
    scenario: Scenario,
    *,
    samples: int,
    old_samples: int,
    expected_keys: Sequence[str],
    expected_truth: Mapping[str, set[int]],
    facet_samples: int | None = None,
) -> dict[str, Any]:
    old_values = scenario.old_values if scenario.old_values is not None else scenario.values
    old_ids = _old_ids(old_values)
    new_ids = _new_ids(scenario.values)
    if scenario.compatibility_required and old_ids != new_ids:
        raise AssertionError(
            f"新旧账号集合不等价: {scenario.name}, old={len(old_ids)}, new={len(new_ids)}"
        )
    old_count = _old_count(old_values)
    new_count = _new_count(scenario.values)
    if scenario.compatibility_required and (old_count != new_count or old_count != len(old_ids)):
        raise AssertionError(
            f"新旧总数不等价: {scenario.name}, old={old_count}, new={new_count}, ids={len(old_ids)}"
        )

    measurements: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for operation in ("list", "count", "facets"):
        measurements[operation] = {"old_json": [], "new_projection": []}
        new_limit = facet_samples if operation == "facets" and facet_samples is not None else samples
        old_limit = min(old_samples, new_limit)
        for index in range(new_limit):
            order = ("old_json", "new_projection") if index % 2 == 0 else ("new_projection", "old_json")
            for variant in order:
                if variant == "old_json" and index >= old_limit:
                    continue
                measurements[operation][
                    "old_json" if variant == "old_json" else "new_projection"
                ].append(
                    _measure(
                        operation,
                        scenario.values,
                        variant=variant,
                        old_values=old_values,
                    )
                )
    old_facets = _old_facets(scenario.old_values or scenario.values)
    new_facets = _new_facets(scenario.values)
    old_promotion = old_facets.get("promotion", {})
    new_promotion = new_facets.get("promotion", {})
    new_category_facets = {
        key: value for key, value in new_promotion.items() if key in old_promotion
    }
    old_non_promotion = {
        key: value for key, value in old_facets.items() if key != "promotion"
    }
    new_non_promotion = {
        key: value for key, value in new_facets.items() if key != "promotion"
    }
    if scenario.compatibility_required and (
        old_non_promotion != new_non_promotion or old_promotion != new_category_facets
    ):
        raise AssertionError(
            f"旧 facets 分类不等价: {scenario.name}, "
            f"old={old_facets}, new={new_facets}"
        )
    expected_key_set = set(expected_keys)
    dynamic_facets = {
        key: value for key, value in new_promotion.items()
        if key.startswith("offer_v1_")
    }
    validate_dynamic_facet_truth(dynamic_facets, expected_truth)
    return {
        "name": scenario.name,
        "values": list(scenario.values),
        "matched_accounts": {
            "old_json": len(old_ids),
            "new_projection": len(new_ids),
        },
        "ids_digest": {
            "old_json": _json_digest(old_ids),
            "new_projection": _json_digest(new_ids),
        },
        "compatibility": {
            "ids_equal": old_ids == new_ids,
            "count_equal": old_count == new_count,
            "required": scenario.compatibility_required,
            "old_count": old_count,
            "new_count": new_count,
            "old_values": list(old_values),
        },
        "facet_counts": {"old_json": old_facets, "new_projection": new_facets},
        "facet_compatibility": {
            "old_json_codes": sorted(old_promotion),
            "new_legacy_category_counts": new_category_facets,
            "new_dynamic_keys": sorted(dynamic_facets),
            "dynamic_keys_equal_expected": set(dynamic_facets) == expected_key_set,
            "dynamic_counts_equal_expected": True,
        },
        "measurements": {
            operation: {
                variant: {
                    "summary": summarize_samples(rows),
                    "samples": rows,
                }
                for variant, rows in variants.items()
            }
            for operation, variants in measurements.items()
        },
    }


def _host_metadata(database_label: str, schema: str, args: argparse.Namespace) -> dict[str, Any]:
    from core.storage import postgres

    with postgres.connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_setting('server_version')")
        database, postgres_version = cur.fetchone()
    configured_schema = postgres.schema_name()
    if database != _DEFAULT_DATABASE or configured_schema != schema:
        raise RuntimeError(
            f"实际连接目标不符: database={database!r}, schema={configured_schema!r}"
        )
    return {
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": database,
        "database_label": database_label,
        "schema": schema,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cpu_count": os.cpu_count(),
        "postgres_version": postgres_version,
        "psycopg": importlib.metadata.version("psycopg"),
        "current_head": _git("rev-parse", "HEAD"),
        "worktree_dirty": bool(_git("status", "--porcelain")),
        "command": list(sys.argv),
        "arguments": {
            key: str(value) if isinstance(value, Path) else value
            for key, value in vars(args).items()
        },
    }


def _run_isolated(args: argparse.Namespace) -> dict[str, Any]:
    database_label, schema = _require_isolated_environment()
    from core.storage import postgres
    from tests.support_pg import drop_schema
    _assert_fresh_schema(schema)

    definitions = synthetic_offer_definitions()
    expected_keys = _expected_codes(definitions)
    try:
        scenarios = _make_scenarios(expected_keys, names=args.scenario)
    except ValueError as exc:
        _parser().error(str(exc))
    result: dict[str, Any] = {
        "metadata": _host_metadata(database_label, schema, args),
        "method": {
            "old": "f298c9c8 等价 JSON account_promotions/legacy Plus 细分类",
            "new": "Task 1 account_promotion_offers 投影 + Task 2 compile_query/account_query_count/account_query_facets",
            "transport": "同一 turb_test schema 的本地 PostgreSQL，零远端请求",
            "alternation": "每个操作每个场景按样本奇偶交替 old_json/new_projection",
            "p95_rule": "样本不足 30 时不输出 p95_ms，尤其是 300000 账号旧路径诊断样本",
            "facet_rule": "promotion facet 自排除当前 promotion 条件，并按账号去重",
            "list_metric": "list 是完整命中账号 ID 集合查询，独立于真实页面分页；EXPLAIN 同时输出 LIMIT 100 页计划",
            "dynamic_facet_metric": "new_dynamic_facets_cost 单独记录投影动态选项聚合，不伪报为旧 account_query_facets 等价路径",
        },
        "synthetic_data": {
            "accounts": args.accounts,
            "json_bytes_target": args.json_bytes,
            "offer_rows": list(synthetic_expected_offer_names(definitions)),
            "expected_projection_offer_keys": list(expected_keys),
            "scenarios": [
                {
                    "name": item.name,
                    "values": list(item.values),
                    "old_values": list(item.old_values if item.old_values is not None else item.values),
                    "compatibility_required": item.compatibility_required,
                }
                for item in scenarios
            ],
        },
        "schema_cleaned": False,
    }
    try:
        result["seed"] = _seed_accounts(args.accounts, args.json_bytes, definitions)
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT to_regclass(%s), to_regclass(%s)",
                (f"{schema}.registered_accounts", f"{schema}.account_promotion_offers"),
            )
            actual_accounts, actual_offers = cur.fetchone()
        if not actual_accounts or not actual_offers:
            raise RuntimeError(
                f"建表后实际 schema 不符: accounts={actual_accounts!r}, offers={actual_offers!r}"
            )
        result["sizes_after_seed"] = {
            "registered_accounts": _relation_sizes(postgres, "registered_accounts"),
            "account_promotion_offers": _relation_sizes(postgres, "account_promotion_offers"),
        }
        logical_total = int(result["seed"]["json_logical_bytes"]["total"])
        stored_total = int(result["sizes_after_seed"]["registered_accounts"]["total_bytes"])
        result["sizes_after_seed"]["registered_accounts"]["json_to_relation_ratio"] = (
            round(stored_total / logical_total, 4) if logical_total else None
        )
        with postgres.connect() as conn, conn.cursor() as cur:
            cur.execute(
                f"SELECT offer_key, COUNT(DISTINCT account_id), COUNT(*) "
                f"FROM {postgres.qualified('account_promotion_offers')} GROUP BY offer_key ORDER BY offer_key"
            )
            projection_rows = [
                {"offer_key": str(row[0]), "accounts": int(row[1]), "rows": int(row[2])}
                for row in cur.fetchall()
            ]
        actual_keys = {row["offer_key"] for row in projection_rows}
        expected_key_set = set(expected_keys)
        if actual_keys != expected_key_set:
            raise AssertionError(
                "投影优惠 key 集合不等于合成预期: "
                f"missing={sorted(expected_key_set - actual_keys)}, "
                f"extra={sorted(actual_keys - expected_key_set)}"
            )
        ordinal_ids = _account_ordinal_ids()
        id_to_ordinal = {
            account_id: ordinal for ordinal, account_id in ordinal_ids.items()
        }
        expected_truth = synthetic_offer_truth(args.accounts, definitions)
        actual_truth = _actual_offer_truth()
        for key in expected_keys:
            if actual_truth.get(key, set()) != expected_truth[key]:
                raise AssertionError(
                    f"投影账号集合不等于合成真值: {key}, "
                    f"missing={sorted(expected_truth[key] - actual_truth.get(key, set()))}, "
                    f"extra={sorted(actual_truth.get(key, set()) - expected_truth[key])}"
                )
            new_ids_for_key = _new_ids((key,))
            new_ordinals_for_key = map_account_ids_to_ordinals(
                new_ids_for_key,
                id_to_ordinal,
            )
            if new_ordinals_for_key != expected_truth[key] or _new_count((key,)) != len(expected_truth[key]):
                raise AssertionError(
                    f"新查询动态优惠真值不等价: {key}, "
                    f"expected={len(expected_truth[key])}, "
                    f"actual_ids={len(new_ordinals_for_key)}, "
                    f"actual_count={_new_count((key,))}"
                )
        result["projection"] = {
            "rows": projection_rows,
            "actual_offer_keys": sorted(actual_keys),
            "truth": {
                key: {
                    "expected_count": len(expected_truth[key]),
                    "actual_count": len(actual_truth.get(key, set())),
                    "ids_digest": _json_digest(sorted(expected_truth[key])),
                }
                for key in expected_keys
            },
        }
        no_filter_facets = _new_facets(())
        no_filter_promotion = no_filter_facets.get("promotion", {})
        validate_dynamic_facet_truth(
            {
                key: value
                for key, value in no_filter_promotion.items()
                if key.startswith("offer_v1_")
            },
            expected_truth,
        )
        result["projection"]["dynamic_facets_unfiltered"] = {
            key: int(value)
            for key, value in no_filter_promotion.items()
            if key.startswith("offer_v1_")
        }
        result["execution_plans"] = _explain_plans(scenarios)
        result["scenarios"] = [
            _compare_scenario(
                scenario,
                samples=args.samples,
                old_samples=args.old_samples if args.old_samples is not None else args.samples,
                expected_keys=expected_keys,
                expected_truth=expected_truth,
                facet_samples=args.facet_samples,
            )
            for scenario in scenarios
        ]
        return result
    finally:
        try:
            drop_schema(schema)
            result["schema_cleaned"] = True
        except Exception as exc:
            result["schema_cleanup_error"] = f"{type(exc).__name__}: {exc}"
            raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accounts", type=int, default=8000)
    parser.add_argument("--json-bytes", type=int, default=_DEFAULT_JSON_BYTES)
    parser.add_argument("--samples", type=int, default=30)
    parser.add_argument(
        "--old-samples",
        type=int,
        default=None,
        help="旧 JSON 路径样本数；300000 账号建议 1-3，少于 30 不输出旧 P95",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        metavar="名称",
        help="只采样指定场景，可多次传入，例如 --scenario 无筛选 --scenario Team。默认采样全部场景",
    )
    parser.add_argument(
        "--facet-samples",
        type=int,
        default=None,
        help="单独指定每个场景的新 facets 样本数，旧 facets 样本数也不超过此值。默认沿用 --samples",
    )
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.accounts < 1:
        parser.error("--accounts 必须为正整数")
    if args.json_bytes < _MIN_JSON_BYTES:
        parser.error(f"--json-bytes 至少为 {_MIN_JSON_BYTES}")
    if args.samples < 1:
        parser.error("--samples 必须为正整数")
    if args.old_samples is not None and args.old_samples < 1:
        parser.error("--old-samples 必须为正整数")
    if args.facet_samples is not None and args.facet_samples < 1:
        parser.error("--facet-samples 必须为正整数")
    try:
        from tools.test_isolated import build_isolated_environment

        schema = _BENCHMARK_SCHEMA_PREFIX + uuid.uuid4().hex[:12]
        environment = build_isolated_environment(project_root=ROOT, schema=schema)
        worker_code = (
            "import sys; "
            f"sys.path.insert(0, {str(ROOT)!r}); "
            "from tools.benchmarks.benchmark_account_promotions import _parser, _worker_main; "
            "raise SystemExit(_worker_main(_parser().parse_args()))"
        )
        command = [sys.executable, "-c", worker_code, *sys.argv[1:]]
        return subprocess.call(command, cwd=ROOT, env=environment)
    except RuntimeError:
        raise
    except Exception as exc:
        print(f"优惠性能基准隔离环境失败：{type(exc).__name__}。", file=sys.stderr)
        return 1


def _worker_main(args: argparse.Namespace) -> int:
    try:
        result = _run_isolated(args)
        output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(output, encoding="utf-8")
        print(output)
        return 0
    except Exception as exc:
        print(f"优惠性能基准失败：{type(exc).__name__}；隔离 schema 已尝试清理。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
