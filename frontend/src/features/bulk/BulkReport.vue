<script setup lang="ts">
import {computed} from 'vue';
import type {BulkRecord} from './contracts';
import {
  object,
  rows,
  number,
  numeric,
  duration,
  scopeText,
  operationLabel,
  operationNames,
  businessGroups,
  planName,
  offerName,
  railWidth,
} from './bulkReportPresentation';
import BulkBusinessStats from './BulkBusinessStats.vue';
const props = defineProps<{report: BulkRecord; formatDateTime: (value: unknown) => string}>();
const supported = computed(() => Object.hasOwn(operationNames, String(props.report.operation_key)));
const totals = computed(() => object(props.report.totals)),
  timing = computed(() => object(props.report.duration)),
  at = computed(() => object(props.report.at_refresh)),
  offers = computed(() => object(props.report.offers));
const completed = computed(() => props.report.phase === 'completed'),
  planCheck = computed(() => props.report.operation_key === 'plan_check');
const plans = computed(() =>
  rows(props.report.plans).sort((a, b) =>
    a.plan === 'unknown'
      ? 1
      : b.plan === 'unknown'
        ? -1
        : (numeric(b.accounts) || 0) - (numeric(a.accounts) || 0),
  ),
);
const offerRows = computed(() =>
  rows(offers.value.by_plan).sort(
    (a, b) =>
      (numeric(b.accounts) || 0) - (numeric(a.accounts) || 0) ||
      planName(a.plan).localeCompare(planName(b.plan)),
  ),
);
const maxPlans = computed(() => Math.max(0, ...plans.value.map((row) => numeric(row.accounts) || 0))),
  maxOffers = computed(() => Math.max(0, ...offerRows.value.map((row) => numeric(row.accounts) || 0)));
const groups = computed(() => businessGroups(props.report.business_summary));
const outcomeMetrics = [
  ['成功', 'success', 'is-success'],
  ['失败', 'failed', 'is-danger'],
  ['部分成功', 'partial_success', 'is-warning'],
  ['待完成', 'active', ''],
] as const;
const atCauses = [
  ['AT 过期', 'expired_accounts'],
  ['远端拒绝 AT', 'invalid_accounts'],
  ['缺少 AT', 'missing_token_accounts'],
] as const;
const atResults = [
  ['尝试刷新', 'attempted_accounts', ''],
  ['刷新成功', 'succeeded_accounts', 'is-success'],
  ['刷新失败', 'failed_accounts', 'is-danger'],
  ['刷新中', 'pending_accounts', ''],
] as const;
const offerTotals = [
  ['有优惠账号', 'with_offer_accounts', '多个国家只算一个账号'],
  ['确认无优惠', 'confirmed_no_offer_accounts', '完整查询成功且无优惠'],
  ['优惠待确认', 'unknown_accounts', '含待完成、未执行或缺少结果'],
] as const;
</script>
<template>
  <section
    v-if="supported && report.population_ready === false"
    class="bulk-plan-report bulk-report-placeholder"
    :aria-label="operationLabel(report.operation_key) + '报告'"
  >
    <h3>{{ operationLabel(report.operation_key) }}报告</h3>
    <p role="status">
      {{ scopeText(report) }} ·
      {{
        report.phase === 'preparing'
          ? '账号名单准备中，固定后生成报告。'
          : '该轮名单未固定，无法生成账号统计。'
      }}
    </p>
  </section>
  <section v-else-if="supported" class="bulk-plan-report" aria-labelledby="bulkPlanReportTitle">
    <header class="bulk-report-header">
      <div>
        <div class="bulk-report-heading-line">
          <h3 id="bulkPlanReportTitle">
            {{ operationLabel(report.operation_key) }}{{ completed ? '完成报告' : '实时报告' }}
          </h3>
          <span class="bulk-report-phase" :class="{'is-completed': completed}">{{
            completed ? '已完成' : report.phase === 'preparing' ? '名单准备中' : '统计更新中'
          }}</span>
        </div>
        <p>{{ scopeText(report) }} · {{ number(totals.accounts) }} 个账号</p>
      </div>
      <span class="bulk-report-updated">更新于 {{ formatDateTime(report.generated_at) }}</span>
    </header>
    <p
      v-if="object(report.projection).state && object(report.projection).state !== 'current'"
      class="bulk-report-sync"
      role="status"
    >
      {{
        object(report.projection).state === 'failed'
          ? '结果汇总暂时失败，以下统计尚未收齐，请稍后刷新。'
          : '执行结果正在汇总，以下统计尚未收齐。'
      }}
    </p>
    <dl class="bulk-report-outcomes">
      <div
        v-for="[title, key, variant] in outcomeMetrics"
        :key="key"
        class="bulk-report-metric"
        :class="variant"
      >
        <dt>{{ title }}</dt>
        <dd>{{ number(totals[key]) }}<span>个</span></dd>
      </div>
    </dl>
    <div class="bulk-report-outcome-note">
      <span>已结束 {{ number(totals.completed) }} / {{ number(totals.accounts) }} 个</span
      ><span>未执行 {{ number(totals.not_executed) }} 个</span
      ><span>已取消 {{ number(totals.cancelled) }} 个</span>
    </div>
    <div class="bulk-report-execution">
      <section aria-label="账号执行耗时">
        <div class="bulk-report-section-head">
          <h4>账号执行耗时</h4>
          <span>已结束样本 {{ number(timing.sample_count) }} 个</span>
        </div>
        <dl class="bulk-report-durations">
          <div class="is-average">
            <dt>平均耗时</dt>
            <dd>{{ duration(timing.avg_seconds) }}</dd>
          </div>
          <div>
            <dt>最快</dt>
            <dd>{{ duration(timing.min_seconds) }}</dd>
          </div>
          <div>
            <dt>最慢</dt>
            <dd>{{ duration(timing.max_seconds) }}</dd>
          </div>
        </dl>
        <p class="bulk-report-note">
          从账号开始执行到结束，{{
            planCheck ? '含自动刷新及链内等待' : '含链内等待'
          }}，不含开始前排队。<template v-if="(numeric(timing.missing_count) || 0) > 0">
            {{ number(timing.missing_count) }} 个已结束账号缺少有效耗时，未计入均值。</template
          ><template v-else-if="numeric(timing.sample_count) === 0"> 暂无有效耗时样本。</template>
        </p>
      </section>
      <section v-if="planCheck" aria-label="AT 检查与自动刷新">
        <div class="bulk-report-section-head">
          <h4>AT 检查与自动刷新</h4>
          <span>按账号去重</span>
        </div>
        <dl class="bulk-report-at-causes">
          <div v-for="[title, key] in atCauses" :key="key" class="bulk-report-minor">
            <dt>{{ title }}</dt>
            <dd>{{ number(at[key]) }}<span>个</span></dd>
          </div>
        </dl>
        <dl class="bulk-report-at-results">
          <div
            v-for="[title, key, variant] in atResults"
            :key="key"
            class="bulk-report-minor"
            :class="variant"
          >
            <dt>{{ title }}</dt>
            <dd>{{ number(at[key]) }}<span>个</span></dd>
          </div>
        </dl>
        <p class="bulk-report-note">
          <template v-if="numeric(at.not_needed_accounts) !== null"
            >未触发刷新 {{ number(at.not_needed_accounts) }} 个 · </template
          >刷新状态待确认 {{ number(at.unknown_accounts) }} 个<template
            v-if="numeric(at.not_executed_accounts) !== null"
          >
            · 未开始执行 {{ number(at.not_executed_accounts) }} 个</template
          >。待确认含执行中尚无结果及历史证据缺失；触发原因可能重叠，远端拒绝不等于本地过期。
        </p>
      </section>
      <section v-else aria-label="功能统计">
        <div class="bulk-report-section-head">
          <h4>功能统计</h4>
          <span>当前查看范围</span>
        </div>
        <BulkBusinessStats :groups="groups" />
      </section>
    </div>
    <div v-if="planCheck" class="bulk-report-distributions">
      <section class="bulk-report-offers" aria-label="优惠结果">
        <div class="bulk-report-section-head">
          <div>
            <h4>优惠结果</h4>
            <p>统计本次查到的可用优惠，按账号去重</p>
          </div>
        </div>
        <dl class="bulk-report-offer-totals">
          <div
            v-for="[title, key, note] in offerTotals"
            :key="key"
            class="bulk-report-metric"
            :class="{'is-accent': key === 'with_offer_accounts'}"
          >
            <dt>{{ title }}</dt>
            <dd>{{ number(offers[key]) }}<span>个</span></dd>
            <small>{{ note }}</small>
          </div>
        </dl>
        <div class="bulk-report-offer-list">
          <div v-for="row in offerRows" :key="String(row.plan)" class="bulk-report-offer-row">
            <div class="bulk-report-offer-line">
              <strong>{{ planName(row.plan) }}</strong
              ><span
                ><b>{{ number(row.accounts) }}</b> 个账号</span
              >
            </div>
            <span class="bulk-report-rail" aria-hidden="true"
              ><span :style="{width: railWidth(row.accounts, maxOffers)}"></span
            ></span>
            <dl class="bulk-report-kind-list">
              <div v-for="kind in rows(row.kinds)" :key="String(kind.kind)">
                <dt>{{ offerName(kind.kind) }}</dt>
                <dd>{{ number(kind.accounts) }}<span>个</span></dd>
              </div>
            </dl>
          </div>
          <p v-if="!offerRows.length" class="bulk-report-empty">
            {{
              numeric(offers.with_offer_accounts) === 0 ? '本次尚未查到可用优惠。' : '暂无优惠套餐明细。'
            }}
          </p>
        </div>
        <p class="bulk-report-note">同一账号可符合多个套餐或优惠，分项数量可能重叠。</p>
      </section>
      <section class="bulk-report-plans" aria-label="当前订阅套餐">
        <div class="bulk-report-section-head">
          <div>
            <h4>当前订阅套餐</h4>
            <p>本次查询确认的套餐状态</p>
          </div>
        </div>
        <dl class="bulk-report-plan-list">
          <div
            v-for="row in plans"
            :key="String(row.plan)"
            :class="{'is-unknown': row.plan === 'unknown'}"
          >
            <dt>{{ planName(row.plan) }}</dt>
            <dd>
              <span>{{ number(row.accounts) }}<small>个</small></span
              ><span
                class="bulk-report-rail"
                :class="{'is-muted': row.plan === 'unknown'}"
                aria-hidden="true"
                ><span :style="{width: railWidth(row.accounts, maxPlans)}"></span
              ></span>
            </dd>
          </div>
          <div v-if="!plans.length" class="bulk-report-empty">暂无套餐结果。</div>
        </dl>
        <p class="bulk-report-note">“尚未确认”包含待完成、失败或缺少套餐记录的账号。</p>
      </section>
    </div>
    <details v-if="planCheck && groups.length" class="bulk-business-details">
      <summary>更多查询统计<span>展开查看</span></summary>
      <BulkBusinessStats :groups="groups" />
    </details>
  </section>
</template>
