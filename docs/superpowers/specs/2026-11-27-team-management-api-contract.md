# Team 管理 HTTP 契约 v1

日期：2026-11-27。状态：HTTP 契约 v1 已收口，后端端点、存储迁移和任务处理已在独立工作区实现，前端页面由 Antigravity 独立开发。本文与[菜单及业务设计](2026-11-27-team-management-design.md)配套；机器契约见 [OpenAPI](../../../contracts/teams.openapi.json)，生成类型见 [teams-schema.d.ts](../../../frontend/src/api/teams-schema.d.ts)，验证边界见[后端验收记录](../reviews/2026-11-27-team-backend-acceptance.md)。

## 1. 公共约定

### 1.1 身份、时间与响应

- 新端点以 `/api/teams` 为前缀，沿用现有同域认证。
- 本地 `team_id`、`account_id`、`probe_id`、`invitation_id`、`member_id`、`join_request_id`、`selection_id`、`task_id`、`run_id`、`batch_id` 及其数组均为正整数十进制字符串，不转换为 JavaScript `Number`。
- `workspace_id`、`remote_user_id`、`remote_invitation_id` 保留远端不透明字符串，不要求十进制；本地 ID 与远端 ID 不互换。
- `revision`、`expected_revision`、`selection_revision` 为正整数版本号；数量为非负整数。时间为带时区的 ISO 8601 字符串。未知数量、时间和远端事实为 `null`，不得用 `0`、空字符串或当前时间代替。
- `purchased_seats=0` 是明确的零席位。`planned_member_limit=null` 表示未设置。明确支持清空的本地可编辑字段可接收 `null`，与远端未知事实分开解释。
- 所有新 Team 响应使用下列包络；列表也放在 `data` 内。HTTP 状态与包络一致，不使用 HTTP 200 包装输入错误。
- 请求只接受本文列出的字段；不返回完整账号行、AT、Cookie、密码、OTP、原始 Session、私有恢复材料或原始上游响应。

成功响应：

```json
{
  "ok": true,
  "request_id": "本次HTTP追踪编号",
  "data": {}
}
```

错误响应：

```json
{
  "ok": false,
  "request_id": "本次HTTP追踪编号",
  "error": {
    "code": "parameter_invalid",
    "message": "中文原因",
    "field": "account_ids",
    "retryable": false,
    "details": {}
  }
}
```

`request_id` 仅定位本次 HTTP 请求，不是幂等键。`field` 无单一对应字段时为 `null`。业务阶段错误的完整证据通过 TaskCenter 读取。

### 1.2 写请求与幂等

除 `join-preview`、`candidates/resolve` 两个纯读 POST 外，所有新 POST、PATCH 至少提供 `Idempotency-Key` 请求头或 JSON `idempotency_key`；同时提供时必须完全相同。键为去除首尾空格后 16–128 个字符的字符串，推荐 UUID。

新 Team 写接口在同一幂等命名空间内按键定位回执；同一键、同一路径及规范化请求返回原持久回执，同键更换路径、Team、操作或请求内容返回 `409 idempotency_conflict`。请求摘要包括路径中的 Team、操作、固定目标和所有执行选项。先找原回执，再检查名单到期、版本及当前权限，避免已经受理的请求因环境变化失去原回执。既有 `/api/bulk/selections` 继续使用自身命名空间。幂等键不是凭据，不承载账号材料。

网络重发保留原键和原请求。用户再次发起继续或重跑使用新键；同 Team 同目标仍有未终态执行时复用该执行，不能借新键并行创建第二次加入。人工重跑终态任务创建新 Run，保留原邀请、成员成果和旧 Run。

### 1.3 分页、筛选与排序

新列表使用 `page`、`page_size`；默认 `page=1`、`page_size=20`，`page_size` 范围 1–100。列表 `data` 为 `{items,total,page,page_size,revision}`；`revision` 为该读模型修订标识字符串，不能作为写入 `expected_revision` 使用。

`include_facets=0|1` 默认 `0`。请求 `1` 时增加 `facets`，只返回该端点列明的字段及 `{value,count}` 数组；`total`、列表和 facets 使用同一业务范围。精确 ID 筛选不做模糊匹配。未知筛选字段、非法枚举、分页越界参数返回 422；合法但无结果返回空列表，保留真实 `total`。

| 列表 | 允许的业务筛选 | 固定排序 |
| --- | --- | --- |
| Team | `q`、`manager_account_id`、`role`、`last_sync_status` | 本地 `id` 降序 |
| 成员 | `q`、`membership_state`、`role`、`linked=all\|linked\|unlinked` | 本地 `id` 升序 |
| 邀请 | `q`、`invitation_state`、`membership_state`、`execution_status`、`stage`、`join_request_id` | `updated_at`、`id` 降序 |
| 候选账号 | `q`、`scope=unassigned\|all`、`archived=0\|only\|all`、`has_access_token=true\|false`、`has_password=true\|false`、`totp_enabled=true\|false`、`email_status=invalid\|unmarked` | 本地账号 `id` 降序 |
| 加入请求的逐项目回执 | `acceptance_status`、`execution_status`、`reason_code` | 固定目标 `ordinal` 升序 |

`q` 仅匹配相应列表的公开名称、邮箱或本地 ID，不作为 `team_id` 筛选的替代。各枚举为精确单值，不接受逗号拼接；`all` 仅在表中明确列出的字段有效。候选布尔筛选只接受字符串 true/false，不传表示不限定；它们只检查本地材料存在性，不代表在线认证成功。email_status=unmarked 表示未标记失效，不宣称邮箱健康。Team facets 仅支持 `role/last_sync_status`，成员支持 `membership_state/role/linked`，邀请支持 `invitation_state/membership_state/execution_status/stage`；其他列表不返回 facets，传 `include_facets=1` 时为 `{}`。

## 2. 固定枚举与窄 DTO

### 2.1 枚举

| 字段 | 值与含义 |
| --- | --- |
| `role` | `owner`、`admin`、`member`、`unknown`；按实际远端权限归一化，未知不推断 |
| `membership_state` | `joined` 已确认当前成员、`left` 已明确离开、`unconfirmed` 当前关系未确认 |
| `invitation_state` | `not_sent` 本次意图尚未确认发出邀请、`pending` 有效待接受、`accepted` 已有接受证据、`revoked` 明确撤回、`expired` 明确过期、`unconfirmed` 邀请事实未确认 |
| `auth_capability` | `available` 已知具备本次认证材料、`missing` 已确认缺少必要材料、`unknown` 尚不能判断；不把 `unknown` 当作必失败 |
| `execution_status` | `none` 尚无执行，或现有任务公开状态 `queued/running/waiting/cancelling/settling/stopping/success/partial_success/failed/stopped/cancelled/interrupted/deactivated/unsupported` |
| `stage` | `queued/manager_verify/state_check/invite/member_auth/accept/member_verify/persist/complete` |
| `waiting_reason_code` | `waiting_account/waiting_sync/waiting_capacity/waiting_child/waiting_remote`，没有等待原因时为 `null`；等待仍使用 `execution_status=waiting` |
| `last_sync_status` | `never/queued/running/success/partial_success/failed/interrupted` |
| Probe `status` | `queued/running/success/failed/cancelled/interrupted` |
| Probe `stage` | `queued/manager_auth/workspace_discovery/permission_check/complete`；与邀请执行 stage 分开 |
| `acceptance_status` | `pending/accepted/reused/skipped/failed`；仅表示逐项目受理，不表示加入成果 |
| 请求 `status` | `preparing/queued/running/waiting/success/partial_success/failed/stopped/cancelled/interrupted` |

邀请状态和成员状态分别保存。已是成员但没有邀请历史时，不伪造 `accepted`；已有邀请本身是续接事实，不是失败原因。历史成功 Run 不因后来离开 Team 而改写。

### 2.2 公共对象

| 对象 | 精确字段 |
| --- | --- |
| `AccountRef` | `id,email,archived`；邮箱未返回时 `email=null`，归档为布尔值 |
| `TeamRef` | `id,workspace_id,name,display_name` |
| `TaskRef` | `task_id,run_id,status`；尚未创建逐账号 Run 时相应引用为 `null` |
| `ErrorInfo` | `code,message,stage,retryable`；没有错误为 `null`，详细证据另读任务 |
| `ActionReceipt` | `accepted,reused,team_id,task_id,run_id,status`；持久任务受理后 `accepted=true` |
| `AllowedAction` | `enabled,reason_code`；无禁用原因为 `null`，只描述本次快照能力，不替代执行时核验 |

`TeamDTO` 固定为：

| 字段 | 类型与含义 |
| --- | --- |
| `id,workspace_id,name` | 本地 ID、远端工作区 ID、远端名称；名称未知为 `null` |
| `display_name` | 本地备注名，未设置为 `null`；UI 优先显示备注名，再显示远端名称 |
| `manager_account` | `AccountRef`，包括已归档母号；绑定引用不另存一份凭据 |
| `role` | 最近确认的管理账号角色 |
| `purchased_seats` | 已购席位，未知为 `null`，明确为零则为 `0` |
| `planned_member_limit` | 本地总人数上限，正整数或 `null`，包含已确认属于该 Team 的母号 |
| `confirmed_member_count,pending_invite_count,processing_count` | 各自独立的数量快照，未知为 `null`；不能相加当成占位数 |
| `last_synced_at,last_sync_status` | 最近一次成功取得业务快照的时间及当前同步结果；失败保留原成功时间和数据 |
| `revision` | Team 可编辑记录的正整数版本，供 `expected_revision` 校验 |

`MemberDTO` 固定为 `{id,team_id,remote_user_id,email,account,role,membership_state,joined_at,last_verified_at,latest_task}`。`account` 为 `AccountRef|null`，`latest_task` 为 `TaskRef|null`。远端成员未入库仍返回，不自动创建本地账号。

`InvitationDTO` 固定为 `{id,team_id,remote_invitation_id,account,email_snapshot,invitation_state,membership_state,latest_execution,updated_at,last_verified_at,actions}`。它是本地“邀请与加入意图”记录，可在尚未发送远端邀请时存在；`remote_invitation_id=null` 不等于执行失败。

- `account` 为 `AccountRef|null`；远端邀请未匹配本地账号时仍保留。
- `latest_execution` 为 `{task_id,run_id,status,stage,waiting_reason_code,error_info}`，不存在执行时 ID 为 `null`、`status=none`。
- `actions` 仅含 `continue/retry/view_task` 三个 `AllowedAction`。
- 邀请表固定六列：目标账号、业务事实、执行与阶段、结果摘要、时间、操作。“业务事实”分两行呈现 invitation_state 与 membership_state；“执行与阶段”呈现状态与阶段；“结果摘要”使用本契约第 8 节短语，完整证据进入 TaskCenter。

## 3. 绑定探测与 Team 记录

### 3.1 探测管理账号

| 端点 | 请求 | 成功响应 `data` | 状态码 |
| --- | --- | --- | --- |
| `POST /api/teams/binding-probes` | `manager_account_id` 必填；`target_workspace_id` 可选，仅限制或预选探测目标；幂等键 | `{probe_id,status,task_id,run_id}`，持久化后异步探测 | 202；400/422 输入，404 账号，409 幂等冲突，503 受理失败 |
| `GET /api/teams/binding-probes/{probe_id}` | 无请求体 | 下述 `BindingProbeDTO` | 200；404 |

`BindingProbeDTO` 为 `{id,revision,manager_account,status,stage,task_id,run_id,workspaces,suggested_workspace_id,completed_at,expires_at,error_info}`。revision 为证据修订正整数，stage 可轮询，详细进度仍通过 Task/Run 读取。每个 `workspaces` 元素仅含 `{workspace_id,workspace_type,name,role,can_manage,capabilities,purchased_seats}`；workspace_type=personal|team|unknown，`capabilities` 为 `{read_members,read_invitations,invite_members}`，各值允许 `null` 表示未确认。

探测必须进入持久 Task/Run，执行认证与远端读取。归档母号可以探测。仅有一个已明确为非个人 Team 的可管理候选时，suggested_workspace_id 才返回该 ID；多候选、没有候选或证据未确认时为 null。该字段只帮助预选，不创建 Team，也不默认绑定个人工作区。target_workspace_id 仅限定本次核验目标，不能省略后续的明确绑定。成功证据仅从成功完成时间起 10 分钟内有效；排队与失败结果没有有效期。创建绑定提交准确 workspace_id 及匹配的 probe_id/probe_revision；更换母号按路径 Team 已保存的 workspace_id 核对探测证据，不允许通过 PATCH 修改 workspace_id。该工作区的 can_manage 必须为 true。

多个远端 workspace 候选本身不是跨 Team 冲突，允许明确单选。单 Team 占用约束针对本地 Team 业务归属：只有证据已经映射到其他本地 Team 的成员关系、母号或未决占用，才拒绝绑定或跳过加入；其他尚未绑定本地 Team 的远端关系仅作为观察证据，不据此默认阻断所有候选。

### 3.2 创建、读取与修改

| 端点 | 请求 | 成功响应 `data` | 状态码 |
| --- | --- | --- | --- |
| `POST /api/teams` | `manager_account_id,workspace_id,probe_id,probe_revision`；可选 `display_name,planned_member_limit`；幂等键 | `{team:TeamDTO,sync:ActionReceipt}` | 201；404 账号或 Probe，409 证据过期/不匹配、重复绑定或跨 Team 母号占用，422 参数，503 事务失败 |
| `GET /api/teams` | 公共分页、Team 筛选 | 公共列表，`items` 为 `TeamDTO` | 200；422 |
| `GET /api/teams/{team_id}` | 无请求体 | `{team:TeamDTO,actions:{sync,reverify,join},permission_verified_at}` | 200；404 |
| `PATCH /api/teams/{team_id}` | `expected_revision`；至少一个可编辑字段 `display_name,planned_member_limit,manager_account_id`；换母号时必需 `probe_id,probe_revision`；幂等键 | `{team:TeamDTO}` | 200；404，409 版本/Probe/母号占用冲突，422 参数 |

创建在同一数据库事务中保存 Team、管理关联及首轮同步任务，二者不能部分成功。首轮尚未取得数据时，相应数量为 `null`，`last_sync_status=queued`。同 workspace 在同部署只能有一份 Team；不同键重复创建返回 `409 team_already_bound`，`details.existing_team_id` 定位原记录；相同键重发返回原 201 回执。

`display_name` 只接受不超过 120 字符的本地备注名或 `null`；空白名称按 `null` 清空。`planned_member_limit` 只接受正整数或 `null`，不接受 0。换母号需要该账号对同一 workspace 的有效成功 Probe，且 probe_revision 与证据修订匹配，账号不被其他本地 Team 占用；只更换执行管理身份，**不转移远端所有权，不改变成员角色**。未换母号不得通过无关 Probe 修改权限事实。

修改前校验 `expected_revision`，冲突返回 `409 revision_conflict` 及当前 `revision`；相同幂等请求仍先复用原回执。降低本地上限不移除现有成员或撤回已发邀请，只影响后续新增占位。权限、席位和远端名称不是 PATCH 可写字段。

换母号不丢弃旧母号已发请求的真实回执。该回执继续按原请求、workspace 与 execution fence 保存；旧执行不得覆盖新母号配置或更新其当前快照。母号配置 revision 与业务回执归属分开核验，不能只因配置版本变化就抹掉已经发生的邀请或接受成果。

### 3.3 同步与单独权限核验

| 端点 | 请求 | 成功响应 `data` | 状态码 |
| --- | --- | --- | --- |
| `POST /api/teams/{team_id}/sync` | 幂等键 | `ActionReceipt`，同步成员、邀请、订阅及数量快照 | 202；404，409 幂等冲突，503 |
| `POST /api/teams/sync-bulk` | `team_ids` 数组，1–100 个；幂等键 | `{accepted:true,batch_id,requested_count,unique_count,duplicate_count,reused_count,accepted_count,skipped_count,failed_count,items}`；每项 `{team_id,task_id,run_id,acceptance_status,execution_status,reason_code}` | 202；422，409 幂等冲突，503 |
| `POST /api/teams/{team_id}/reverify` | 幂等键 | `ActionReceipt`，单独重新验证当前母号对该 workspace 的管理权限 | 202；404，409 幂等冲突，503 |

同 Team 已有同类未终态同步或核验任务时返回其任务引用，`reused=true`。权限核验只更新权限证据与角色，不冒充完整成员/邀请同步。普通 GET 不触发这些任务。

sync-bulk 的逐项 acceptance_status 为 accepted/reused/skipped/failed，仅表示受理；execution_status 才是对应 Task/Run 的公开执行状态，没有执行引用时为 none。reused_count 包含在 accepted_count 中；accepted+skipped+failed=unique，requested=unique+duplicate，不重复相加。

## 4. 成员、邀请与候选账号读取

| 端点 | 请求 | 成功响应 `data` | 状态码 |
| --- | --- | --- | --- |
| `GET /api/teams/{team_id}/members` | 公共分页、成员筛选；`membership_state` 默认 `joined` | 公共列表，`items:MemberDTO[]` | 200；404，422 |
| `GET /api/teams/{team_id}/invitations` | 公共分页、邀请筛选；不传状态显示全部本地意图及远端邀请 | 公共列表，`items:InvitationDTO[]` | 200；404，422 |
| `GET /api/teams/{team_id}/invitations/{invitation_id}` | 无请求体 | `{invitation:InvitationDTO}` | 200；404，不属于路径 Team 也按 404 |
| `GET /api/teams/{team_id}/candidates` | 公共分页、高频筛选；`scope` 默认 `unassigned`；`archived` 默认 `0` | 公共列表，`items:CandidateDTO[]` | 200；404，422 |
| `POST /api/teams/{team_id}/candidates/resolve` | `values`：1–10,000 个邮箱或本地账号 ID 字符串 | `{requested_count,unique_count,duplicate_count,items}` | 200；404 Team，422 输入 |

候选 GET 与 resolve 均只读本地数据，不触发认证、远端请求、名单持久化、席位预留或任务。resolve 不要求幂等键；按去除首尾空格后的输入去重，邮箱按现有账号规范化规则精确匹配。每项返回 `{input,match_status,candidates,reason_code}`；`match_status=matched|not_found|ambiguous`。只有唯一匹配才作为候选；多匹配返回候选列表，由用户选准，不默认选第一条。

`CandidateDTO` 为 `{account,category,auth_capability,has_access_token,has_password,totp_enabled,email_status,other_teams,disabled,reason_code}`；材料存在性字段为布尔值，email_status=invalid|unmarked；`other_teams:TeamRef[]` 仅指本地 Team 归属，`category` 使用下一节互斥分类。`scope=unassigned` 必须无任何本地 Team 成员/母号归属及未决占用，包含本 Team pending 的账号默认也不列出；它们可通过 scope=all 或 resolve 查看并续接。`unavailable/another_team/missing_auth` 分类置灰并提供原因；归档本身不是禁用原因，`auth_capability=unknown` 不置灰，同 Team 活跃意图在 all/resolve 中允许复用。

新成员候选 GET 默认仅查询未归档账号，可显式 archived=only/all 查看归档。resolve 按明确粘贴的 ID/邮箱解析，不因归档跳过或禁用；母号绑定选择器仍可包含归档账号，这与新成员候选的默认范围分开。

成员列表默认仅展示当前已确认关系。查看历史离开或未确认关系时显式筛选相应状态；远端名单读取失败、不完整或单次缺项，不能将 `joined` 改为 `left`。本地关联和远端身份分别保存，不因邮箱显示变化悄悄换成本地其他账号。

## 5. 名单、预览与容量

### 5.1 请求名单与 selection 接缝

`join-preview` 与 `join` 使用同一种目标描述，二选一：

```json
{"account_ids": ["101", "102"], "expected_emails": {"101": "member-a@example.test", "102": "member-b@example.test"}}
```

```json
{"selection_id": "900", "selection_revision": 1}
```

显式 `account_ids` 为 1–10,000 个本地 ID，按账号 ID 去重并保留首次顺序。expected_emails 为可选 ID→邮箱快照映射；键必须属于 account_ids，值为非空邮箱，账号页来源应传完整已选邮箱快照。`selection_id` 必须为冻结的账号集合，`selection_revision` 必填且相符，沿用名单固定时的邮箱快照，不另传 expected_emails；集合上限 100,000 个账号。

预检、逐项受理与执行核对账号 ID 及其固定邮箱快照。已提供的快照或 selection 固定快照与当前账号不符时，归入 unavailable 并保留 account_identity_changed 原因，逐项跳过，不把换绑后的邮箱静默改成本次目标；其他账号继续处理。只核对本地快照，不增加逐项登录或新的远端验证。

selection 沿用已扩展的 `POST /api/bulk/selections` 与 `GET /api/bulk/selections/{selection_id}`：

- `operation={key:"team_join",version:1}`，`parameters={team_id:"目标本地TeamID"}`。
- 来源为既有 `source={kind:"query",query:AccountQuery}` 或 `{kind:"ids",entity:"account",ids:[...]}`；账号范围的 `team_scope/archived` 同第 9 节。
- 该现有接口仍使用 `Idempotency-Key` 头及自己的包络、异步 preparing/ready、TTL 和 selection_revision，不因 Team 新接口而改写。
- 批量创建页的 `operations` 保留原六类操作；Team 名单元数据放在 `selection_operations`，使用专用 `team_join/v1` 参数、预检和读取适配。不得拿查套餐等其他操作的 selection 直接加入 Team。
- 准备完成后固定成员，不在执行时重新跑原筛选。Team、操作、修订、有效期不匹配分别返回明确 409/410；账号筛选变化不替换固定名单。
- preview 不消费 selection。join 同事务关联固定名单与请求；相同键重发复用原请求，其他请求重复消费返回 `409 selection_consumed` 及 `details.existing_join_request_id`。

### 5.2 纯本地加入预览

`POST /api/teams/{team_id}/join-preview`：只接收上面的目标描述，不要求幂等键，返回 HTTP 200：

| `data` 字段 | 含义 |
| --- | --- |
| `team_id` | 精确目标 Team |
| `selection_id,selection_revision` | 使用 selection 时回显；显式 ID 模式为 `null` |
| `snapshot_revision,snapshot_at,team_last_synced_at` | 本地评估修订、本次读取时间、最近远端快照时间，未知为 `null` |
| `requires_sync` | 成员、邀请或占位事实尚不足以可靠评估容量时为 `true`，执行前需要同步 |
| `counts` | 下述固定、互斥人数分组 |
| `capacity` | 下述容量评估 |

不创建 Task/Run、持久 selection、邀请意图或席位占位，不刷新 Token，不获取 OTP，不调用上游。`can_submit=false` 是正常评估结果，仍返回 200；输入非法才返回 400/422，Team 不存在返回 404。性能验收目标为服务端 P95 小于 50ms，按名单规模分别记录，包含本地校验和序列化；实测结果及未达项见[后端验收记录](../reviews/2026-11-27-team-backend-acceptance.md)，不因接口已实现而推定达标。

`counts` 固定字段：

| 字段 | 含义 |
| --- | --- |
| `requested_count,unique_count,duplicate_count` | 原请求数量、去重目标数量、重复数量；三者满足 requested=unique+duplicate |
| `unavailable_count` | 本地账号不存在或已有明确不可用证据 |
| `another_team_count` | 已确认属于其他本地 Team，或被其他本地 Team 母号/未终态加入意图/有效占位占用 |
| `already_member_count` | 已确认属于目标 Team |
| `same_team_active_count` | 同目标 Team 已有未终态加入意图，可复用执行 |
| `missing_auth_count` | 没有以上事实，且已明确缺少必要认证材料 |
| `resume_invite_count` | 已有本 Team 有效邀请，可续接接受 |
| `new_count` | 没有上述事实，需要执行时检查并处理的新目标 |
| `eligible_count` | new+resume_invite+same_team_active；不是另一个互斥桶 |

每个去重账号按 `unavailable→another_team→already_member→same_team_active→missing_auth→resume_invite→new` 顺序归入一个桶，七个桶之和等于 `unique_count`。`auth_capability=unknown` 不能归为 missing_auth；它仍按其他已知事实归类，执行时检查。没有本地邀请证据而归入 new，不承诺远端必定没有邀请。

### 5.3 容量与费用

`capacity` 固定为：

| 字段 | 类型与规则 |
| --- | --- |
| `basis` | `purchased_seats/planned_member_limit/unavailable` |
| `purchased_seats,planned_member_limit` | 与 TeamDTO 相同 |
| `effective_limit` | 实际执行人数上限，无法确定为 `null` |
| `occupied_count` | 当前成员、有效邀请、有效本地占位按目标身份去重后的并集；不能直接相加三组摘要，证据不足为 `null` |
| `available_count` | 已知 limit 和 occupied 时为 max(0,limit−occupied)，否则 `null` |
| `additional_required` | 本批尚需净新增预留的目标数量，已存在成员/邀请/原意图有效占位不重复申请；不能机械等于 new_count，不足以确定为 `null` |
| `can_submit` | 是否可提交当前请求，布尔值；不表示已获远端邀请权限或已预留名额 |
| `blocking_reason_code` | `team_limit_required/no_eligible_targets` 或 `null` |

有明确已购席位时，`basis=purchased_seats`，本地计划上限存在则 effective_limit 为二者较小值。已购席位未知时，必须有正整数本地计划上限，`basis=planned_member_limit`；二者都未知/未设置时为 unavailable。**已购席位为 0 不回退本地上限**，effective_limit 为 0。

本地已购/计划上限规则已满足，但成员、邀请名单尚未完整同步时，`occupied_count/available_count=null` 且 preview 的 `requires_sync=true`，不推算成零。名额暂不足或需先同步但已具备人数上限时，可受理后等待，`can_submit=true`，不把等待同步/容量放入 blocking_reason_code。preview.can_submit 只对应 POST join：purchased_seats 与 planned_member_limit 均为 null 时，一律 false/team_limit_required，与 POST join 的 409 完全一致，不因预计无需新占位而放行；具备上限但没有合格目标时为 false/no_eligible_targets。

只有第 7 节邀请 continue/retry 对纯接受、核验或本地保存提供独立例外：无需新增占位时，可在席位/本地上限暂缺时继续；这不改变 join-preview 对 POST join 的结果。执行时若发现需要重新发送新邀请，再核验上限和占位，必要时等待，不把旧邀请成功当作无限新增邀请授权。

同 Team 原意图已有有效预留时复用自己的占位；`occupied_count=effective_limit` 不阻止它继续。上限降低至占用数以下时，暂停新的邀请，但仍允许接受、核验及保存。等待同步或容量本身只保留固定 Team 的已受理意图，不虚构已经分配新席位。

preview 是预计，不预占、不授权；join 必须在工作区事务/执行围栏内原子复核占位。仅凭本地人数上限无法承诺绝对零新增计费；UI 展示 basis、数据来源和时间，不将 planned_member_limit 标为已购免费名额。

## 6. 集合加入与持久回执

| 端点 | 请求 | 成功响应 `data` | 状态码 |
| --- | --- | --- | --- |
| `POST /api/teams/{team_id}/join` | 目标描述；幂等键；不接收任意角色、workspace 替换或个人数据合并选项 | `JoinRequestDTO`，持久请求及父 Task/Run 引用 | 202；404 Team/selection，409 名单/幂等冲突或缺上限，410 selection 到期，422 输入，503 未受理 |
| `GET /api/teams/{team_id}/join-requests/{join_request_id}` | 公共分页，逐项目回执筛选 | `{request:JoinRequestDTO,items:JoinItemDTO[],total,page,page_size,revision}` | 200；404，422 |

`JoinRequestDTO` 固定为 `{id,team_id,operation,accepted,reused,status,waiting_reason_code,selection_id,selection_revision,batch_id,task_id,run_id,created_at,counts,capacity,items_url}`。`operation=join|continue|retry`；POST join 为 join。顶层 accepted=true 与 HTTP 202 只表示请求已经持久化，不表示所有 pending 目标已经受理，更不表示已加入。

`counts` 为 `{requested_count,unique_count,duplicate_count,pending_count,accepted_count,reused_count,skipped_count,failed_count}`。requested/unique/duplicate 受理后固定；其余为受理处理进度。pending+accepted+skipped+failed=unique，reused 是 accepted 的子集，不能再加一次。failed 仅指逐项受理失败，不是后台加入失败数；后台成果读取邀请及 Task/Run。

`JoinItemDTO` 固定为 `{ordinal,account_id,invitation_id,acceptance_status,task_id,run_id,execution_status,reason_code,message}`。reused 项计入 accepted_count。skipped/failed 项没有新执行时 Task/Run 为 `null`，但有原记录时可保留精确引用。

大批次先持久化固定目标、父任务和回执，后台按窗口处理，不在 HTTP 请求内遍历创建全部 Run。尚未处理的目标为 pending，不计入 accepted_count；分类和子 Run 引用通过回执分页读取。固定名单不因后续读取页面变化增减，目标不存在等逐项问题保留分类，不使整批其他账号丢失。

逐目标进入 accepted/reused 前，必须在集合事务中取得或复用唯一的账号 Team 业务占用，不能等到实际登录或发送邀请时才检查跨 Team 冲突。不同 Team 竞态中最多一方进入 accepted，其余 skipped/already_in_another_team。等待同步或容量的 accepted 目标也固定持有账号 Team 占用，但没有容量时不虚假预留席位；子 Run 可在之后创建，账号占用与某次 Run 生命周期独立。

跨本地 Team 业务归属的账号一律为 `skipped/already_in_another_team`，不自动退出原 Team、不覆盖原认证上下文；母号绑定/更换中的同类冲突返回 409。未映射到本地 Team 的其他远端 workspace 关系不自动导致跳过。目标 Team 内已有成员为 skipped/already_member；同 Team 未终态意图为 reused；已知缺少材料为 skipped/missing_auth_materials；未知材料仍受理检查。

名额暂不足可返回 202，执行为 `waiting/waiting_capacity`。已有上限但名单未完整同步时可返回 202，执行为 `waiting/waiting_sync`，Worker 先同步、再原子获取净新增容量。已购席位与本地上限都缺失时，POST join 返回 `409 team_limit_required`，不得留下新邀请或席位占位；第 7 节纯接受/核验的继续与重跑保留其例外。母号会话/权限暂待核验、目标账号暂忙可排队；实际认证或权限失败按阶段写入任务，不能用缺少 preview 远端证据永久阻断重跑。

默认邀请普通成员，自动接受指定 workspace，保留个人工作区，不自动合并个人数据。成功必须同时确认目标成员关系和本次要求的本地保存；远端已加入但保存失败时保留 joined，执行可为 partial_success/failed，不回退成未加入。

## 7. 邀请继续、重跑与任务控制

| 端点 | 请求 | 成功响应 `data` | 状态码 |
| --- | --- | --- | --- |
| `POST /api/teams/{team_id}/invitations/{invitation_id}/continue` | 幂等键 | `JoinRequestDTO`，operation=continue，唯一目标 | 202；404，409 请求冲突，422，503 |
| `POST /api/teams/{team_id}/invitations/{invitation_id}/retry` | 幂等键 | `JoinRequestDTO`，operation=retry，唯一目标 | 202；404，409 请求冲突，422，503 |
| `POST /api/teams/{team_id}/invitations/continue-bulk` | `invitation_ids`，1–10,000 个；幂等键 | `JoinRequestDTO`，operation=continue | 202；404 Team，409，422，503 |
| `POST /api/teams/{team_id}/invitations/retry-bulk` | `invitation_ids`，1–10,000 个；幂等键 | `JoinRequestDTO`，operation=retry | 202；404 Team，409，422，503 |

单条邀请必须属于路径 Team，否则 404。批量各项不属于该 Team 或不存在时返回逐项 skipped/invitation_not_found，不读取或返回其他 Team 的材料；其余目标继续受理。批量按 invitation_id 去重，再按同 Team 的目标身份去重，不为同一目标创建两个并行加入。

continue 按已确认事实从未完成阶段接续；retry 是对终态执行的人工重跑。二者遇到同 Team 同目标未终态执行均复用并返回原 Task/Run；终态后需要执行则新建 Run，保留原邀请记录，不强制重新发信。已经加入且要求的本地保存完整时，逐项 skipped/already_member，无需伪造一次远端操作。

跨 Team 占用仍 skipped/already_in_another_team。只有继续接受/核验而不新增占位时，不因当前上限缺失或没有新名额拒绝受理；需要重发时按第 5.3 节执行。回执丢失、结果待确认不构成永久禁重跑原因。

任务中心统一提供：

| 现有端点 | 使用约定 |
| --- | --- |
| `GET /api/operations/{task_id}?include_events=0` | 保持 `{ok,task}`，读取精确任务及 Run |
| `GET /api/operations/{task_id}/runs/{run_id}/progress` | 保持 `{ok,progress}` |
| `GET /api/operations/{task_id}/runs/{run_id}/events` | 沿用 `after_id/limit` 的事件分页与旧包络 |
| `GET /api/operations/{task_id}/runs/{run_id}/logs` | 沿用字节 `cursor/limit` 的日志分页与旧包络 |
| `POST /api/operations/{task_id}/retry` | Team handler 必须接入同一继续/重跑协调层及请求幂等，不能只重复执行旧 HTTP |
| `POST /api/operations/{task_id}/cancel` | 请求停止，保留已确认业务事实 |
| `POST /api/operations/{task_id}/terminate` | 沿用现有明确终止与资源回收语义 |

旧任务端点的请求、状态码和响应仍以[任务中心既有契约](../../../contracts/task-center.openapi.json)为准，不套用新 Team 包络。原生 retry handler 已接入 HTTP 幂等键；Team handler 使用统一写回执协调层，旧单参 handler 继续兼容。

## 8. 错误与部分受理

新 Team HTTP 层至少固定以下 code；执行阶段的详细分类继续登记现有错误目录，不把所有异常合并为 unknown。

| HTTP | `error.code` | 含义 |
| --- | --- | --- |
| 400 | `invalid_json` | 不是 JSON 对象 |
| 401/403 | `authentication_required/access_denied` | 控制台认证或权限失败 |
| 404 | `team_not_found/account_not_found/probe_not_found/invitation_not_found/join_request_not_found/selection_not_found` | 对应资源不存在或不在路径归属内 |
| 409 | `idempotency_conflict/revision_conflict` | 请求键或编辑版本冲突 |
| 409 | `probe_not_ready/probe_expired/probe_revision_conflict/probe_identity_mismatch/manager_permission_unconfirmed` | Probe 未成功、过期、证据版本变化、账号或 workspace 不匹配、没有确认管理能力 |
| 409 | `team_already_bound/already_in_another_team` | 重复工作区绑定或母号跨 Team 占用 |
| 409 | `selection_not_ready/selection_revision_mismatch/selection_operation_mismatch/selection_team_mismatch/selection_consumed` | 固定名单不满足消费条件 |
| 409 | `team_limit_required` | POST join 缺少已购席位与本地上限；继续/重跑的纯接受核验按第 7 节例外 |
| 410 | `selection_expired` | 未消费的固定名单已到期 |
| 422 | `parameter_invalid/field_not_supported/idempotency_key_required/idempotency_key_invalid/idempotency_key_mismatch` | 输入、字段或请求键不符合契约 |
| 503 | `team_store_unavailable` | 未能完成持久受理或本地读取，`retryable=true` |

结构性输入错误或请求事务未提交时，不返回虚假的 Task/Run。持久受理后的逐项目结果，通过回执的 `reason_code` 表达；常用值固定为 `already_in_another_team/already_member/missing_auth_materials/account_not_found/account_unavailable/account_identity_changed/invitation_not_found`。账号忙、等待同步和等待名额属于运行等待，不作为永久 skipped。

HTTP 401/403 仅表明对应请求响应，不能单凭它认定 OpenAI 账号已停用或密码错误。有效邀请已存在为正常续接，不分类为失败。原始错误证据、私有恢复记录与公开简短原因分开保存。

### 8.1 Team 专用短语与分类登记

下表冻结 Team 新增业务原因的默认摘要；每个短语不超过 10 个 Unicode 字符。后续统一登记到 `core/operations/error_labels.py`、既有 `core/operations/errors.py` 分类器，并生成 `frontend/src/generated/task-error-labels.json`。HTTP 输入类通用原因复用现有分类；UI 不按错误原文自行匹配。

| 原因码 | 默认短语 | 阶段或用途 |
| --- | --- | --- |
| `probe_not_ready` | 等待探测完成 | 绑定校验，等待原探测 |
| `probe_expired` | 探测已过期 | 绑定校验，重新探测 |
| `probe_revision_conflict` | 探测版本变化 | 绑定校验，读取当前证据 |
| `probe_identity_mismatch` | 探测身份不符 | 绑定校验，选择准确账号及工作区 |
| `manager_permission_unconfirmed` | 管理权限待核验 | 绑定校验，重新核验 |
| `team_already_bound` | 工作区已绑定 | 绑定校验，定位 existing_team_id |
| `already_in_another_team` | 已属其他Team | 本地归属冲突，保留原归属 |
| `already_member` | 已是成员 | 目标成果，正常跳过 |
| `missing_auth_materials` | 缺认证材料 | member_auth，补齐已知缺失材料 |
| `account_identity_changed` | 账号身份变化 | state_check，原邮箱快照不符，保留原目标 |
| `team_limit_required` | 缺人数上限 | invite 前置条件，配置本地上限或同步已购事实 |
| `selection_team_mismatch` | 名单团队不符 | 名单校验，使用准确 Team 的固定名单 |
| `no_eligible_targets` | 无可处理目标 | 本地预览，不创建失败执行 |
| `team_workspace_unavailable` | 工作区不可见 | manager_verify，保留实际远端原因 |
| `team_permission_denied` | 无管理权限 | manager_verify，可重新核验 |
| `team_invite_rate_limited` | 邀请限流 | invite，按远端证据延后或重跑 |
| `team_invite_rejected` | 邀请被拒 | invite，保留具体拒绝依据 |
| `team_invite_receipt_missing` | 邀请回执缺失 | invite，允许重跑并先核对远端 |
| `team_invitation_expired` | 邀请已过期 | accept，重跑时决定是否需要新邀请 |
| `team_invitation_revoked` | 邀请已撤回 | accept，重跑时决定是否需要新邀请 |
| `team_workspace_mismatch` | 工作区不符 | accept/member_verify，不保存为其他 workspace 成功 |
| `team_member_unconfirmed` | 成员待核验 | member_verify，继续核验 |
| `team_save_failed` | 结果保存失败 | persist，保留远端加入事实并补保存 |
| `team_execution_lost` | 执行租约失效 | 原发生阶段，恢复核验后开启有效执行 |
| `waiting_account` | 等待账号空闲 | 正常等待原因，不产生失败 ErrorInfo |
| `waiting_sync` | 等待同步 | 正常等待原因，不产生失败 ErrorInfo |
| `waiting_capacity` | 等待名额 | 正常等待原因，不产生失败 ErrorInfo |

具体密码拒绝、OTP、TOTP、网络与存储错误继续复用对应细分类和实际阶段，不被上表的概括原因覆盖。短语仅用于默认摘要，完整原因、请求回执和 Run 证据继续保留；上述正常跳过或等待原因不自动改变任务为 failed。

## 9. 既有接口的有限扩展

### 9.1 任务中心精确 Team 过滤

`GET /api/operations` 新增 `team_id`，接受一个本地十进制 Team ID，与现有筛选按 AND 组合。它必须限定相关父子任务的精确持久关联，不能用 `q`、邮箱、目标名称或前端二次过滤替代。非法 ID 返回 422，合法但没有关联任务返回空列表。

调用示例：

```text
GET /api/operations?team_id=123&page=1&page_size=50&include_facets=0&include_batches=0
```

保持旧 `{ok,items,total,page,page_size,revision,facets?,batches?}`，不更改现有分页上限、默认值或包络。total、facet、计数及分页使用同一 team_id 谓词；详情继续使用原 Task/Run 引用，不引入 `/api/teams/.../task-logs` 副本。

后续须同步扩展路由、OperationQuery、存储谓词、OpenAPI、TaskFilters 与导航过滤状态；当前这些接缝没有 team_id，不能只在 UI 请求中加参数而让服务端忽略。

### 9.2 账号 Team 视图

现有账号读取、状态轮询、facet 与账号集合选择统一新增 `team_scope=non_team|team|all`，不传时默认为 all，保持旧调用范围；archived 独立，规范值统一为 `0/only/all`。既有兼容别名 1/true/yes 仍表示 only，include 表示 all，不能把 1 改成包含归档。

| 菜单视图 | 明确查询 |
| --- | --- |
| 活跃账号 | `team_scope=non_team&archived=0` |
| Team 账号 | `team_scope=team&archived=all`，默认包括归档账号 |
| 归档账号 | `team_scope=all&archived=only` |

team 只认至少一条当前已确认 joined 的母号/成员关系；non_team 为没有该关系，不因邀请排队、待接受或接受待核验提前迁移。Team 菜单按本地 account_id 去重，多工作区不重复计数；归档视图可与 Team 视图重叠。

账号读 DTO 仅增加窄字段 `team_memberships`，每项 `{team_id,workspace_id,name,display_name,role,membership_state,last_verified_at}`，不附带其他成员材料。最后一个 Team 明确离开后按原归档状态归类，单次同步失败不移除关系。既有账号响应包络与原字段保持兼容。

## 10. 前端挂载与交接边界

冻结接缝：

```text
侧栏 data-tab="teams"
  → #tab-teams > #teams-page-root
  → frontend/src/teams.ts 导出 mountTeams()
  → webui/static/task-center/teams.js
```

薄页面桥负责按需加载与现有 hash/history 导航，Vue 页面拥有筛选、分页、选择、请求失效和轮询状态。模块公开 `setVisible/closeDialogs/destroy`；离开停止读取，不取消已受理写请求。

沿现有导航传 `{tab:"teams",view:"list"|"detail",team_id?,section:"members"|"invitations"}`，不另外引入 Router。账号来源的加入动作使用显式 `target_team_id` 携带目标；上下文保存来源账号视图、查询、分页、勾选、滚动和返回位置，不能用当前可见页重新推导名单。

UI 直接消费 InvitationDTO 六列、服务端动作能力、capacity.basis 和状态枚举，不自行猜测权限、费用、剩余名额或重跑资格。TaskCenter 仍拥有执行详情；Team 页保留邀请及成员成果。本文件只冻结接口和交接规则，不包含前端代码或 OpenAPI 实现。
