# -*- coding: utf-8 -*-
"""从账号最终套餐快照维护优惠筛选所需的轻量记录。"""
from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
import re

from core.accounts.plans.promotion import (
    ELIGIBLE_PROMO_KINDS, PROMOTION_PLANS, PROMO_KINDS, sanitize_promotion_text,
)
from core.storage import postgres as pg
from core.storage.records import ACCOUNTS, _ACCOUNT_PROMOTION_KIND_SQL

TABLE_NAME = "account_promotion_offers"
LEGACY_OFFER_CHECKED_FIELD = "plus_offer_last_checked_at"
_KEY_PREFIX = "offer_v1_"
_DECIMAL_SYNTAX = r"^[+-]?([0-9]+([.][0-9]*)?|[.][0-9]+)([eE][+-]?[0-9]+)?$"
_ASCII_WHITESPACE = " \t\n\r\f\v"
_ASCII_LOWERCASE = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_PERIOD_ALIASES = {
    "days": "day", "日": "day", "天": "day",
    "weeks": "week", "周": "week", "星期": "week",
    "months": "month", "月": "month", "个月": "month",
    "years": "year", "年": "year",
}
_PERIOD_LABELS = {"day": "天", "week": "周", "month": "个月", "year": "年"}
_PLAN_LABELS = {"team": "Team", "plus": "Plus", "go": "Go"}
_LEGACY_OFFER_COLUMNS = (
    "plus_promo_kind", "plus_discount_eligible", "plus_promo_eligible", "plus_trial_eligible",
    "plus_promo_discount_percentage", "plus_promo_duration_num_periods", "plus_promo_duration_period",
    "plus_promo_campaign_id", "plus_promo_title", "plus_promo_promotion_type", "plus_promo_promotion_type_label",
)
_LEGACY_JSON_FIELDS = (
    "plus_trial_discount_percentage", "plus_trial_duration_num_periods", "plus_trial_duration_period",
    "plus_trial_campaign_id", "plus_trial_title", "plus_trial_promotion_type_label",
)
_OFFER_COLUMNS = (
    "country, offer_key, plan, kind, eligible, discount_percentage, "
    "duration_num_periods, duration_period, stale, legacy_filter_values"
)
_OFFER_UPSERT = """ON CONFLICT (account_id, country, offer_key) DO UPDATE
       SET eligible = excluded.eligible, stale = excluded.stale, legacy_filter_values = excluded.legacy_filter_values
     WHERE (current_offer.eligible, current_offer.stale, current_offer.legacy_filter_values)
        IS DISTINCT FROM (excluded.eligible, excluded.stale, excluded.legacy_filter_values)"""


def _normalized_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip(_ASCII_WHITESPACE).translate(_ASCII_LOWERCASE)


def _normalized_period(value: object) -> str:
    period = _normalized_text(value)
    return _PERIOD_ALIASES.get(period, period)


def _number_text(value: object, *, is_percentage: bool = False) -> str:
    if isinstance(value, str):
        value = value.strip(_ASCII_WHITESPACE)
        if re.fullmatch(_DECIMAL_SYNTAX, value) is None:
            return ""
    elif isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return ""
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        return ""
    if not number.is_finite():
        return ""
    if is_percentage:
        if not 0 <= number <= 100:
            return ""
    elif number <= 0:
        return ""
    if number == 0:
        return "0"
    text = format(number, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def offer_key(plan, kind, percentage, periods, period) -> str:
    """生成跨国家和活动标识通用的优惠组合键。"""
    normalized_kind = _normalized_text(kind)
    values = (
        _normalized_text(plan),
        normalized_kind if normalized_kind in PROMO_KINDS else "unknown",
        _number_text(percentage, is_percentage=True),
        _number_text(periods),
        _normalized_period(period),
    )
    # SQL 使用相同的字段顺序、空值表示及 UTF-8 编码。
    digest = hashlib.md5("|".join(values).encode("utf-8"), usedforsecurity=False)
    return _KEY_PREFIX + digest.hexdigest()


def _duration_label(periods: str, period: str) -> str:
    unit = _PERIOD_LABELS.get(period)
    if unit is None:
        unit = " ".join((sanitize_promotion_text(period) or "").split())
    if periods and unit:
        return f" {periods}{unit}"
    if periods:
        return f" {periods}（期限单位未返回）"
    if unit:
        return f"（期限数量未返回，单位为{unit}）"
    return "（期限未返回）"


def offer_label(row: Mapping[str, object]) -> str:
    """用投影字段生成可读筛选标签。"""
    plan = _PLAN_LABELS.get(_normalized_text(row.get("plan")), "")
    kind = _normalized_text(row.get("kind"))
    status = {"none": "无优惠", "unknown": "历史优惠待复查"}.get(kind)
    if status:
        return f"{plan} {status}".strip()
    percentage = _number_text(row.get("discount_percentage"), is_percentage=True)
    details = "（折扣比例未返回）" if not percentage else ""
    if kind == "free_trial":
        description = "免费"
        if percentage and percentage != "100":
            details = f"（记录折扣 {percentage}%）"
    elif kind == "discount":
        if percentage == "50":
            description = "半价"
        else:
            description = f"减 {percentage}%" if percentage else "折扣比例未返回"
        details = ""
    else:
        description = "其他优惠"
        if percentage:
            details = f"（减 {percentage}%）"
    duration = _duration_label(
        _number_text(row.get("duration_num_periods")), _normalized_period(row.get("duration_period")),
    )
    return f"{plan} {description}{duration}{details}".strip()


def _sql_text(expression: str) -> str:
    return rf'''LOWER(BTRIM({expression}, E' \t\n\r\f\013') COLLATE "C")'''


def _sql_json_number(expression: str) -> str:
    value = _sql_text(expression)
    return (
        f"CASE WHEN {value} ~ '{_DECIMAL_SYNTAX}' AND pg_input_is_valid({value}, 'numeric') "
        f"THEN {value}::NUMERIC END"
    )


def _sql_members(values: Iterable[str]) -> str:
    return ", ".join(f"'{value}'" for value in sorted(values))


def _sql_legacy_confirmed(row: str) -> str:
    return (
        f"(COALESCE({row}.plan_check_status = 'success', FALSE) OR {row}.plan_check_ok IS TRUE "
        f"OR NULLIF({row}.plan_last_success_at, '') IS NOT NULL)"
    )


def _sql_legacy_snapshot_status(row: str) -> str:
    """旧结果只有保存了优惠字段时才能证明当前活动状态。"""
    snapshot = f"{row}.data->>'plan_last_success_result_json'"
    return f"""CASE WHEN ({snapshot}) IS JSON OBJECT AND pg_input_is_valid(({snapshot}), 'jsonb') THEN EXISTS (
        SELECT 1 FROM jsonb_object_keys(({snapshot})::JSONB) AS fields(name)
         WHERE name = 'plus_discount_eligible' OR name LIKE 'plus!_promo!_%' ESCAPE '!'
               OR name LIKE 'plus!_trial!_%' ESCAPE '!'
    ) END"""


def _sql_legacy_none_confirmed(row: str) -> str:
    kind = _sql_text(f"{row}.plus_promo_kind")
    return f"""CASE
        WHEN {kind} IS DISTINCT FROM 'none' THEN FALSE
        WHEN {row}.data ? '{LEGACY_OFFER_CHECKED_FIELD}' THEN TRUE
        WHEN {_sql_legacy_confirmed(row)} THEN ({_sql_legacy_snapshot_status(row)}) IS DISTINCT FROM FALSE
        ELSE FALSE
    END"""


def _sql_legacy_evidence(row: str) -> str:
    return f"ROW({_sql_legacy_confirmed(row)}, {row}.data->'plan_last_success_result_json')"


def _sql_legacy_activity_codes() -> str:
    """按原始活动字段生成旧筛选代码，保持旧端点对字符串和数字的区分。"""
    percentage = "offer->'discount_percentage'"
    period = "LOWER(COALESCE(offer->>'duration_period', ''))"
    periods = "offer->>'duration_num_periods'"
    return f"""CASE WHEN offer->'eligible' = 'true'::jsonb AND (
        (offer->>'plan' IN ('plus', 'go') AND jsonb_typeof({percentage}) = 'number'
          AND {percentage} > '0'::jsonb AND {percentage} <= '100'::jsonb)
        OR (offer->>'plan' = 'team' AND offer->>'kind' IN ({_sql_members(ELIGIBLE_PROMO_KINDS)}))
    ) THEN ARRAY_REMOVE(ARRAY[
        CASE WHEN offer->>'plan' = 'team' THEN 'team_eligible'
             ELSE (offer->>'plan') || '_' || CASE {percentage}
                 WHEN '100'::jsonb THEN '100' WHEN '50'::jsonb THEN '50' ELSE 'other' END END,
        CASE WHEN offer->>'plan' = 'plus' AND {percentage} = '50'::jsonb
                  AND {period} IN ('month', 'months', '月') AND ({periods}) ~ '^[123]$'
             THEN 'plus_50_' || ({periods}) || 'm' END
    ], NULL) ELSE ARRAY[]::TEXT[] END"""


def _sql_legacy_promoted_codes() -> str:
    """旧 Plus 完全基于原有提升列分类，独立于具体优惠的历史字段补全。"""
    percentage = "source_account.plus_promo_discount_percentage"
    period = "LOWER(COALESCE(source_account.plus_promo_duration_period, ''))"
    periods = "source_account.plus_promo_duration_num_periods"
    return f"""CASE WHEN legacy.promoted_kind IN ({_sql_members(ELIGIBLE_PROMO_KINDS)})
                          AND {percentage} > 0 AND {percentage} <= 100
    THEN ARRAY_REMOVE(ARRAY[
        CASE {percentage} WHEN 100 THEN 'plus_100' WHEN 50 THEN 'plus_50' ELSE 'plus_other' END,
        CASE WHEN {percentage} = 50 AND {period} IN ('month', 'months', '月') AND {periods} IN (1, 2, 3)
             THEN 'plus_50_' || {periods}::TEXT || 'm' END
    ], NULL) ELSE ARRAY[]::TEXT[] END"""


def _create_projection_function(cur, function: str, accounts: str) -> None:
    period = _sql_text("raw.period")
    period_aliases = " ".join(f"WHEN '{alias}' THEN '{unit}'" for alias, unit in _PERIOD_ALIASES.items())
    country_text = _sql_text("offer->>'country'")
    country = f'UPPER({country_text} COLLATE "C")'
    legacy_kind_columns = ", ".join(f"source_account.{field}" for field in _LEGACY_OFFER_COLUMNS[:4])
    # 顶层数组存在时以它为准，空数组也不能回退到历史 Plus。
    # 历史迁移曾默认写入 none，因此旧记录需要成功证据才能确认无优惠。
    # 原期限和提升整数能互相对应时，动态项保留未舍入的原始期限。
    cur.execute(f"""
        CREATE OR REPLACE FUNCTION {function}(source_account {accounts})
        RETURNS TABLE (
            country TEXT, offer_key TEXT, plan TEXT, kind TEXT, eligible BOOLEAN,
            discount_percentage NUMERIC, duration_num_periods NUMERIC, duration_period TEXT, stale BOOLEAN,
            legacy_filter_values TEXT[]
        ) LANGUAGE SQL IMMUTABLE PARALLEL SAFE SET extra_float_digits TO 3 AS $$
            WITH source AS (
                SELECT CASE WHEN jsonb_typeof(source_account.data->'account_promotions') = 'array'
                       THEN source_account.data->'account_promotions' END AS snapshot
            ), legacy_inputs AS (
                SELECT NULLIF({_sql_text("source_account.plus_promo_kind")}, '') AS kind,
                       ({_ACCOUNT_PROMOTION_KIND_SQL}) AS promoted_kind,
                       {_sql_legacy_none_confirmed('source_account')} AS confirmed_none,
                       source_account.plus_promo_duration_num_periods AS promoted_periods,
                       {_sql_json_number("source_account.data->>'plus_trial_duration_num_periods'")} AS trial_periods,
                       COALESCE(source_account.plus_promo_discount_percentage::TEXT,
                                source_account.data->>'plus_trial_discount_percentage') AS percentage,
                       COALESCE(NULLIF({_sql_text("source_account.plus_promo_duration_period")}, ''),
                                source_account.data->>'plus_trial_duration_period') AS period,
                       COALESCE(NULLIF({_sql_text("source_account.plus_promo_campaign_id")}, ''),
                                {_sql_text("source_account.data->>'plus_trial_campaign_id'")}, '') AS campaign,
                       COALESCE(NULLIF({_sql_text("source_account.plus_promo_title")}, ''),
                                {_sql_text("source_account.data->>'plus_trial_title'")}, '') AS title,
                       COALESCE({_sql_text("source_account.plus_promo_promotion_type")}, '') AS promo_type,
                       COALESCE(NULLIF({_sql_text("source_account.plus_promo_promotion_type_label")}, ''),
                                {_sql_text("source_account.data->>'plus_trial_promotion_type_label'")}, '') AS promo_label
                  FROM source
                 CROSS JOIN LATERAL (SELECT {legacy_kind_columns}) AS compatibility
                 WHERE source.snapshot IS NULL
            ), legacy AS (
                SELECT kind, promoted_kind, confirmed_none,
                       percentage IS NOT NULL AS has_percentage,
                       CASE WHEN pg_input_is_valid(percentage, 'numeric') THEN percentage::NUMERIC END AS percentage,
                       CASE
                            WHEN promoted_periods IS NULL THEN trial_periods
                            WHEN trial_periods > 0 AND trial_periods <= 2147483647.5
                                 AND pg_input_is_valid(trial_periods::TEXT, 'double precision') THEN CASE
                                WHEN ROUND(trial_periods::DOUBLE PRECISION) = promoted_periods THEN trial_periods
                                ELSE promoted_periods::NUMERIC END
                            ELSE promoted_periods::NUMERIC
                       END AS periods,
                       period, campaign, promo_type,
                       concat_ws(' ', campaign, title, promo_type, promo_label) AS description
                  FROM legacy_inputs
            ), raw AS (
                SELECT {country} AS country,
                       {_sql_text("offer->>'plan'")} AS plan,
                       {_sql_text("offer->>'kind'")} AS kind,
                       COALESCE(offer->'eligible' = 'true'::jsonb, FALSE) AS eligible,
                       {_sql_json_number("offer->>'discount_percentage'")} AS percentage,
                       {_sql_json_number("offer->>'duration_num_periods'")} AS periods,
                       CASE WHEN jsonb_typeof(offer->'duration_period') = 'string'
                            THEN offer->>'duration_period' END AS period,
                       COALESCE(offer->'stale' = 'true'::jsonb, FALSE) AS stale,
                       {_sql_legacy_activity_codes()} AS legacy_filter_values
                  FROM source, LATERAL jsonb_array_elements(source.snapshot) AS element(offer)
                UNION ALL
                SELECT '', 'plus', classified.kind, classified.kind IN ({_sql_members(ELIGIBLE_PROMO_KINDS)}),
                       legacy.percentage, legacy.periods, legacy.period, FALSE, compat.filter_values
                  FROM legacy
                 CROSS JOIN LATERAL (SELECT CASE
                       WHEN legacy.kind IN ({_sql_members(PROMO_KINDS)}) THEN legacy.kind
                       WHEN legacy.percentage = 100 THEN 'free_trial'
                       WHEN legacy.percentage > 0 AND legacy.percentage < 100 THEN 'discount'
                       WHEN legacy.percentage = 0 THEN 'none'
                       WHEN legacy.has_percentage THEN 'unknown'
                       WHEN legacy.description LIKE '%free trial%' OR legacy.campaign LIKE '%-free%'
                            OR legacy.campaign LIKE '%trial%' OR legacy.promo_type IN ('free_trial', 'free')
                         THEN 'free_trial'
                       WHEN legacy.campaign LIKE '%pct-off%' OR legacy.description LIKE '%discount%'
                            OR legacy.description LIKE '%% off%' THEN 'discount'
                       WHEN BTRIM(legacy.description) <> '' THEN 'other_promo'
                       WHEN source_account.plus_discount_eligible IS TRUE THEN 'discount'
                       WHEN source_account.plus_promo_eligible IS TRUE OR source_account.plus_trial_eligible IS TRUE
                         THEN 'unknown'
                       ELSE 'none'
                 END AS kind) AS classified
                 CROSS JOIN LATERAL (SELECT {_sql_legacy_promoted_codes()} AS filter_values) AS compat
                 WHERE classified.kind <> 'none' OR legacy.percentage = 0
                    OR cardinality(compat.filter_values) > 0 OR legacy.confirmed_none
            ), normalized AS (
                SELECT CASE WHEN raw.country ~ '^[A-Z]{{2}}$' THEN raw.country ELSE '' END AS country,
                       raw.plan,
                       CASE WHEN raw.kind IN ({_sql_members(PROMO_KINDS)}) THEN raw.kind ELSE 'unknown' END AS kind,
                       raw.eligible,
                       CASE WHEN raw.percentage BETWEEN 0 AND 100 THEN trim_scale(raw.percentage) END AS percentage,
                       CASE WHEN raw.periods > 0 AND raw.periods < 'Infinity'::NUMERIC
                            THEN trim_scale(raw.periods) END AS periods,
                       CASE {period} {period_aliases} ELSE NULLIF({period}, '') END AS period,
                       raw.stale, raw.legacy_filter_values
                  FROM raw
                 WHERE raw.plan IN ({_sql_members(PROMOTION_PLANS)})
            ), keyed AS (
                SELECT normalized.*, '{_KEY_PREFIX}' || md5(convert_to(concat_ws('|',
                       normalized.plan, normalized.kind, COALESCE(normalized.percentage::TEXT, ''),
                       COALESCE(normalized.periods::TEXT, ''), COALESCE(normalized.period, '')
                ), 'UTF8')) AS offer_key
                  FROM normalized
            )
            SELECT keyed.country, keyed.offer_key, keyed.plan, keyed.kind, bool_or(keyed.eligible),
                   keyed.percentage, keyed.periods, keyed.period,
                   COALESCE(bool_and(keyed.stale) FILTER (WHERE keyed.eligible), bool_and(keyed.stale)),
                   COALESCE(array_agg(DISTINCT code ORDER BY code) FILTER (WHERE code IS NOT NULL), ARRAY[]::TEXT[])
              FROM keyed
              LEFT JOIN LATERAL unnest(keyed.legacy_filter_values) AS codes(code) ON TRUE
             GROUP BY keyed.country, keyed.offer_key, keyed.plan, keyed.kind, keyed.percentage, keyed.periods, keyed.period
        $$
    """)


def _create_remember_legacy_none_trigger(cur, accounts: str) -> None:
    name = "remember_account_legacy_no_promotion"
    function = pg.qualified(name)
    trigger = pg.quote_identifier(name)
    old_kind = _sql_text("OLD.plus_promo_kind")
    new_kind = _sql_text("NEW.plus_promo_kind")
    # 旧无优惠证据可能只存在于通用套餐状态或上次成功结果。
    # 覆盖该证据时先把已确认的优惠事实保存到账号，重建无需读取旧投影。
    cur.execute(f"""
        CREATE OR REPLACE FUNCTION {function}() RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            IF ({_sql_legacy_none_confirmed('OLD')}) AND NOT ({_sql_legacy_none_confirmed('NEW')}) THEN
                NEW.data := jsonb_set(
                    NEW.data, ARRAY['{LEGACY_OFFER_CHECKED_FIELD}'],
                    COALESCE(to_jsonb(NULLIF(OLD.plan_last_success_at, '')), 'null'::JSONB)
                );
            END IF;
            RETURN NEW;
        END
        $$
    """)
    cur.execute(f"""
        CREATE OR REPLACE TRIGGER {trigger}
        BEFORE UPDATE OF data, plan_check_status, plan_check_ok, plan_last_success_at ON {accounts}
        FOR EACH ROW WHEN (
            {old_kind} = 'none' AND {new_kind} = 'none'
            AND jsonb_typeof(OLD.data->'account_promotions') IS DISTINCT FROM 'array'
            AND jsonb_typeof(NEW.data->'account_promotions') IS DISTINCT FROM 'array'
            AND NOT OLD.data ? '{LEGACY_OFFER_CHECKED_FIELD}'
            AND NOT NEW.data ? '{LEGACY_OFFER_CHECKED_FIELD}'
            AND {_sql_legacy_evidence('OLD')} IS DISTINCT FROM {_sql_legacy_evidence('NEW')}
        ) EXECUTE FUNCTION {function}()
    """)


def _create_sync_trigger(cur, accounts: str, offers: str, project: str) -> None:
    name = "sync_account_promotion_offers"
    function = pg.qualified(name)
    trigger = pg.quote_identifier(name)

    def legacy_values(row: str) -> str:
        columns = [f"{row}.{column}" for column in _LEGACY_OFFER_COLUMNS]
        json_fields = [f"{row}.data->'{key}'" for key in (*_LEGACY_JSON_FIELDS, LEGACY_OFFER_CHECKED_FIELD)]
        return ", ".join([*columns, *json_fields])

    changes = ", ".join((
        "data", *_LEGACY_OFFER_COLUMNS, "plan_check_status", "plan_check_ok", "plan_last_success_at",
    ))
    cur.execute(f"""
        CREATE OR REPLACE FUNCTION {function}() RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
            snapshot JSONB := NEW.data->'account_promotions';
        BEGIN
            IF TG_OP = 'UPDATE' THEN
                -- JSONB 数值 1 和 1.0 相等，旧期限筛选仍区分其文本表示。
                -- 旧结果证据新增时应与历史回填得到同一投影。
                IF snapshot::TEXT IS NOT DISTINCT FROM (OLD.data->'account_promotions')::TEXT
                   AND (
                       jsonb_typeof(snapshot) = 'array'
                       OR (
                           ROW({legacy_values('OLD')}) IS NOT DISTINCT FROM ROW({legacy_values('NEW')})
                           AND CASE WHEN {_sql_legacy_evidence('OLD')} IS NOT DISTINCT FROM {_sql_legacy_evidence('NEW')}
                                THEN TRUE ELSE ({_sql_legacy_none_confirmed('OLD')}) = ({_sql_legacy_none_confirmed('NEW')}) END
                       )
                   )
                THEN
                    RETURN NEW;
                END IF;

                WITH expected AS MATERIALIZED (SELECT * FROM {project}(NEW)), removed AS (
                    DELETE FROM {offers} AS previous
                     WHERE previous.account_id = NEW.id
                       AND NOT EXISTS (
                           SELECT 1 FROM expected
                            WHERE expected.country = previous.country AND expected.offer_key = previous.offer_key
                       )
                )
                INSERT INTO {offers} AS current_offer (account_id, {_OFFER_COLUMNS})
                SELECT NEW.id, expected.* FROM expected
                {_OFFER_UPSERT};
            ELSE
                INSERT INTO {offers} (account_id, {_OFFER_COLUMNS})
                SELECT NEW.id, projected.* FROM {project}(NEW) AS projected;
            END IF;
            RETURN NEW;
        END
        $$
    """)
    cur.execute(f"""
        CREATE OR REPLACE TRIGGER {trigger}
        AFTER INSERT OR UPDATE OF {changes} ON {accounts}
        FOR EACH ROW EXECUTE FUNCTION {function}()
    """)


def ensure_schema(conn) -> None:
    """在版本迁移事务中建表、安装触发器并回填最终优惠。"""
    accounts = pg.qualified(ACCOUNTS.name)
    offers = pg.qualified(TABLE_NAME)
    project = pg.qualified("project_account_promotion_offers")
    with conn.cursor() as cur:
        cur.execute(f"""
            CREATE TABLE IF NOT EXISTS {offers} (
                account_id BIGINT NOT NULL REFERENCES {accounts}(id) ON DELETE CASCADE,
                country TEXT NOT NULL,
                offer_key TEXT NOT NULL,
                plan TEXT NOT NULL,
                kind TEXT NOT NULL,
                eligible BOOLEAN NOT NULL,
                discount_percentage NUMERIC,
                duration_num_periods NUMERIC,
                duration_period TEXT,
                stale BOOLEAN NOT NULL,
                legacy_filter_values TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
                PRIMARY KEY (account_id, country, offer_key)
            )
        """)
        cur.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_account_promotion_offers_key_account
              ON {offers} (offer_key, account_id)
        """)
        _create_projection_function(cur, project, accounts)
        _create_remember_legacy_none_trigger(cur, accounts)
        _create_sync_trigger(cur, accounts, offers, project)
        cur.execute(f"""
            INSERT INTO {offers} AS current_offer (account_id, {_OFFER_COLUMNS})
            SELECT account.id, projected.*
              FROM {accounts} AS account
             CROSS JOIN LATERAL {project}(account) AS projected
            {_OFFER_UPSERT}
        """)
        cur.execute(f"ANALYZE {offers}")
