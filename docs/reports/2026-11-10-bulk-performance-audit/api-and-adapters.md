# 批量任务 API、共享筛选与领域适配详细设计

日期：2026-11-10。状态：接口设计稿，未实现；承接[整体方案](design.md)。
本文确定公共请求、响应及领域边界，不声明当前服务已经支持这些新接口。
现有账号列表筛选语义、领域执行步骤、配置来源和手动重跑行为优先保持一致。

## 1. 通用协议

- 新接口统一位于 `/api/bulk`，沿用现有 WebUI 鉴权和同源访问规则。
- `Content-Type: application/json`；时间使用带时区 ISO 8601，日期筛选例外见第 2 节。
- 新 API 的所有数据库 ID 为十进制字符串，例如 `"4201"`，禁止转换为 JS Number。
- 底层已有 `operation_batches/tasks/runs.id` 是 BIGINT identity；`*_uuid` 是另一个字段。
- 新增内部表也使用 BIGINT 标识；公开 ID 字符串化不改变底层类型，不改旧 API 的数字响应。
- 数量、页大小、版本序号是受范围检查的整数；不得接收布尔值冒充整数。
- 未声明请求字段返回 `422 field_not_supported`，不能悄悄忽略国家、driver 等参数。
- `202` 仅表示受理意图已可靠保存；不是全部目标入队，更不是业务成功。
- 所有响应带 `request_id`；公开结果不含账号密码、Token、Cookie、OTP 和完整配置密钥。
- 任务日志与详细诊断继续通过既有 Run 详情入口读取；批次列表不携带完整事件。

成功响应的公共外层：

```json
{"ok":true,"request_id":"公开请求标识","data":{}}
```

失败响应：

```json
{"ok":false,"request_id":"公开请求标识","error":{
  "code":"selection_expired","message":"账号范围快照已过期，请重新预览。",
  "field":"selection_id","retryable":false,"details":{"selection_id":"71"}
}}
```

`retryable` 只表示是否适合重发同一 HTTP 请求，不表示账号业务是否允许手动重跑。
业务重跑由目标的 `actions` 和领域适配决定，不由 HTTP 错误分类代替。

## 2. AccountQuerySpec 与现有筛选同源

### 2.1 规范对象

```json
{
  "schema_version":1,"entity":"account","archived":"0",
  "date_from":"2026-10-01","date_to":"2026-10-31","q":"",
  "plan":[],
  "filters":{
    "id":"","email":"","source":[],"registration_driver":[],
    "token":[],"password":[],"promotion":["none"],"totp":[],
    "risk":[],"codex":[],"account_status":[],"email_status":[]
  },
  "order":[{"field":"id","direction":"desc"}],"limit":null
}
```

第一版排序只支持现有列表实际使用的 `id DESC`，不自行增加“创建时间正序”。
后续排序扩展必须在账号列表与批量选择同时启用，再增加 schema 版本或能力声明。
`limit=null` 表示全部匹配；正整数表示按固定排序取前 N 个，范围由目录返回的上限约束。
`limit` 是选取范围限制，`page_size` 是显示分页，两者不得混用。

### 2.2 精确字段与兼容转换

| 规范字段 | 现有输入 | 类型与语义 |
|---|---|---|
| `archived` | `archived` | `0 / only / all`，默认 `0`；旧 `1/true/yes` 归一为 `only` |
| `date_from/date_to` | 同名日期列条件 | 空或 `YYYY-MM-DD`；比较 `created_at` 前十位，结束日包含 |
| `q` | 高级搜索 `q` | 沿用 `parse_account_search`，当前最长 1,000 字符、最多 32 条 |
| `plan` | `plan` | 数组；沿用当前套餐谓词及 Plus 变体兼容，不自行改为精确枚举判断 |
| `filters.id` | `id` | 文本包含匹配；高级搜索 `ID:123` 的精确匹配仍由 `q` 表达 |
| `filters.email` | `email` | 沿用邮箱或姓名的现有包含匹配 |
| 其他 `filters.*` | 同名列参数 | 字符串数组，同列 OR、不同列 AND |
| `filters.promotion` | `promotion`，兼容 `trial` | 正规化旧别名后使用当前优惠投影 |
| `order` | 当前后端固定排序 | v1 仅 `id DESC`；显式 ID 选择按首次出现顺序另行固定 |

空数组表示无该列限制，不表示“匹配空值”。重复枚举去重，输入顺序不影响请求摘要。
日期不得在新菜单单独转换为 UTC 或远端注册成功时间；迁移日期存储时先证明集合一致。
日期格式合法但 `date_from > date_to` 返回 422；历史缺失/无效日期保持现有谓词结果。
现有高级搜索继续支持方式、地区、邮箱、姓名、来源、备注、ID 等别名，不新增第二套解析器。

### 2.3 枚举复用策略

| 字段 | 已有值或来源 | 不得改变的含义 |
|---|---|---|
| `source` | 当前 facets 中的业务来源值 | 动态来源，不另写容易过期的前端白名单 |
| `registration_driver` | `roxy,roxy_oss,protocol,protocol_oss,protocol_oss_2,cloakbrowser,unknown` | 与当前驱动投影及历史兼容一致 |
| `token` | `has,none,expired,invalid_401,invalid_403,invalid_other` | `has` 使用当前 Token 状态投影，不保证远端实时有效 |
| `password` | `has,none` | 本地有无保存值，不等同密码已确认 |
| `promotion` | `free_trial,half_price,other_discount,other_promo,none,unknown,pending,failed,not_applicable` | 当前 Plus 优惠列，失败时可能保留上次成功结论 |
| `totp` | `enabled,disabled` | 当前启用标记投影，不保证完整材料及本轮确认 |
| `risk` | `detected,clear,pending` | 当前封号邮件检查投影，不等同账号生命周期 |
| `codex` | 当前 `codex_status` facets | 兼容列值，不能替换为 `codex_credential_state` |
| `account_status` | 当前状态 facets，常见 `active,deactivated,unknown` | 保留历史值，不把空值/其他状态强制改成停用 |
| `email_status` | `invalid,unmarked` | 邮箱失效标记，独立于 OpenAI 停用状态 |
| `plan` | 当前套餐 facets，含 `unqueried` 与历史变体 | 不假定只有 free/plus 两种 |

`eligible→free_trial`、`ineligible→none`、`discount→[half_price,other_discount]` 沿用现有别名。
动态值由共享字段目录声明 `enum_source=facets`，允许已保存的历史合法字符串继续精确筛选。
值作为绑定参数传入 SQL；不得把动态枚举拼成列名、表达式或排序片段。
新目录的静态 label 与现有列表共用定义；facets 只提供数量，不作为业务资格判断。

### 2.4 匹配与预检是两份结果

`target_count` 是准确的固定目标数；可选 `matched_count` 是 limit 前匹配数，未求全量时为null。
提供matched_count须标明与固定选择同快照或独立matched_count_at，不为首屏强制全库COUNT。
`preflight` 回答“按当前配置能否提交”，与选择集合分开。
功能不可用、材料缺失、被其他任务占用、后来被删除，均不能从固定目标集合静默移除。
原有 password/totp/codex 列不改含义；需要确认状态时作为新共享列增加并同时开放两处。
查询套餐即主动刷新，历史成功不属于 `already_satisfied`；缺 AT 先检查原有自动恢复能力。
预检只做本地集合查询，不调用登录、代理领取、查套餐、邮箱或远端凭证接口。

## 3. 目录与选择快照 API

### 3.1 `GET /api/bulk/catalog`

返回 `catalog_revision`、`query_schema`、操作列表、创建限额和部署能力。
目录不返回实时全库各字段计数；需要 facets 时使用共享筛选仓储的单独缓存请求。

```json
{"catalog_revision":"1","query_schema":{"version":1,"entity":"account"},
 "limits":{"explicit_ids_max":10000,"target_limit_max":100000,"page_size_max":100},
 "operations":[{"key":"plan_check","version":1,"label":"查询套餐",
   "target_kind":"account","availability":{"available":true,"reason_code":null},
   "parameter_schema":{"timezone_offset_min":{"type":"integer","minimum":-840,"maximum":840,"optional":true}},
   "effective_settings":{"source":"saved_config","config_revision":"188","countries":["JP","US"]},
   "capabilities":{"country_override":false,"cancel_not_started":true,"request_stop":true},
   "result_schema_version":1,"result_panel":"plan_check"}]}
```

上述限额是新平台建议初值，实施压测后定稿；达到上限返回明确错误，不截断范围。
`availability.available=false` 禁用创建该操作，但仍允许预览筛选和查看旧批次。
目录修改不使既有批次静默升级；无法运行旧版本时进入明确的版本不支持状态。
`effective_settings.config_revision` 是公开设置的修订；selection响应也返回本次预检使用的修订和设置。
创建页面以实际展示过的selection设置修订填写 `expected_config_revision`，不能用未展示的新目录值替换。

### 3.2 `POST /api/bulk/selections`

请求头必须含 `Idempotency-Key`。一次选择只绑定一种操作版本，供预检与比较基线采集。
同时绑定规范化parameters、配置修订和非密钥快照/私有引用；预检不得在准备过程中改用最新配置。

```json
{"operation":{"key":"plan_check","version":1},"expected_config_revision":"188",
 "parameters":{"timezone_offset_min":-480},
 "source":{"kind":"query","query":{"schema_version":1,"entity":"account",
   "archived":"0","date_from":"2026-10-01","date_to":"2026-10-31",
   "q":"","plan":[],"filters":{"promotion":["none"]},
   "order":[{"field":"id","direction":"desc"}],"limit":null}}}
```

显式选择使用 `source={"kind":"ids","entity":"account","ids":["1","9"]}`。
不允许同时提供 `query` 和 `ids`；显式 ID 去重并保留首次出现顺序。
显式不存在 ID 也保存目标身份和 `account_missing`，不能以预览时不存在而丢失请求内容。
更换功能需重新准备选择快照，UI 可保留共享条件，不沿用其他功能的预检基线。
parameters使用catalog同一白名单；expected_config_revision来自用户已见的目录设置，漂移返回409。
预检公开config_revision/parameters_hash；创建时规范化参数必须与selection一致，变化返回409/selection_settings_mismatch。
改功能参数或确认新版配置后重新预览；首期不增加复用旧成员的重新预检接口，旧selection保留至原到期规则。

同一固定名单新建批次使用 `source={"kind":"batch_targets","batch_id":"4201","selection":{"kind":"all"}}`。
也支持 `selection={"kind":"targets","target_ids":["900","901"]}`，ID必须属于来源批固定根目标。
结果子集使用 `selection={"kind":"result_filter","view":"current","round_id":null,"states":["failed"]}`；
view=round时必须指定该批round_id，功能result_filters仍须符合来源批结果schema，不能查当前账号列重选。
服务端按来源批ordinal复制身份为新selection，在一次投影快照固定结果子集并记录basis_revision/selection_at。
all不重新应用旧账号条件；targets不扩充；结果子集以后台固定时点为准，允许观察修订/数量作为提示基线。
新selection使用新操作版本、新预检和新比较基线；原批保留，新根canonical_target_id为空，不借用旧owned Run。
不存在的来源目标返回422/target_outside_source_batch；已删除账号身份仍保留并报告account_missing。

受理返回 202：

```json
{"id":"71","state":"preparing","selection_revision":0,"target_count":null,"matched_count":null,
 "created_at":"2026-11-10T09:00:00+08:00","selection_at":null,
 "status_url":"/api/bulk/selections/71","reused":false}
```

固定集合使用单次 MVCC 语句或明确同事务快照；批量预检发生在该快照后的检查时间单列。
`selection_at` 表示真正固定范围的时点，不等于受理时间；准备失败时没有可提交的半份名单。
API `selection_at/basis_revision` 分别映射存储 `selected_at/basis_summary_revision`，两套名称不得混用。
选择准备不占业务账号许可；预检不是预留名额。

### 3.3 `GET /api/bulk/selections/:id`

可选 `cursor`、`page_size`，返回状态与固定名单的分页样本，不返回全部 ID 数组。

```json
{"id":"71","state":"ready","selection_revision":1,"target_count":240,"matched_count":null,
 "selection_at":"2026-11-10T09:00:01+08:00","expires_at":"2026-11-10T09:30:01+08:00",
 "effective_settings":{"config_revision":"188","countries":["JP","US"]},
 "preflight":{"checked_at":"2026-11-10T09:00:02+08:00","config_revision":"188","parameters_hash":"opaque",
   "ready":230,
   "waiting_account":8,"not_executable":2,"unassessed":0},
 "items":[{"target_id":"900","account_id":"4901","ordinal":1,
   "preflight":{"status":"ready","reason_code":null},
   "display":{"email":"示例账号","promotion":"none","plan_last_success_at":"2026-10-20"}}],
 "page":{"page_size":20,"next_cursor":"opaque","has_more":true}}
```

预检四分类互斥且合计为固定目标数；更细原因通过 reason 统计提供，不改变匹配数。
`unassessed` 表示资格摘要尚在准备，可提交前必须给出清楚提示；资格仍在执行前原子重检。
ready 快照 TTL 建议 30 分钟，目录公开；已被批次消费后不按此 TTL 清理。
字段变动后页面必须清除旧 selection 引用；不能仅更新页面条件但提交旧名单。

## 4. 批次、明细与轮次 API

### 4.1 `POST /api/bulk/batches`

请求：

```json
{"name":"10月无优惠账号刷新套餐","selection_id":"71","selection_revision":1,
 "operation":{"key":"plan_check","version":1},"expected_config_revision":"188",
 "parameters":{"timezone_offset_min":-480},"execution":{"max_concurrency":3}}
```

名称可省略或为空，由服务端按“功能名称 + 创建时间”生成；显式名称去空白后最长120字符。
并发是正整数，范围由目录返回，必须落入已有许可可表达范围。
`max_concurrency` 是本批上限，不修改全局/类型配置，也不保证同时达到该数量。
创建短事务校验 selection ready/未过期/版本一致，冻结操作设置并消费选择，不逐项建任务。
批次仅保存允许公开的参数/非密钥配置快照及私有配置引用，不能把密钥明文复制进batch JSON。
同一 selection 只能消费一次；同一幂等请求返回原批次，其他请求返回 `selection_consumed`及details.existing_batch_id。
零匹配selection可ready供展示，但创建返回422/selection_empty且不消费；重跑零目标轮另按第4.5节处理。

返回 202：

```json
{"id":"4201","round_id":"5001","round_no":1,"control_state":"active",
 "expansion_state":"pending","target_count":240,"reused":false,
 "selection_id":"71","config_revision":"188","summary_revision":0,
 "links":{"detail":"/api/bulk/batches/4201","targets":"/api/bulk/batches/4201/targets"}}
```

`expected_config_revision` 是用户实际见过的有效设置修订，创建事务必须校验。
配置已变化返回409/config_revision_changed及最新公开设置，保留selection；页面展示新设置、重新预览后再提交。
不得在用户未见过新设置时自动捕获新配置执行；参数反馈只针对配置变化，不因账号动态变化阻塞创建。
新配置导致整项功能不可用时返回明确409/422，快照保留可重新处理设置。
部分账号资格改变时仍创建批次，让每个固定目标获得等待或未执行结果。

### 4.2 `GET /api/bulk/batches`

参数：`cursor`、`page_size`（默认 20，最大 100）、`operation_key[]`、`control_state[]`、
`created_from`、`created_to`、`q`。批次时间范围用带时区时间，和账号日期列不是同一字段。
排序固定 `(created_at DESC,id DESC)`；名称/ID 搜索限制长度并绑定参数。
只返回当前页预计算摘要，`total_count` 可省略，不每次聚合全部历史求准确总页数。

### 4.3 `GET /api/bulk/batches/:id`

`view=current|round`，默认 current；view=round 必须传 `round_id`。
返回 `operation/selection_summary/control/effective_settings/summary/rounds_head/links`。
轮次超过首屏时用轮次分页资源，不把全部轮次塞进每次轮询。

```json
{"id":"4201","view":{"kind":"current","round_id":null},"target_count":240,
 "summary_revision":32,"projected_at":"2026-11-10T09:02:00+08:00",
 "summary":{"pending_submit":20,"waiting_account":8,"queued":70,"running":3,
   "waiting":2,"success":120,"partial_success":4,"failed":10,
   "not_executed":2,"cancelled":0,"attention_required":1},
 "projection":{"state":"current","lag_seconds":1},
 "control":{"state":"active","revision":1,"pending":false},
 "business_summary":{"schema":"plan_check.v1","confirmed_no_offer_accounts":80},
 "rounds_head":[{"id":"5001","round_no":1,"target_count":240,"state":"active"}]}
```

公共分类合计必须等于本视图目标数；`running+waiting` 可在页面合并，API 保留分别数量。
未生成 target_round 行的目标由固定目标数和展开游标计入 pending_submit，不等待全量插入后才出现。
ETag 由视图、摘要修订和控制修订生成；`If-None-Match` 命中返回 304，不发空 200 假装更新。
投影失败/滞后时保留上次摘要，显示 `projection.state=delayed|failed` 与更新时间，不清零。

### 4.4 `GET /api/bulk/batches/:id/targets`

参数：`view`、`round_id`、`state[]`、`reason_code[]`、功能 `result_filters`、`q`、cursor/page_size。
`result_filters` 只能使用该结果 schema 声明的字段，不复用账号当前条件重新过滤成员。
默认顺序 `(ordinal,target_id)`；状态筛选的游标绑定该状态条件，但结果变化不承诺跨页强快照。
分页期间状态变动可导致某项离开筛选；精确导出/重跑使用新的固定子集，不从已加载页拼接。

```json
{"items":[{"target_id":"900","target_round_id":"8001","account_id":"4901",
 "round_id":"5001","ordinal":1,"state":"failed","source_status":"failed",
 "reason":{"code":"plan_request_timeout","message":"套餐接口响应超时。","stage":"plan_request"},
 "owned_runs":[{"task_id":"6201","run_id":"7201","step_key":"plan_check","relation":"owned_root"}],
 "blocker":null,"result":{"schema":"plan_check.v1","query_outcome":"failed"},
 "actions":{"retry":{"available":true,"mode":"automatic"}},"duration_ms":12000}],
 "page":{"page_size":50,"next_cursor":null,"has_more":false},"summary_revision":32}
```

`owned_runs` 首屏只返回当前关联摘要和数量；大量子运行通过明细详情按需加载。
另加 `GET /api/bulk/batches/:id/rounds` 和 `/targets/:target_id` 分别分页历史轮次与目标详情。

### 4.5 `POST /api/bulk/batches/:id/rounds`

默认“重跑未成功”仅选首轮/当前结果中的终态未成功项，不把正常排队执行项当失败。
允许明确选择 target_id；受理后发生占用冲突时逐项目标等待，不拒绝整个请求。

```json
{"source":{"view":"current","round_id":null,"observed_summary_revision":32,"observed_target_count":17},
 "selection":{"kind":"result_filter","states":["failed","partial_success","attention_required","not_executed"]},
 "retry_mode":"automatic","name":"第一次重跑"}
```

`selection` 也可为 `{"kind":"targets","target_ids":["900","901"]}`，不得传任意新账号 ID。
`retry_mode` 首期仅 automatic，由领域自动选手动重跑/恢复/补回执，UI 不要求用户逐账号判断。
请求幂等保存轮次意图；失败子集通过独立固定事务形成，计数未准备好时返回 `target_count:null`。
`observed_summary_revision` 只记录用户所见修订，不作为整批摘要CAS门槛。
result_filter明确选择“后台固定时点、指定view中符合所选终态的原批目标”，页面事先说明。
后台在同一投影事务快照固定成员与来源Run，记录实际 `basis_revision/selection_at`。
数量变化返回 `counts_changed_since_request=true`，并返回实际basis_revision供审计，不阻断准备。
`observed_target_count` 是可选显示基线，不能参与选择或授权；未提供则数量变化提示为null。
不得扩展到其他批次、其他view、未选状态；显式targets严格固定所给ID，不自动增加新失败项。
固定后不再跟随实时结果变化；同目标已有活动轮则逐项waiting，不错误拒绝整批。
需要精确重跑用户先前看到的集合时，使用先准备ready选择快照再消费的后续能力。
首期不声称保存任意旧修订的完整成员版本，也不依赖短暂静止的全批摘要才能接受请求。
轮次意图与成员固定失败可恢复；新轮被明确取消时不会继续创建新 Run。

返回 202 含 `round_id/round_no/state=preparing/target_count/reused/status_url`。
同批重跑使用原 task 的新 Run；不同批次重复执行产生新的 task，不借用旧批 task 假装本批运行。
首轮尚未创建Task的未执行目标在重跑时创建该批的首个Task，仍使用稳定目标身份，不要求虚构来源Run。
首期同批人工重跑与自动依赖续接均沿用批次冻结的功能参数/配置版本；全局实时并发许可仍取最新策略。
原领域重跑入口会重新捕获配置时，managed适配必须显式注入原快照，不静默换驱动或国家；原检查点仍沿领域规则恢复。
需要当前新设置时使用“同一批账号再次执行”创建新批次，预览新设置后受理，不在旧批中悄悄变更配置。
零个可选目标的轮次为 `completed`，`completion_reason=empty`，目标数0，不虚构成功1。
轮次过程状态统一 `preparing/active/settling/completed/failed`，与其业务成功/失败计数分开。

## 5. 控制、幂等、分页与错误

### 5.1 `POST /api/bulk/batches/:id/control`

```json
{"action":"cancel_not_started","expected_control_revision":1,"scope":{"kind":"batch"}}
```

首期只开放 `cancel_not_started / request_stop`；scope 支持整批和指定 round_id，不支持任意 task_id。
`cancel_not_started` 阻止未启动账号链继续展开/首次领取，已开始链及必需子步骤按原规则收口。
`request_stop` 包含取消未开始效果，再对本范围owned活跃链提交协作取消；不停止blocker、不强杀线程。
控制命令持久化到 `operation_batch_control_commands`，返回command_id，不只改批次状态布尔值。
batch scope固定受理时的through_round_no；round scope只作用该轮，不能取消其他轮或未来新意图。
同键重发先返回原命令，再决定是否做revision CAS；不能让原请求的旧expected值破坏幂等重放。
返回 202 含新 control_revision、请求状态、待处理目标数；不能直接返回“全部已停止”。
下发控制不遍历整批串行调用取消；后台分块派发，领取和展开事务核对同一控制门闩。
revision 冲突返回409/current_revision；客户端重新读状态，可用新幂等键及新expected修订重试同一控制意图。
preparing轮在成员固定前取消，结束为completed，completion_reason=cancelled_before_freeze，target_count=null。
此时不假报“0个账号成功”，取消后的准备worker必须在提交前验证命令/fence而放弃发布名单。
暂停暂不在目录声明；后续只暂停新账号链，不截断已开始组合流程。

### 5.2 幂等与游标

所有创建/重跑/控制 POST 使用 16—128 字符的稳定 `Idempotency-Key`，唯一范围为部署+路由作用域。
服务端对规范化请求计算摘要；同键同内容返回原资源，异内容返回 409/idempotency_conflict。
失败子集、配置修订等服务端执行结果不重新计算进客户端请求摘要；重发读取首次受理记录。
幂等记录随被引用批次/轮次保留；不能因短 TTL 清理使丢回执重发创建重复批次。
客户端新点击“再运行/重跑”产生新键；不得由筛选字符串永久派生同一个键。
配置/控制revision冲突等未持久受理的校验失败，回滚且不占成功幂等键；明确409后新内容可使用新键。
用户看过新版设置后更新expected_config_revision；控制重试更新expected_control_revision，不改已受理请求内容。
超时、断连或回执不明必须以原键和原内容查询/重发，不能先换键，否则可能重复创建；已成功键优先重放。

游标是服务端签名的不透明字符串，绑定资源、视图、筛选摘要、排序与最后边界。
不得把跨批次或旧筛选 cursor 直接使用；返回 422/cursor_scope_mismatch。
固定 selection 分页稳定；动态结果分页允许状态变化，接口明确其一致性级别。
`page_size` 默认20/50，最大100；返回 `next_cursor/has_more`，没有数据返回空数组。

### 5.3 错误与逐项失败

| HTTP | 原因码示例 | 语义 |
|---|---|---|
| 400 | `invalid_json` | 无法解析请求体 |
| 401/403 | 现有鉴权原因码 | 无访问资格 |
| 404 | `batch_missing,selection_missing,target_missing` | 资源不存在或不属于此批次 |
| 409 | `selection_not_ready,selection_consumed,selection_settings_mismatch,idempotency_conflict,control_revision_conflict,config_revision_changed` | 当前资源/配置状态冲突 |
| 410 | `selection_expired` | 未消费快照过期，需重新预览 |
| 422 | `query_invalid,parameter_invalid,field_not_supported,cursor_scope_mismatch,selection_empty,target_outside_source_batch` | 请求契约不合法或创建范围为空 |
| 429 | `submission_capacity_exceeded` | 批次受理容量达到上限，带 Retry-After，未丢任务 |
| 503 | `bulk_store_unavailable,operation_unavailable` | 存储或整个功能暂不可用 |

账号已删除、已废、材料缺失、任务忙、单项持久化失败是目标结果，不能把其他目标全部回滚为 500。
连接断开/事务不可判定等系统故障回滚分块并靠幂等恢复，不能猜哪些账号已提交。
原因保留 `code/stage/exception_type/evidence_ref/fingerprint` 的公开摘要；不返回凭据或完整响应正文。
允许 `diagnostic_cause_unresolved` 表示证据不足，携带已证实症状和待分析指纹。
界面可写“响应超时，具体原因待分析”，不得伪造远端根因，也不显示无上下文“未知错误”。

## 6. 领域适配器的函数与事务契约

### 6.1 公共类型（Python 设计签名）

```python
@dataclass(frozen=True)
class BatchContext:
    batch_id: int
    round_id: int
    operation_key: str
    definition_version: int
    parameters: Mapping[str, object]
    config_snapshot: Mapping[str, object]  # 仅非密钥快照；私有材料由领域存储引用获取
    config_revision: str
    control_revision: int

@dataclass(frozen=True)
class TargetRef:
    target_id: int
    target_round_id: int
    entity: str
    entity_id: int
    ordinal: int
    submission_key: str

@dataclass(frozen=True)
class PreparedItem:
    target: TargetRef
    disposition: str  # ready / waiting_account / not_executable
    reason_code: str | None
    blocker_run_id: int | None
    private_input: object  # 仅本次函数栈使用，不写批次JSON或公开响应

@dataclass(frozen=True)
class SubmissionReceipt:
    target_round_id: int
    disposition: str  # created / idempotent_owned / waiting / not_executed
    task_id: int | None
    run_id: int | None
    relation: str | None  # owned_root / owned_child / owned_continuation
    blocker_run_id: int | None
    reason_code: str | None
```

`private_input` 可含从原事实表读取的执行材料，只存内存并受原领域边界保护；不复制到目标快照。
公开 `SubmissionReceipt` 不需要携带 email/token；target identity 与账号当前读取分开。

```python
def preflight_many(selection_targets, *, definition, settings, conn) -> list[PreflightResult]: ...
def prepare_many(targets: Sequence[TargetRef], *, context: BatchContext, conn) -> list[PreparedItem]: ...
def submit_chunk(items: Sequence[PreparedItem], *, context: BatchContext, conn) -> list[SubmissionReceipt]: ...
def retry_many(sources: Sequence[RetrySource], *, context: BatchContext, conn) -> list[SubmissionReceipt]: ...
def project_many(evidence: Sequence[TargetEvidence], *, schema_version: int) -> list[TargetResult]: ...
```

上述签名的其余值对象必须至少包含：

| 类型 | 必需字段 |
|---|---|
| `PreflightResult` | target_id、status、reason_code、checked_at、blocker_run_id；状态含unassessed |
| `RetrySource` | target、source_target_round_id、source_task_id、source_run_ids、retry_mode=automatic |
| `TargetEvidence` | target_round_id、source_revision、owned_run证据、活动依赖、步骤确认、选择基线 |
| `TargetResult` | target_round_id、schema、source_revision、state、source_status、terminal、reason、result、contribution |

输入输出必须对每个 target 一一覆盖且顺序可关联；遗漏项是 adapter_contract_violation。
`prepare_many` 批量读取字段与关联凭证，不逐项列全库；不能产生远端请求或持久业务副作用。
`submit_chunk/retry_many` 使用调用者事务，不自行 commit、开启后台执行、逐项通知 dispatcher。
共享协调层负责有界块、锁序、保存点和保存关联；每块提交后一次通知。
目标物化先以投影锁序保存target_round、初始贡献及materialization_cursor；该事务不调用领域提交。
后续独立managed提交事务创建业务任务；不能把物化cursor与业务提交状态放进同一个持锁事务。
托管批次事实更新统一先锁target，再按领域锁序锁账号/task/Run并递增source_revision；
已有Run锁之后不得反向锁target。旧事实入口需显式传递托管上下文，不能由同步投影补拿目标锁。
创建任务+账号queued状态+精确Run关联+目标提交状态必须同事务，缺 conn 的旧服务须先增事务入口。
逐项冲突使用保存点或集合预检；执行前仍保留原原子约束，不能以预检结果替代抢占。
`project_many` 纯计算公开结果；所需 Run、依赖、步骤证据由 repository 批量取齐，不内嵌N+1查询。
事实事务按上述target-first顺序完成更新，再追加 `operation_projection_outbox`；按source_revision幂等消费。
摘要投影与业务执行互不共用同步大锁，重复事件通过已应用贡献与修订去重。

### 6.2 与现有调用链衔接

| 用户功能 | 现有协调入口 | 新适配必须补的能力 |
|---|---|---|
| `plan_check` | `plans.service.enqueue_account_plan_check` | 批量prepare、共享conn、配置快照注入、原子claim与Run绑定 |
| `password_setup/twofa_setup` | `WebUIContext.enqueue_account_setup` | 协调下沉core；保持原source_system映射和handler行为；事务入口 |
| `codex_retry` | `codex.operation_service.submit/retry_task` | 批量账号定位、snapshot/conn注入、exact owned Run关联 |
| `account_completion` | `WebUIContext.enqueue_account_completion`及依赖续接 | 下沉core、原规划器、父续接/子Run上下文传递 |

不修改既有 `source_system="webui_runtime"` 来“顺手清理命名”，历史重跑依赖此字段。
旧单条入口也委托同一准备/提交能力；兼容参数和响应由薄适配保留，不只修新菜单。
纯协调可不占业务槽，但现有 account_completion 仍可能执行业务，迁移前不能直接免除其许可。

### 6.3 owned 与 blocker，手动与依赖路径

每个实际新 Run 在创建事务内登记 `target_round_id/step_key/relation/generation`。
manual 重跑保留同一个 task，新 Run 属新轮；dependency continuation 属原轮，不凭触发时间归新轮。
parent retry 和 child retry 必须显式返回/传播批次上下文；不能以账号邮箱猜所属轮次。
`reused=true` 只有幂等命中本 target 的 owned Run 才是 idempotent_owned。
遇到其他批次/单条活跃 Run 仅保存 blocker；完成通知只唤醒重检，不自动贡献本批成功数。
本批复用已确认材料属于领域“已满足”的证据，不把外部 Run 改为本批 owned_child。
已有 `manual_retry`、`dependency_ready` 两条路径必须保留各自原逻辑与检查点。
adapter 不以 `needs_reconciliation` 总开关拒绝手动重跑；未知回执交给原功能恢复规则。
Codex Token 刷新的 `allow_unknown_manual_retry` 属后续功能专用能力，不透传成所有动作公共开关。

## 7. 首期功能参数与结果 schema

### 7.1 当前可传参数与只读有效设置

| 功能 | v1 可传参数 | 从已有配置捕获并展示，暂不可传覆盖 |
|---|---|---|
| 查套餐 | `timezone_offset_min`，整数，映射现有字符串参数；省略沿用现有未提供行为 | 国家、查询driver、自动刷新AT、支付预检、超时/重试 |
| 补密码 | `{}` | 密码driver、密码恢复开关、认证与网络配置 |
| 补2FA | `{}` | twofa driver、浏览器回退、协议重认证 |
| 补Codex | 可选 `driver=roxy|protocol`，沿用已有显式入参；省略沿用配置 | 其他OAuth配置、目标后端、认证策略 |
| 组合补全 | `{}`，按现有 completion_settings 配置目标能力 | password/plan/twofa/codex/refresh_at开关及原依赖策略 |

时间偏移参数必须为 -840—840 的整数；正负号沿用BrowserSession.js_timezone_offset_min的JS口径，不能反转。
`timezone_offset_min` 省略时内部继续传 `"-"`，不把目录显示示例 -480 当自动覆盖所有用户。
需要“本批国家/能力集合”时，在内部已有 snapshot 字段上新增明确的覆盖适配和回归测试。
能力完成前 catalog 对应 override=false，UI 只读；未知参数返回422，不能收下后偷偷忽略。
第一版不暴露通用 `force/reset_password/ignore_busy`；补与更换/重置是不同操作定义。

### 7.2 通用 TargetResult

```json
{"schema":"plan_check.v1","state":"success","source_status":"success",
 "evidence_revision":5,"terminal":true,"reason":null,
 "result":{"query_outcome":"success"},"step_results":[],
 "contribution":{"state":"success","dimensions":{"plan.free":1}},
 "actions":{"retry":{"available":true,"mode":"automatic"}}}
```

`contribution` 是投影内部结构，普通API可省略；一次目标对状态计数只贡献1。
不同单位使用不同命名空间：`account.* / country_query.* / step.*`，不能直接相加当账号数。
重跑动作允许不等于自动重跑；用户明确请求后再按领域返回新的Run或等待原因。

### 7.3 `plan_check.v1`

结果字段：`query_outcome=success|partial_success|failed|unconfirmed`、`countries_requested`、
`country_success_count/country_failed_count`、`account_plan_type`、`plus_offer_kind`、`comparison`。
逐国项保存 `country/status/checked_at/plan_type/promotions/error_code/evidence_state`，详细内容按需取。
`promotions` 沿用 `plan/kind/discount_percentage/duration_num_periods/duration_period`。
`kind` 复用 `free_trial/discount/other_promo/none/unknown`；展示半价由percentage=50派生。
读取本轮真实成功证据，剔除旧 result/stale 活动；全部国家无优惠必须全部本轮成功。
部分国家失败但另一个有优惠，显示“部分成功，已发现优惠”，不归“全部无优惠”。
账号分布用明确规则：本轮最佳已证Plus优惠优先；无证据归未确认，不进入无优惠计数。
`comparison=unchanged|changed|new_offer|offer_removed|not_comparable`；比较同产品同国家及可靠基线。
基线来自固定目标快照，后来的账号更新不得回写原批比较结果；国家范围不一致则not_comparable。
附带额度查询失败不覆盖已经成功的套餐结果，作为独立字段/警告沿用原服务语义。

### 7.4 `password_setup.v1` 与 `twofa_setup.v1`

密码结果：`confirmation=confirmed|unconfirmed|not_executed`、`before_state/after_state`、
`change_kind=confirmed_existing|set_new|already_satisfied|not_recorded`、`failure_stage`。
状态可区分missing/candidate/confirmed，但是资格/结果派生，不改变现有password列has/none。
本轮既有证据不支持区分“新设置/验证原值”时用not_recorded，不能凭前后有值猜测。
密码写入未确认仍保留原候选检查点；批量层不能替换候选或自动改走重置密码。

2FA结果：`confirmation=confirmed|unconfirmed|not_executed`、
`material_state=missing|pending|usable|flag_only`、`change_kind`、`failure_stage`。
`usable` 需完整材料和原领域确认；存在secret但totp_setup_pending不能算新启用成功。
只看到totp_enabled标记时显示flag_only，不产生本轮确认成功贡献。
两类公开结果不得包含密码、secret、OTP或可恢复的私有材料。

### 7.5 `codex_retry.v1` 与 `account_completion.v1`

Codex结果：`attempt_outcome`、`credential_confirmation=confirmed|pending|not_confirmed`、
`receipt_state`、`asset_state_before/after`、`existing_asset_preserved`、`credential_ref`公开标识。
回执已提交/接受不等于凭证确认；旧资产valid与本轮failed可以并存，分别显示。
本轮成功以原服务的confirmed及实际凭证保存为依据，不只看兼容codex_status。

组合结果：`required_steps/completed_steps/pending_steps/blocked_steps`、`goal_satisfied`、
`dependencies_active`、每步骤`status/evidence_ref/owned_run_ids`，来自冻结要求与真实依赖。
父Run partial_success且子任务仍活跃时目标保持waiting；不提前进入已结束/部分成功计数。
业务全成功需所有本轮必需目标确认；原本满足和本轮新完成分开；被阻塞步骤不能从分母消失。
第一版沿用现有规划器，不增加任意DAG、全局流程顺序或隐式注册续跑。

## 8. 原始状态的完整映射

先判断owned依赖是否仍活跃、领域结果是否有未决写入，再按下表归一；保留原始source_status。
不得只按最新父Run的字符串判断整个账号链，也不得改写原Run以适配UI。

| 输入状态/来源 | 公共状态 | 规则 |
|---|---|---|
| 尚未创建Run | `pending_submit` | 已受理目标，不算queued |
| 其他活跃账号Run阻塞 | `waiting_account` | 保存blocker，本批没有owned执行 |
| `pending`（兼容任务） | `queued` | 仅明确已拥有待运行任务时；不是预检待处理 |
| `queued` | `queued` | 含同Run延期，提供not_before与等待原因 |
| `running` | `running` | 已认领且有效owner，不能用后台线程数代替 |
| `waiting` | `waiting` | 本轮依赖/外部结果仍待完成 |
| `settling` | `waiting` | 回执/资源正在收口，未结束 |
| `cancelling/stopping` | 原活动类别+`control_pending=true` | 确认退出前不算cancelled |
| `debug_paused`（兼容展示） | `waiting` | 标明调试暂停，底层可能仍running |
| `success` | `success` | 领域目标已确认；不等于仅提交成功 |
| `partial_success` | `waiting`或`partial_success` | 有待续接则waiting，无活动且实际部分目标达成才部分成功 |
| `failed` | `failed` | 保留具体错误、阶段和远端回执轴 |
| `attention_required/request_unknown` | `attention_required` | 结果未确认，不推断远端失败，不统禁手动重跑 |
| `cancelled` | `cancelled` | 原事实明确取消；若原因账号不存在仍保留对应reason |
| `stopped` | `cancelled`或`failed` | 有用户停止证据归取消；进程中断等归失败并保留中断原因 |
| `interrupted` | `waiting`或`failed` | 已有可靠恢复待续接则waiting，否则进程中断失败 |
| `deactivated` | `not_executed`或`failed` | 执行前确认不可运行归未执行；执行中确认停用归失败 |
| `unsupported` | `not_executed` | 功能/驱动明确不支持，给出原因 |
| `skipped`（兼容结果） | `not_executed` | 明确已满足或未执行；不可直接变success |
| `deferred`（handler返回） | 以DB `queued`为准 | 不是新终态，当前worker退出不等于任务完成 |

未知输入枚举属于 `adapter_status_unmapped` 合约错误，暂归attention_required，保留原值并告警。
该项明确 `reason.scope=data_contract`，不据此声称远端提交未知；修复映射后重建投影并校验计数。
实现需把已出现的原始状态纳入契约测试，不使用宽泛else=success/failed吞掉新状态。
“原因尚未分析”使用diagnostic_cause_unresolved，不等同“远端结果待确认”，两个维度不得混为一谈。

## 9. 实施前必须补证与验收

- 账号列表与选择SQL编译器逐字段集合对照：日期、Plus变体、历史优惠、动态来源/状态、搜索转义。
- plan现有claim与create分离；新事务入口必须保持原占用/回滚语义并减少SQL，不能仅包一层函数。
- setup/completion协调下沉必须保持source_system、handler注册、旧重跑入口与依赖续接兼容。
- Codex submit/retry当前配置捕获策略不同，批次新建、手动重跑、依赖续接分别标注实际配置修订。
- 参数schema只声明真正可执行的覆盖；未实现countries/能力集覆盖不能先做可编辑UI。
- 所有目标有一项公开结果；事务失败、重复回执、reused外部Run不造成漏计或重复owned关系。
- 原始状态映射、部分国家失败、父partial仍等待、旧资产有效但新执行失败必须有定向测试。
- HTTP请求重发不重复建轮；用户明确新建/重跑不被永久去重；未知回执不统一阻断。
- 本地和Oracle能力分别读取，Oracle不提供本机Roxy时明确配置不可用，不隐式换驱动。
- 字段输出检查及性能预算覆盖prepare/SQL数量、每块事务、摘要/明细分页，而非仅测返回202。

代码依据：[筛选仓储](../../../core/storage/admin_repository.py)、[搜索解析](../../../core/accounts/search.py)、
[套餐服务](../../../core/accounts/plans/service.py)、[国家结果](../../../core/accounts/plans/countries.py)、
[密码证据](../../../core/accounts/password_evidence.py)、[补全规划](../../../core/accounts/completion.py)、
[WebUI协调](../../../webui/runtime.py)、[Codex协调](../../../core/codex/operation_service.py)、
[任务网关](../../../core/operations/task_gateway.py)、[Run存储](../../../core/storage/operations/store.py)。
