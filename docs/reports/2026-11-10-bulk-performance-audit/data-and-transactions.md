# 批量任务数据模型与事务设计

日期：2026-11-10。状态：实施级设计稿，未执行 DDL，未修改业务代码或生产数据。
本文细化[整体方案](design.md)，约束后续迁移、仓储、协调器和统计实现。

## 1. 本篇确定的决策

- PostgreSQL 继续保存唯一业务事实；批次层不复制账号凭据或另建执行器。
- 复用 `operation_batches/tasks/runs/events`；原六种新增结构保留，再增加共用 `operation_projection_outbox` 和控制请求表，分别解决投影锁冲突与控制请求的可靠幂等。
- 所有新增主键为 `BIGINT GENERATED ALWAYS AS IDENTITY`，API 使用十进制字符串；UUID 只用于客户端幂等键、worker 身份与诊断关联。
- 时间使用 `TIMESTAMPTZ`，计数、版本、ordinal 使用 `BIGINT`；账号原日期筛选继续使用当前日历日期语义。
- 首轮目标引用预览固定名单，后台才创建 target_round；重跑轮也有独立固定成员名单，不能保存动态“失败”条件后分页重新执行筛选。
- 业务事实、轮次结果、批次当前结果分开；当前结果只认该目标最后一次已经固定成功的请求轮次。
- 事实写事务只追加投影事件，不获取批次汇总锁；投影事务不锁账号、Task、Run 或业务许可。
- 同一 managed 账号链的所有写入口采用本篇锁顺序，不能把新锁包在旧 `retry_runtime_task()` 外就声称安全。

现有 `operation_batch_items` 要求 task/run 非空且 ordinal 唯一，不能代替预执行目标表。
现有 `_refresh_batch()` 按 root task 最新状态汇总；managed 批次必须走独立投影分支，旧算法不得写其计数。

## 2. 数据归属与不变量

| 数据 | 唯一写入者 | 可否重建 |
|---|---|---|
| 预览名单、筛选证据、基线 | selection 冻结事务 | 不重查当前账号来重建历史名单 |
| 批次控制与轮次请求 | 批次协调仓储 | 请求事实保留 |
| 目标提交、链启动/关闭事实 | managed 提交/执行协调仓储 | 可由关联事实核对，不由页面推断 |
| 账号当前状态、任务/Run/依赖 | 原领域服务经 managed 存储入口 | 沿现有领域规则 |
| target_round 展示结果、统计贡献 | bulk_target 投影器 | 可从精确 owned Run 重建 |
| 每轮计数、批次当前计数 | 同一 bulk_target 投影事务 | 可重建、带修订号 |
| 当前任务列表投影 | task_read_model 消费者 | 与批次投影相互独立 |

必须始终满足：固定目标不重复；owned Run 只属于一个 target_round；外部 blocker 不成为 owned。
每个视图每个目标只落一个计数桶。终态证据允许合法修订，修订旧轮不能覆盖当前新轮归属。
同一目标可以有后续请求轮等待，但同一时刻最多一个账号链执行；后轮不得提前改写前轮的业务身份。

## 3. 伪 DDL 与字段约束

以下 SQL 使用未限定 schema 的名称便于阅读；实现必须使用项目 schema 工具。
枚举用 `TEXT + CHECK`，避免 PostgreSQL enum 迁移阻塞；所有 JSONB 要求顶层 object。
伪DDL只在query_spec展示JSON类型CHECK；实际迁移必须为其余JSONB展开同一约束，不能仅依赖应用校验。
下文 `counts` 是固定十一桶对象：pending_submit、waiting_account、queued、running、waiting、success、partial_success、failed、not_executed、cancelled、attention_required。
`metrics` 是按动作版本允许的有限统计维度，不接收任意客户端键。

### 3.1 选择请求与固定目标

```sql
CREATE TABLE operation_selections (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  selection_kind TEXT NOT NULL CHECK (selection_kind IN ('account_query','explicit_ids','batch_targets','retry_members')),
  request_key TEXT NOT NULL UNIQUE,
  request_hash TEXT NOT NULL,
  query_version INTEGER NOT NULL CHECK (query_version > 0),
  query_spec JSONB NOT NULL CHECK (jsonb_typeof(query_spec)='object'),
  action_key TEXT NOT NULL,
  action_version INTEGER NOT NULL CHECK (action_version > 0),
  selection_revision BIGINT NOT NULL DEFAULT 0,
  parameters JSONB NOT NULL DEFAULT '{}', parameters_hash TEXT NOT NULL,
  config_revision TEXT NOT NULL, config_snapshot JSONB NOT NULL DEFAULT '{}',
  status TEXT NOT NULL CHECK (status IN ('preparing','ready','failed','expired','consumed')),
  total_count BIGINT CHECK (total_count >= 0),
  selected_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ NOT NULL,
  consumed_by_batch_id BIGINT REFERENCES operation_batches(id) ON DELETE RESTRICT,
  consumed_by_round_id BIGINT,
  basis_batch_id BIGINT REFERENCES operation_batches(id) ON DELETE RESTRICT,
  observed_summary_revision BIGINT, basis_summary_revision BIGINT,
  counts_changed_since_request BOOLEAN NOT NULL DEFAULT FALSE,
  owner_id TEXT, lease_until TIMESTAMPTZ, fence BIGINT NOT NULL DEFAULT 0,
  attempts INTEGER NOT NULL DEFAULT 0, next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  error_code TEXT, error_detail JSONB NOT NULL DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK (status NOT IN ('ready','consumed') OR (selected_at IS NOT NULL AND total_count IS NOT NULL)),
  CHECK (NOT (consumed_by_batch_id IS NOT NULL AND consumed_by_round_id IS NOT NULL))
);

CREATE TABLE operation_selection_targets (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  selection_id BIGINT NOT NULL REFERENCES operation_selections(id) ON DELETE RESTRICT,
  target_kind TEXT NOT NULL CHECK (target_kind IN ('account','credential')),
  target_id BIGINT NOT NULL, ordinal BIGINT NOT NULL CHECK (ordinal > 0),
  canonical_target_id BIGINT REFERENCES operation_selection_targets(id) ON DELETE RESTRICT,
  source_target_round_id BIGINT, source_run_id_snapshot BIGINT,
  display_snapshot JSONB NOT NULL DEFAULT '{}',
  match_evidence JSONB NOT NULL DEFAULT '{}', baseline JSONB NOT NULL DEFAULT '{}',
  latest_requested_round_id BIGINT,
  current_contribution JSONB NOT NULL DEFAULT '{"pending_submit":1}',
  current_projection_revision BIGINT NOT NULL DEFAULT 0,
  UNIQUE(selection_id,target_kind,target_id), UNIQUE(selection_id,ordinal)
);
```

根 selection 的 canonical_target_id 为 NULL，其 id 就是 canonical target；重跑成员必须引用同批根目标。
`target_id` 不直接外键到账号/凭证表，删除账号不得级联删除批次历史，也不能为历史引用阻断正常删除。
`source_run_id_snapshot` 是历史来源标识，非 latest_run 动态引用；详细 Run 的保留由 3.4/11 节处理。
三个 `current_* / latest_*` 列是可变投影，其余目标列一旦 selection ready 就不可修改。
最初 `latest_requested_round_id=NULL` 表示 controls.initial_round_id；创建批次无需逐项更新十万个目标。
显式 ID 按原始顺序去重；非法格式在请求校验拒绝，格式合法但不存在的ID通过请求集合LEFT JOIN保留身份与account_missing证据。
同固定账号新建批次使用selection_kind=batch_targets、basis_batch_id和query_spec来源选择条件，生成全新根目标（canonical=NULL）。
它复制账号身份并读取新基线；来源批次/目标ID只留追溯证据，不复用旧owned Run、不沿用旧target_round或latest指针。

### 3.2 批次控制和轮次

```sql
CREATE TABLE operation_batch_controls (
  batch_id BIGINT PRIMARY KEY REFERENCES operation_batches(id) ON DELETE RESTRICT,
  manager_version INTEGER NOT NULL CHECK (manager_version=1),
  selection_id BIGINT NOT NULL UNIQUE REFERENCES operation_selections(id) ON DELETE RESTRICT,
  initial_round_id BIGINT,
  action_key TEXT NOT NULL, action_version INTEGER NOT NULL,
  result_version INTEGER NOT NULL, parameters JSONB NOT NULL, config_snapshot JSONB NOT NULL,
  config_revision TEXT NOT NULL,
  request_key TEXT NOT NULL UNIQUE, request_hash TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('active','cancel_requested','stop_requested','ended')),
  control_revision BIGINT NOT NULL DEFAULT 1,
  summary_revision BIGINT NOT NULL DEFAULT 0,
  next_round_no BIGINT NOT NULL DEFAULT 2,
  desired_workers INTEGER NOT NULL CHECK (desired_workers > 0),
  counts JSONB NOT NULL, metrics JSONB NOT NULL DEFAULT '{}',
  projected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  archived_at TIMESTAMPTZ, purge_started_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE operation_batch_rounds (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  batch_id BIGINT NOT NULL REFERENCES operation_batch_controls(batch_id) ON DELETE RESTRICT,
  round_no BIGINT NOT NULL CHECK (round_no > 0),
  request_kind TEXT NOT NULL CHECK (request_kind IN ('initial','manual_retry')),
  request_key TEXT NOT NULL, request_hash TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('preparing','active','settling','completed','failed')),
  member_selection_id BIGINT REFERENCES operation_selections(id) ON DELETE RESTRICT,
  target_count BIGINT CHECK (target_count >= 0),
  materialized_count BIGINT NOT NULL DEFAULT 0 CHECK (materialized_count >= 0),
  materialization_cursor BIGINT NOT NULL DEFAULT 0,
  unmaterialized_bucket TEXT NOT NULL DEFAULT 'pending_submit'
    CHECK (unmaterialized_bucket IN ('pending_submit','cancelled')),
  control_revision BIGINT NOT NULL DEFAULT 1,
  control_action TEXT NOT NULL DEFAULT 'none' CHECK (control_action IN ('none','cancel_not_started','request_stop')),
  control_command_id BIGINT,
  counts JSONB NOT NULL DEFAULT '{}', metrics JSONB NOT NULL DEFAULT '{}',
  summary_revision BIGINT NOT NULL DEFAULT 0,
  owner_id TEXT, lease_until TIMESTAMPTZ, fence BIGINT NOT NULL DEFAULT 0,
  next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  completion_reason TEXT, preparation_error_code TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(), frozen_at TIMESTAMPTZ, completed_at TIMESTAMPTZ,
  UNIQUE(batch_id,round_no), UNIQUE(batch_id,request_key),
  CHECK (target_count IS NULL OR materialized_count <= target_count)
);
```

迁移第二步增加循环外键：controls.initial_round_id、selection.consumed_by_round_id 和 target.latest_requested_round_id引用rounds，
target.source_target_round_id引用target_rounds，round.control_command_id引用下述commands；均DEFERRABLE/RESTRICT。
首轮 row 可先插入，再同事务填 initial_round_id；事务结束必须完整。
`state=failed` 仅指轮次准备/协调无法完成，账号执行失败仍是 completed 加失败计数。
公开结果中的 `execution_state` 与 counts 分开，不把“轮次 completed”画成全部成功。
selection和controls的config_snapshot只保存非密钥值及现有密文runtime配置的版本引用，不能复制secret进批次JSON。
配置引用的保留期覆盖活跃执行及重跑所需版本，读取时仍由现有密文配置服务解密。

### 3.3 目标轮次：提交事实与展示投影分列

```sql
CREATE TABLE operation_batch_target_rounds (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  batch_id BIGINT NOT NULL REFERENCES operation_batch_controls(batch_id) ON DELETE RESTRICT,
  round_id BIGINT NOT NULL REFERENCES operation_batch_rounds(id) ON DELETE RESTRICT,
  member_target_id BIGINT NOT NULL REFERENCES operation_selection_targets(id) ON DELETE RESTRICT,
  canonical_target_id BIGINT NOT NULL REFERENCES operation_selection_targets(id) ON DELETE RESTRICT,
  ordinal BIGINT NOT NULL,
  admission_state TEXT NOT NULL CHECK (admission_state IN
    ('pending_submit','waiting_account','submitted','not_executed','cancelled')),
  chain_state TEXT NOT NULL DEFAULT 'not_started'
    CHECK (chain_state IN ('not_started','started','waiting','closed')),
  chain_started_at TIMESTAMPTZ, chain_closed_at TIMESTAMPTZ,
  source_revision BIGINT NOT NULL DEFAULT 0,
  applied_revision BIGINT NOT NULL DEFAULT 0,
  owner_id TEXT, lease_until TIMESTAMPTZ, fence BIGINT NOT NULL DEFAULT 0,
  next_prepare_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  blocker_task_id_snapshot BIGINT, blocker_run_id_snapshot BIGINT,
  retry_from_target_round_id BIGINT REFERENCES operation_batch_target_rounds(id) ON DELETE RESTRICT,
  outcome TEXT NOT NULL DEFAULT 'pending_submit',
  result_version INTEGER NOT NULL, result JSONB NOT NULL DEFAULT '{}',
  applied_contribution JSONB NOT NULL DEFAULT '{"pending_submit":1}',
  reason_code TEXT, projected_at TIMESTAMPTZ,
  next_execution_generation BIGINT NOT NULL DEFAULT 1,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(round_id,canonical_target_id), UNIQUE(round_id,ordinal), UNIQUE(member_target_id,round_id),
  CHECK (applied_revision <= source_revision)
);
```

`chain_state` 是执行协调事实，不由异步投影推测；关闭需所有 owned 运行终结且无待创建续接。
没有Run的not_executed/cancelled目标也必须在事实事务中置chain_state=closed并记录chain_closed_at，不能靠摘要假设已关闭。
`source_revision` 仅由持有该 target_round 锁的 managed 写入口递增；一次事务多次变化只需一个新版本。
`outcome/result/applied_*` 是展示投影，不代替 admission/chain事实，也不决定是否允许旧 worker 写回。
一个轮次的来源成员只能来自其 member_selection；同批根目标关系由仓储检查，并用约束触发器阻止越批绑定。

### 3.4 运行关联与共用投影事件

```sql
CREATE TABLE operation_batch_run_links (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  target_round_id BIGINT NOT NULL REFERENCES operation_batch_target_rounds(id) ON DELETE RESTRICT,
  task_id BIGINT REFERENCES operation_tasks(id) ON DELETE SET NULL,
  run_id BIGINT REFERENCES operation_runs(id) ON DELETE SET NULL,
  task_id_snapshot BIGINT NOT NULL, run_id_snapshot BIGINT NOT NULL,
  step_key TEXT NOT NULL, execution_generation BIGINT NOT NULL,
  relation TEXT NOT NULL CHECK (relation IN ('owned_root','owned_child','owned_continuation','external_blocker')),
  archive_state TEXT NOT NULL DEFAULT 'live' CHECK (archive_state IN ('live','pending','archived')),
  result_archive_ref TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(target_round_id,run_id_snapshot,relation)
);
CREATE UNIQUE INDEX uq_bulk_owned_run ON operation_batch_run_links(run_id_snapshot)
  WHERE relation IN ('owned_root','owned_child','owned_continuation');
CREATE UNIQUE INDEX uq_bulk_owned_generation ON operation_batch_run_links(target_round_id,step_key,execution_generation)
  WHERE relation IN ('owned_root','owned_child','owned_continuation');

CREATE TABLE operation_projection_outbox (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_key TEXT NOT NULL UNIQUE,
  consumer_kind TEXT NOT NULL CHECK (consumer_kind IN ('bulk_target','task_read_model')),
  target_round_id BIGINT REFERENCES operation_batch_target_rounds(id) ON DELETE RESTRICT,
  task_id BIGINT REFERENCES operation_tasks(id) ON DELETE SET NULL,
  task_id_snapshot BIGINT,
  source_kind TEXT NOT NULL, source_id BIGINT NOT NULL, source_revision BIGINT NOT NULL,
  event_kind TEXT NOT NULL,
  available_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  attempts INTEGER NOT NULL DEFAULT 0, error_code TEXT,
  processed_at TIMESTAMPTZ, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CHECK ((consumer_kind='bulk_target' AND target_round_id IS NOT NULL)
    OR (consumer_kind='task_read_model' AND task_id_snapshot IS NOT NULL))
);
```

事件不存 Token/完整结果，仅存实体与版本。`event_key=consumer:source_kind:source_id:revision:event_kind`。
现有 Run 添加 `projection_revision BIGINT NOT NULL DEFAULT 0`，任务读模型每次有效状态更新递增该值。
bulk 消费以 target_round.source_revision 为准，单 Run 版本不覆盖组合子链总版本。
一项事实需要两种投影时写两个不同 consumer 的事件；不能一个事件被首个消费者标完成后另一消费者漏处理。
外部 blocker 不递归触发本轮结果，只触发重新核验可执行条件；不持有其业务锁，不迁移它的 batch_id。

### 3.5 持久控制请求

```sql
CREATE TABLE operation_batch_control_commands (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  batch_id BIGINT NOT NULL REFERENCES operation_batch_controls(batch_id) ON DELETE RESTRICT,
  request_key TEXT NOT NULL, request_hash TEXT NOT NULL,
  action TEXT NOT NULL CHECK (action IN ('cancel_not_started','request_stop')),
  scope_kind TEXT NOT NULL CHECK (scope_kind IN ('batch','round')),
  scope_round_id BIGINT REFERENCES operation_batch_rounds(id) ON DELETE RESTRICT,
  through_round_no BIGINT NOT NULL,
  expected_control_revision BIGINT NOT NULL, result_control_revision BIGINT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('accepted','settling','completed','failed')),
  next_round_id BIGINT, settlement_cursor BIGINT NOT NULL DEFAULT 0,
  owner_id TEXT, lease_until TIMESTAMPTZ, fence BIGINT NOT NULL DEFAULT 0,
  error_code TEXT, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), completed_at TIMESTAMPTZ,
  UNIQUE(batch_id,request_key),
  CHECK ((scope_kind='round')=(scope_round_id IS NOT NULL))
);
```

请求先按key/hash复用原命令，再检查expected_revision；已完成请求重放不能因控制版本已变化变成409。
batch范围在受理时固定through_round_no，新建后续轮不受旧命令影响；round范围只作用指定轮。
取消与停止为单调升级：同轮request_stop不能被迟到cancel_not_started降级。
request_stop包含取消未开始效果，阻止新账号展开/首次claim，再对本范围已开始owned链协作停止；不停止external_blocker。
具体结算检查round.control_command_id/动作和命令fence，游标只推进已经提交的结算块。

### 3.6 必需索引与约束检查

```sql
CREATE INDEX idx_selection_prepare ON operation_selections(next_attempt_at,id) WHERE status='preparing';
CREATE INDEX idx_selection_expire ON operation_selections(expires_at,id) WHERE status IN ('ready','failed');
CREATE INDEX idx_selection_canonical ON operation_selection_targets(canonical_target_id,selection_id);
CREATE INDEX idx_round_prepare ON operation_batch_rounds(next_attempt_at,id) WHERE state IN ('preparing','active');
CREATE INDEX idx_target_prepare ON operation_batch_target_rounds(next_prepare_at,id)
  WHERE admission_state IN ('pending_submit','waiting_account') AND chain_state='not_started';
CREATE INDEX idx_target_page ON operation_batch_target_rounds(round_id,outcome,ordinal,id);
CREATE INDEX idx_target_current ON operation_batch_target_rounds(canonical_target_id,round_id DESC);
CREATE INDEX idx_run_link_run ON operation_batch_run_links(run_id) WHERE run_id IS NOT NULL;
CREATE INDEX idx_projection_pending ON operation_projection_outbox(consumer_kind,available_at,id)
  WHERE processed_at IS NULL;
CREATE INDEX idx_control_settle ON operation_batch_control_commands(state,id)
  WHERE state IN ('accepted','settling');
```

selection/ordinal、round/ordinal 已有唯一索引，不再重复创建。新批次列表使用现有 batches 创建时间索引，必要时加 `(batch_type,created_at DESC,id DESC)`。
各 CHECK/关系校验由真实 PostgreSQL 约束测试覆盖；不是只在 Python assert 中成立。
不对全部 JSONB 建 GIN；动作筛选确需某结果字段时增加有类型列或明确表达式索引并验查询计划。

## 4. 锁顺序：不能沿用旧函数的混合顺序

现状 create_runtime_task 先账号，retry 先 task 后账号，claim 在准入锁内先 Run 再账号；不能直接组合。
managed 任务新增 conn-aware 仓储原语，旧 HTTP/任务中心入口识别管理标记后转发，禁止回落旧写路径。
以下顺序用于新 managed 数据，不要求本轮改变注册驱动内部流程。

| 事务类型 | 锁顺序 | 禁止事项 |
|---|---|---|
| 账号查询/显式ID选择冻结 | selection行 → 新插入目标 | 不取账号行锁、admission 或批次投影锁 |
| 原批来源选择冻结 | 来源批projection guard → controls → rounds → selection → canonical → target_round | 不先持selection锁再回头等待projection guard |
| 重跑冻结/计数/控制结算 | `bulk_projection:<batch>` advisory → controls → rounds ID升序 → canonical目标ID升序 → target_round ID升序 | 不锁账号/Task/Run/许可 |
| managed首次提交/首次claim | admission（如需）→ controls FOR SHARE → target_round → 账号行 → Task → Run → dependency | 不在已有业务锁后补取admission/control/投影锁 |
| managed续接/结束/事实更新 | target_round → 账号行（需要时）→ Task → Run → dependency → append outbox | 不取得controls/round计数/投影锁 |
| Run历史清理 | 不处理managed活跃引用；已归档对象按独立维护窗口 | 不持Run锁后等待批次投影锁 |

同层多行按 ID 升序；需要处理同账号多个 task/run 时一次定位完整集合后按顺序锁定。
事务持锁期间不请求网络、不等待线程槽、不写磁盘日志。JSONL 在事实提交后写，数据库事件保证可恢复。
现有 `permits.admission_lock()` 是所有需准入事务的第一把锁；新 control 检查不得放在它前面。
持admission时control/target/其他可能争锁行必须NOWAIT或极短lock_timeout；失败立即回滚整个准入事务释放admission，之后才退避。
禁止在admission内睡眠、局部保存点重试或等待大批冻结/取消事务；纯展开持久化不申请admission。
事实事务追加 outbox 后提交，投影器只读取已提交 Run 快照，不对 Run `FOR UPDATE`。
由此不存在“事实Run锁→target等待；投影target锁→Run等待”的环。
managed父子均属于同一 target_round；跨目标依赖一律 external_blocker，只读，不做跨账号递归收口。
目标物化也必须走projection guard→controls→round→canonical目标顺序，初始化贡献、materialized_count与cursor同事务。
物化事务不创建Task/Run；随后独立managed提交事务才触达业务行，禁止持projection guard调用领域提交。

投影候选发现不先长时间持 outbox 锁：普通 SELECT 找 batch，取该批 guard 后再锁该批待处理 outbox。
所有 bulk 消费者使用相同 guard，避免两个消费者互持事件行再争不同批。task_read_model 使用独立 task guard。
单个 managed 状态/心跳更新也必须遵守 target-first；未经改造的旧 Run-first 写入口不得用于新批次。

## 5. 预览冻结与首轮受理事务

### 5.1 selection请求与领取

请求事务先按request_key/hash查回执；新请求校验expected_config_revision，固定白名单parameters及规范化parameters_hash、配置版本/引用，再INSERT。
同键hash不同返回冲突，相同返回原selection，不因配置后来变化破坏原回执幂等。
协调worker用FOR UPDATE SKIP LOCKED短事务领取preparing selection，写owner、lease_until、fence=fence+1后提交。
下列SQL只用于account_query/explicit_ids；retry_members与batch_targets先释放领取锁，再按来源批guard顺序冻结。
冻结只读账号字段，使用一次 statement snapshot；失败整次回滚，不能留半份 ready 名单。

```sql
BEGIN;
SELECT * FROM operation_selections WHERE id=:id FOR UPDATE;
-- 校验 status='preparing'、owner、fence；本事务内不释放选择行锁。
WITH candidates AS MATERIALIZED (
  SELECT a.id, a.email, a.created_at, a.account_promotion_value
  FROM registered_accounts a WHERE /* 共享谓词，参数绑定 */
  ORDER BY /* 白名单顺序 */, a.id LIMIT :optional_limit
), inserted AS (
  INSERT INTO operation_selection_targets(selection_id,target_kind,target_id,ordinal,display_snapshot,match_evidence)
  SELECT :id,'account',id,row_number() OVER (ORDER BY /* 同一顺序 */,id),
         jsonb_build_object('email',email),jsonb_build_object('created_at',created_at,'promotion',account_promotion_value)
  FROM candidates RETURNING id
)
UPDATE operation_selections SET total_count=(SELECT count(*) FROM inserted),
  selected_at=statement_timestamp(),status='ready',selection_revision=1,owner_id=NULL,lease_until=NULL,updated_at=now()
WHERE id=:id AND owner_id=:owner AND fence=:fence;
COMMIT;
```

实际SQL中排序所需字段必须在 candidates 内显式投影；LIMIT NULL 表示全部，不插入用户原始排序文本。
超时只回滚这次冻结，ready只能在完整提交后出现；`selected_at`表示成功语句的快照时点，不表示点击时间。
零匹配也可 ready/total_count=0，创建返回 `selection_empty`；不自动扩大条件。
ready响应附预检所用公开配置、config_revision和parameters_hash；不强制COUNT全部匹配，只对实际固定插入行精确计数。
预检使用已固定的参数/配置引用；创建不得拿旧预检换用新参数，修改参数或配置需新建selection重新预览。
batch_targets的result_filter在来源批projection guard下固定来源成员和basis_revision，再以这些身份读取新基线；显式成员不扩充。

### 5.2 创建批次：固定数量的写入

事务先按controls.request_key查询原回执并比较hash，再锁ready selection核验TTL/selection_revision/动作版本。
校验创建的规范化parameters_hash等于selection，expected_config_revision同时等于selection版本及当前有效设置版本。
参数不匹配或配置已变返回明确409且不消费selection，要求重新预览；账号动态变化不阻断创建。
随后新插batches、controls、round1，初始summary_revision=0，首个有效投影增量后递增。
round1.member_selection_id 指向原 selection，target_count=N，counts.pending_submit=N，其余0；controls当前计数同样初始化。
设置 initial_round_id，selection改consumed并绑定batch，同事务提交。**不插N条target_round、不修改N条根目标。**
请求回执丢失时request_key返回已有batch；同一selection被另一个创建请求消费时返回selection_consumed并附原batch引用，不新建第二批。
并发首次提交的唯一冲突在保存点回滚后读取已提交原回执；不能让异常路径误报selection过期或全部失败。
首轮展开使用固定 selection ordinal 游标，每块生成至多100个 target_round，初始贡献取 round.unmaterialized_bucket。
物化后的事实变化由第8节投影计算计数差量；物化pending本身不应把pending再加一次。

## 6. 重跑成员冻结与当前归属

API先检查幂等回执，再创建preparing round和preparing retry selection，保存原批、指定视图/条件或显式目标、observed_summary_revision。
result_filter按照后台冻结时指定视图实际满足条件的原批目标选择；observed_revision仅用于审计，不做严格CAS以免运行中持续变化导致永远重试。
记录实际basis_summary_revision、selected_at及counts_changed_since_request；页面明确“以固定时点的结果为准”。
显式target ID集合不增加新成员；需要严格所见集合时先消费ready选择快照。零成员轮完成，completion_reason=empty，不发业务任务。
冻结后台事务只处理批次投影与成员，不持全局准入锁，不锁真实账号/Run：

1. 取批次projection guard，锁controls，检查本次round仍preparing、未取消且没有更小round_no的preparing轮；依序锁round、selection和根目标。
2. 从已提交的当前贡献选择成员，插入retry selection_targets，记录canonical_target与原target_round、来源Run快照。
3. 若原目标仍有未关闭账号链，该成员保留但标等待前轮；不复制其活跃Run，不阻断其余成员。
4. 在同一事务将每个成员的latest_requested_round_id改为新round，current_contribution切为pending_submit。
5. controls当前计数合并减旧贡献、加pending；round计数初始化pending=N，selection ready/consumed、round active。
6. 递增summary_revision，提交后才对外宣布最终成员数与当前归属改变。

同批preparing轮必须按round_no顺序发布；前轮已冻结、准备失败或取消后，后轮才能发布，防止latest从3回退到2。
两个同时请求相同目标的不同轮次按round_no先后形成请求队列；同key只一个round。
后一轮可成为当前视图待提交，但领取必须等所有更早已冻结轮次对该目标的链关闭；不能抢占或跳过前轮。
比较等待关系使用canonical成员及round_no索引；前轮成员尚未物化也视为未关闭，除非其未物化桶已被取消结算。
不能只查已存在target_round，否则后轮可能越过前轮未展开目标；不扫描该账号的全部历史Run。
后轮取消仅取消该轮请求；前轮合法结果仍留在前轮，当前视图显示后轮取消，不自动倒退latest指针。

所有人工重跑入口都走上述流程。自动dependency_resume使用原round，不创建新用户轮次。
同批manual_retry和dependency_resume均沿controls已冻结的功能参数/配置版本，不清空原恢复检查点；全局实时许可只限制容量。
managed适配器显式注入原snapshot，不能调用旧retry后悄悄capture新配置；要用新配置须按同名单新建批次。
适配器必须返回真正新Run；reused、busy、dependency_stale分别等待/复用原受理，不增加“已创建执行”计数。
人工重跑不得直接复制旧Run.data里的round上下文；conn-aware retry由调用方传入已冻结的新target_round。

## 7. 有界展开、提交与首次执行

窗口统一按已建未结束owned Run计数，包含根/子/续接，不含external_blocker；数值与预留规则以[性能篇第2节](performance-and-operations.md#2-服务结构与容量)为单一来源。
已开始账号的必要子步骤与续接优先获得预留窗口，仍遵守真实业务许可；批次间公平补充。
窗口是准备预算，不是目标总数上限。每轮最多扫描1000个等待候选，等待记录可继续持久化，不生成Run、不占业务窗口。
游标越过忙账号继续准备后续目标，并独立索引退避重查；不能前1000项忙就永久阻挡后续可执行账号。
所有目标都被持久名单覆盖，窗口关闭不丢目标；调小并发不取消已开始账号链。

准备worker领取target_round时写owner/lease/fence，提交事务再校验fence；先批量读取窄字段，不先逐项get_account。
事务按第4节顺序核验控制、前轮链、账号存在/状态及领域资格，再写Task/Run、账号queued状态、owned link。
同时将admission_state=submitted，source_revision递增，并append bulk outbox；一块提交后统一唤醒dispatcher。
约束冲突可用保存点局部回滚，记waiting_account及blocker快照；系统连接故障整块回滚。
首次创建持久source_id使用`bulk:<batch>:<target>:<action>:<step>`，同一逻辑任务重放命中原Task。
人工重跑沿原Task新增Run，不按新round source_id另建Task；target锁下分配稳定generation，owned_generation唯一索引保证提交回执丢失可找回。
若前轮在Task建立前失败，则以同batch/canonical target的稳定source_id创建第一个Task，再关联本次新round；不能假设所有失败项已有Task。
自动续接另取新的generation但沿原round；同一逻辑阶段的重放使用已持久generation，不能每次请求自增后重复发起。
提交成功但链接未写不允许提交事务；存在外层不支持conn的服务必须先改造，不用补偿猜关联。

首次claim在admission后锁controls和target_round，检查没有取消该轮、前轮已关闭、fence匹配，再取得业务许可并启动。
`chain_started_at`在首次真正认领执行事务中写入；创建queued Run不算账号链开始。
一旦started，后续owned_child/owned_continuation承接原target_round，可在cancel_not_started模式下继续；request_stop则沿既有协作取消收口。
链关闭由协调器核验owned执行与持久依赖已收口后写事实；不因某父Run临时partial或queued=0关闭。
关闭后禁止自动再生成owned子任务；合法新用户重跑必须走新round，原结果补证据仅更新旧轮结果版本。

## 8. 事实事件、投影与计数算法

managed写入口持target_round锁，完成真实状态变化后做：

```sql
UPDATE operation_batch_target_rounds
SET source_revision=source_revision+1 WHERE id=:target_round RETURNING source_revision;
INSERT INTO operation_projection_outbox(event_key,consumer_kind,target_round_id,
  source_kind,source_id,source_revision,event_kind)
VALUES (:event_key,'bulk_target',:target_round,'target_round',:target_round,:version,'fact_changed')
ON CONFLICT(event_key) DO NOTHING;
```

这与Run/账号/依赖事实同事务提交。原服务尚未支持事务钩子时不可宣称可靠接入；本轮不采用“提交后内存通知”兜底。
日志单独到达不推动成功/失败计数；只消费有业务含义的状态/结果/依赖修订。
outbox不能用“最大已读ID”当完成游标：较小ID事务可能较晚提交，消费者必须按processed_at IS NULL查找。

bulk projector每次最多处理一个batch的100个target，步骤如下：

1. 发现候选batch，取projection guard，锁controls、涉及round、canonical目标、target_round（均按ID）。
2. 锁该批本次待消费事件；每目标读取当前source_revision与所有owned Run/依赖的已提交窄结果。
3. 在target锁下业务写者无法再改该目标；以当前完整事实计算规范结果new及有限贡献vector。
4. `delta_round=new-applied_contribution`；按round合并差量。只有目标effective latest round等于本轮，才更新根目标current贡献和controls差量。
5. 同事务更新结果、applied_revision=source_revision、贡献、摘要revision/projected_at，并标处理source_revision以内事件已完成。
6. 迟到较旧事件只标完成；新事实的新事件留给下一轮。失败事务全部回滚，不会只加计数而未更新applied版本。

终态结果修订在同事务追加现有operation_events，event_type=`bulk.result_revised`，关联确切task/run与target_round，
detail仅记录old/new revision、规范结果变化字段、reason_code及来源事件ID；event_uuid稳定去重，不写凭据或完整响应。
没有owned Run的not_executed/cancelled终态不允许原位覆写为另一业务结果；账号状态变化通过新轮表达。
控制导致的取消由持久command、范围和target事实版本追溯，不调用要求task_id非空的operation_events伪造执行记录。

事实写者不取projection guard；projector不锁Run，读取时已先持target锁，所有managed事实更新也先锁target，得到一致组合事实。
外部blocker状态只用于下一次预检，不直接参与本轮成功贡献；来源修订无法证明归属时记明确诊断，不猜测。
向量必须含且仅含一个公共桶，值为1，业务metrics独立；单账号多国家计数不得混入账号目标恒等式。
批次计数允许短时滞后但同一响应由一个REPEATABLE READ只读事务取摘要及revision，不混读不同版本。
关闭判断需物化/取消覆盖完成、所有链关闭且source_revision=applied_revision；待确认是结果类别，不是自动创建新执行的许可。

## 9. 隐式pending、取消与统计不重不漏

`U=target_count-materialized_count` 是未物化数。其贡献已经包含在round.counts的unmaterialized_bucket内。
物化时target_round.applied_contribution必须初始化为该桶，增加materialized_count不再改计数。
首次状态变化再从此基线做差量，避免首轮总数翻倍。

“取消未开始”短事务先复用同key命令，再CAS controls.control_revision、保存control command并标记其范围内round控制动作。
expected_revision冲突整体回滚且不消费成功幂等键；batch命令固定through_round_no，round命令只影响指定轮。
后台先在projection guard下处理每轮的未物化贡献，提交后另走managed事实事务取消已有执行：

- 将U从pending_submit一次移到cancelled，round.unmaterialized_bucket改cancelled；记录结算control_revision。
- controls当前计数只转移仍以本轮为latest的未物化成员；重跑冻结也用同guard，集合不会在结算中变化。
- 同时将未物化成员对应根目标的current_contribution设cancelled，使用集合UPDATE；不创建U个Run。
- 已物化目标必须先释放projection guard，再按target→账号/Task/Run顺序逐块取消；queued取消与target事实同事务追加outbox。
- 后续投影事务才结算这些真实取消，不能在控制受理时提前计取消；不持projection guard调用任何领域取消入口。
- 已started链及必需续接不被cancel_not_started截断；request_stop同时执行全部未开始取消步骤，并对已开始owned链走现有协作停止协议。

取消可能需要O(N)轻量根目标投影更新，但由后台完成，绝不把这个成本藏进500毫秒受理事务。
重复结算凭control_revision和原unmaterialized_bucket判断，不能二次把U从pending减掉。
取消之后为查看明细而物化目标时，直接生成cancelled/applied cancelled和chain_state=closed，不另发计数增量。
batch范围命令更新controls.state；单轮命令不阻断其他轮。用户明确新建轮记录新控制代次，不受旧through_round_no约束。
取消preparing重跑轮不会切换latest指针；提交state=completed、completion_reason=cancelled_before_freeze、target_count=NULL。
对应selection结束为failed/error_code=selection_cancelled，避免准备worker稍后重领；该轮显示准备已取消，未知目标数不能伪报0成功。

## 10. owner、租约、代次与故障恢复

协调任务不发外部业务请求，可以凭DB租约与fence安全重领；业务worker仍遵守现有execution_id/许可/身份恢复规则。
selection/round/target准备租约初值30秒，正常每10秒续租；冻结事务持selection行锁期间，其他worker SKIP LOCKED，不抢同一请求。
租约检查使用数据库now()；续租 `WHERE owner_id=:owner AND fence=:fence`，更新0行即停止本地后续写。
fence只递增不复用；超时重领前必须确认没有持锁事务。旧worker提交时owner/fence条件失败，整块回滚。
managed实际执行继续使用既有execution_id；协调fence不授予网络执行资格，也不因为准备超时就复制正在运行的任务。

| 崩溃位置 | 已提交事实 | 恢复动作 |
|---|---|---|
| selection请求提交后、冻结前 | preparing请求 | 到期重领，重新执行一次完整固定语句 |
| 冻结中、ready提交前 | 事务回滚，无半份名单 | 新fence重做；最终selected_at按成功那次 |
| ready已提交、HTTP回执丢失 | 完整名单 | 同request_key读取原selection |
| batch创建提交后回执丢失 | controls+round1+消费归属 | 同key返回原batch，不重复消费 |
| 首轮物化一半 | 固定名单、cursor、已建target_round | 按唯一键继续，基线计数不重复加 |
| Task插入后关联写入前 | 同事务未提交 | 回滚；稳定source_id重放，无孤儿执行 |
| Task/link/outbox提交后唤醒前 | durable queued+关联+事件 | 周期dispatcher和projector自动发现 |
| projector改计数时崩溃 | 同事务全回滚 | 重读未处理事件，delta仍从旧applied算 |
| 取消转移U后崩溃 | revision+桶+贡献同事务 | 同版本不重复转移，继续取消已物化项 |
| 子Run结束、父续接未调度 | 持久dependency+owned上下文 | 原round生成continuation，不能生成人工新轮 |
| 业务成功、JSONL写入失败 | DB结果和outbox完整 | 结果照常成功，日志故障独立诊断 |

恢复扫描只读索引范围，不全表检查所有批次；每周期有时间/行数预算，准备、控制结算、投影各自有受限worker。
投影恢复不依赖进程内Event，Event仅降低发现延迟；部署重启必须启动这三类恢复worker并纳入readiness。

## 11. 账号删除、归档与Run历史保留

账号删除不改固定名单，未开始目标在下一次预检记account_missing；正在执行沿现有取消/写回规则，不伪造成功。
已结束目标保留当时结果、必要展示快照和target_id，不读取现账号来重写历史结果。
现有任务清理先增加managed引用判定：活跃target、未消费outbox、未完成依赖、待确认需要恢复的Run一律保留。
首期保留批次的owned Task/Run、重跑所需检查点及适配器证据，不物理删除；可按既有规则清理大日志，但必要结果证据不能随事件裁剪丢失。
即使预留FK SET NULL，实际清理仓储和保护触发器也须RESTRICT任何仍被保留批次owned引用的Task/Run直删，删除任务页操作仅隐藏。
result_archive_ref/archive_state作为后续扩展预留，首期保持live；不实现未经设计的外部归档，也不假装只凭快照ID能够重跑。
所有引用批次已归档、全部链关闭、无preparing重跑/恢复依赖且达到保留期后，才进入独立整批清理事务。
该事务按projection guard→controls→rounds→canonical→target顺序重检并标记清理；标记后的批次拒绝新轮并给出明确历史过期原因。
清理标记写controls.purge_started_at；新轮受理同样锁controls并拒绝非空标记，因此与清理决定串行。
完成标记后再按target→Task→Run顺序清理，禁止Run锁后等待projection guard；已留存bulk.result_revised审计也须随批次保留。
首期代价是Task/Run历史随批次保留，容量监控必须计入；后续压缩归档需单独给出证据schema、适配器恢复协议及竞态测试。
外部blocker仅保留ID快照，不为阻塞引用无限保留其他批次全部日志。

未消费selection按TTL分块清理：先CAS status=expired，再逐批删除无引用targets；请求行作为幂等墓碑至少保留7天。
墓碑保留request_key/hash、expired状态和原资源ID，删除查询内容/展示证据；API幂等保证只覆盖公布的7天窗口，不承诺永久预览键。
已受理batch/round/control请求的幂等回执随批次保留，不随selectionTTL消失；不使用文件递归删除。
已消费selection随批次保留，不走预览TTL；重跑selection有round引用，不能独立删。
批次删除定义为隐藏/归档展示，不立即物理级联；物理清理仅针对已归档、所有轮结束、无恢复依赖的完整批次。
批次历史统计快照保留期与详细Run日志保留期分别配置，默认沿既有任务历史规则，新增配置需同步schema/配置页/README。

## 12. 迁移与事务验收

迁移仅新增表/索引/Run修订列，先部署识别manager_version的兼容版本，再开放新受理。
新写路径功能开关必须同时控制HTTP入口、任务中心重跑和dispatcher适配；不能只隐藏菜单。
为managed批次路由 `_refresh_batch()` 到dirty通知/专用投影，旧兼容批次继续旧汇总，避免双写。
关闭新受理不等于停止已受理工作；回退版本必须认识owned关联、控制门闩、outbox和保留引用。

必须在独立数据库/schema运行以下并发测试，不得用生产验证替代：

- 两worker同时冻结同selection，仅一份ready名单；模拟事务提交顺序与请求回执丢失。
- 取消与首次claim竞态：若claim先提交则链可收口，否则不发首个业务请求。
- 冻结重跑与projector交错：原轮贡献、当前归属、pending初始贡献保持恒等式。
- 连续两轮选择同目标，冻结按round_no发布、后轮等待前轮且不挂载其Run；取消后轮不终止前轮。
- 大批冻结持control锁时并发首次claim，NOWAIT失败后admission立即释放，不能阻塞其他业务准入。
- 原target_round未物化、部分物化、全部物化时取消，反复恢复计数均无负数和重复。
- 在每个崩溃点强制中止事务，再恢复；确认任务不丢、不重复、统计可重建。
- 手动重跑旧Run入口与自动dependency_resume分别生成新round/原round关联。
- outbox小ID晚提交、大ID先消费，不丢晚提交事件；重复事件和旧revision无重复计数。
- 组合多父Run/子Run及晚到旧轮结果，当前新轮不被覆盖；真实回执修订保留审计记录。
- 删除账号、任务保留清理、selectionTTL与活跃批次并发，不删除恢复所需资料。
- 锁监控覆盖所有managed入口，故意制造旧顺序调用时测试失败；锁超时不得变成静默跳过账号。

实现的目标不是SQL文件逐字照抄，而是以上字段语义、事务边界、锁顺序和可恢复不变量全部成立。
任何字段简化都须同时给出对应不变量和故障测试的替代证明。
