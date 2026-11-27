# 历史设备资料补缺

设备资料缺失不等于账号禁止改密。普通改密仍可按原流程建立认证上下文；设备资料用于优先复用已保存的身份，不能替代密码、邮箱收码与远端核验。补缺和真实改密分别验收，不以设备表行数证明所有账号都能改密。

## 来源与保留范围

先使用[私有会话补缺工具](../../tools/migrations/backfill_account_device_profiles.py)处理绑定有效、包含完整设备资料的会话，再使用[旧账号资料补缺工具](../../tools/migrations/backfill_legacy_device_profiles.py)处理账号旧 JSON。

旧资料工具只读取同一来源同时保存的 `device_id` 与 `browser_profile`，依次检查 `extra_json` 和账号 `data` 顶层；两份完整资料不同则跳过，不跨来源拼接。六个基础字段须为正的有限数值：

- `screen_width`、`screen_height`、`device_pixel_ratio`
- `hardware_concurrency`、`device_memory`、`js_heap_size_limit`

设备值按固定白名单原样投影，保留已保存的设备、UA、Client Hints、WebGL、屏幕、语言、时区及上游传输资料。空字符串、`False` 与未观测字段各自保留，不按当前配置纠正旧画像。Cookie、Token、代理、`react_*`、地理查询结果、页面脚本与请求构建信息不进入设备画像。

任何已有设备行均保留，包括不完整行。明确属于 Rust 注册占位来源的旧 JSON 不参与本轮补缺；未知注册驱动可保留已有资料，但来源标为 `legacy_extra_json` 或 `legacy_account_data`，不称为完整原始注册快照。已保存的派生稳定身份与 Roxy 环境引用不自动转成注册指纹。

## 两端独立执行

使用各实例自己的配置、密钥与清单。默认只读扫描，不初始化业务表：

```sh
python tools/migrations/backfill_legacy_device_profiles.py \
  --source-root /实例目录 --source-instance local \
  --manifest /私有运行目录/legacy-manifest.json \
  --receipt /私有运行目录/legacy-dry-run.json
```

核对预览分类，完成匹配的数据库、密钥和启动配置备份后，应用固定清单：

```sh
python tools/migrations/backfill_legacy_device_profiles.py \
  --source-root /实例目录 --source-instance local --apply \
  --manifest /私有运行目录/legacy-manifest.json \
  --receipt /私有运行目录/legacy-apply.json
```

清单固定实例、schema、账号邮箱、源摘要与更新时间。应用时锁定账号并复核，仅向设备表插入缺失行，不修改账号、旧 JSON 或 Cookie。来源变化或并发新增设备行会分类跳过。清单与回执为 `0600`，不得输出原始设备与认证材料。

源更新时间带明确偏移时保留该时间；没有时区的历史字符串只作原文围栏，使用固定清单的观察时间记录迁移，并在加密包络的来源信息注明依据。账号行更新时间不等于设备实际使用时间，不按当前客户端时区推算历史时间。

## 验收

1. 核对新增行数量、来源与账号邮箱绑定，解密后将设备值与清单对应源逐值比对。
2. 核对源数据摘要、更新时间，以及已有设备行的迁移前后摘要。
3. 对同一清单重复应用，确认没有新增或覆盖；新一次只读扫描列明剩余分类。
4. 在隔离数据库验证画像能通过设备仓储读出并被改密路径选中，另验证不完整设备行会尝试完整会话画像，两者均不可用时保持普通认证回退。
5. 分别记录数据库恢复、运行时消费与真实改密的验收结果。

已保存资料中的可选尺寸或时区值可能不兼容当前消费者。迁移保留原值；改密会跳过不可构造的来源，尝试完整会话资料或普通认证，不为通过校验补写设备值。

本轮不改变注册主流程或严格画像重放。运行时仍可能按现有逻辑补充当前配置字段；保存旧值不代表 HTTP、VM 和 TLS 已完整重现原注册环境，详见[设备画像复用方案](../architecture/device-profile-reuse.md)。
