# 销售第一版内部协作契约

## 仓储 API

`core.sales.store` 所有公开返回为字典或列表，时间公开为 ISO 字符串。初始化调用 `init()`，测试使用隔离 schema；不连接生产。需要事务时函数提供可选 `conn` 参数，内部使用 `records.transaction()`，表名均经 `postgres.qualified`。

```python
init() -> None
list_sources() -> list[dict]
save_source(data: dict) -> dict
get_source(source_id: str) -> dict | None
list_shops() -> list[dict]
save_shop(data: dict) -> dict
get_shop(shop_id: int) -> dict | None
patch_shop(shop_id: int, changes: dict, *, conn=None) -> dict
replace_products(shop_id: int, products: list[dict]) -> list[dict]
list_products(shop_id: int) -> list[dict]
get_product(product_id: int) -> dict | None
add_item(*, source_id: str, account_id: int, email: str,
         plan: str = "", note: str = "", conn=None) -> dict
get_item(item_id: int, *, private=False, conn=None) -> dict | None
get_items(item_ids: list[int], *, private=False, conn=None) -> list[dict]
list_items(*, page=1, page_size=20, status="", shop_id=None, source_id="", q="") -> dict
patch_item(item_id: int, changes: dict, *, event: str = "", conn=None) -> dict
freeze_listing(item_id: int, *, shop_id: int, product_id: int,
               fingerprint: str, delivery_ciphertext: str,
               binding: dict | None = None, historical=False, conn=None) -> dict
confirm_inventory(item_id: int, *, shop_id: int, product_id: int,
                  external_inventory_id: str, sold=False, order_ref="",
                  order_amount=None, currency="CNY", paid_at=None,
                  archive=True, conn=None) -> dict
list_archive_pending(*, limit=100) -> list[dict]
list_listing_pending(*, limit=100) -> list[dict]
list_events(item_id: int) -> list[dict]
```

来源数据：`id/name/kind/base_url/auth_env/enabled`。内置 `local`，`kind=local`，其他来源 `kind=remote`；`id` 限小写字母、数字、下划线、短横线，长度 1–40。

店铺数据：`id/name/platform/base_url/token_env/external_shop_id/enabled/owner_id/sync_interval/last_synced_at/error_code/error_message`。默认平台 `liandong`、地址 `https://wzyp.cn`、owner `local`、周期 60 秒、初始 disabled。`token_env` 和来源 `auth_env` 为环境变量名称，不是真实值。布尔校验严格。

商品标准结构：`id` 为本地 ID，`shop_id/external_product_id/goods_key/name/status/price`。`replace_products` 更新同步快照，缺失商品标记不可用，不删除已关联销售记录。

条目公开结构：`id/source_id/account_id/email/plan/status/shop_id/product_id/shop_name/product_name/external_inventory_id/order_ref/order_amount/currency/channel/price/sold_at/paid_at/note/listed_at/archived/archive_pending/sync_status/error_code/error_message/created_at/updated_at`。`status` 默认 `for_sale`，`sync_status` 默认 `idle`。

条目私有字段：`fingerprint/delivery_ciphertext/listing_binding/archive_owner_id`，仅 `private=True` 返回。公开投影禁止包含这些字段。`listing_binding` 独立保存最初商户 ID、外部商品 ID 和 `goods_key`，不依赖统一任务的历史保留期。

`freeze_listing` 原子锁定当前条目，仅允许待售或同一原目标的重跑；相同指纹被其他条目占用时抛固定分类的 `SalesError`。在售或已售条目不能改派不同店铺/商品。已售不能再次外部上架。每条冻结之后有 `sync_status=pending`。

可信历史匹配可使用 `historical=True` 首次关联尚无外部归属的人工销售条目，不触发外部导入或反转原销售事实。人工误标仅在没有外部库存、订单及付款事实时可撤销。用户取消上架将未确认意图置为 `paused`，周期恢复不补导，手动重跑恢复原材料和原目标。若暂停前已在途导入成功，后续只读同步仍保存实际库存及其原归档义务。

`confirm_inventory` 在同事务保存外部映射、销售状态、首次上架时间和 `archive_pending=true`，不直接操作原账号。已售不得被旧库存快照降为已上架；退款作为单独事实不恢复待售。

历史同步调用 `confirm_inventory(..., archive=False)`，不隐式归档原有账号。本轮新上架和用户明确标记已上架/已售出才产生归档待办。恢复扫描从 `list_listing_pending` 读取所有有固定材料和目标、尚待确认或重试的条目；分组排队仍保留原意图。

`patch_item` 仅允许白名单字段并保存事件，不能使用不受信任字段构造 SQL。来源、账号身份不可改写。公开列表返回 `{items,total,page,page_size,counts:{all,for_sale,listed,sold}}`。

## 适配器 API

```python
class SalesError(ValueError):
    code: str
    status: int
    # __init__(code: str, message: str, status=400)

class LiandongAdapter:
    def __init__(self, shop: dict, *, transport=None): ...
    def check(self) -> dict: ...  # external_shop_id, capabilities
    def products(self) -> list[dict]: ...  # 标准商品，尚无本地 id
    def inventory(self, external_product_id: str) -> list[dict]: ...
    # 库存结构 {external_inventory_id, content, status: available|sold}
    def import_inventory(self, external_product_id: str, lines: list[str]) -> dict: ...
    # {duplicate_only: bool}；不能仅凭该返回值确认新增，service 必须读回
    def orders(self) -> list[dict]: ...
    # {order_ref,goods_key,status:paid|unpaid|closed|refunded|unknown,
    # quantity,sendout,cards:list[str],amount,fee,fee_payer,paid_at}

class AccountSource:
    def __init__(self, source: dict, *, transport=None): ...
    def accounts(self, account_ids: list[int]) -> list[dict]: ...
    # id,email,plan,archived,delivery_line；不存在的ID不返回
    def find_accounts(self, emails: list[str]) -> list[dict]: ...
    # 仅精确规范化邮箱候选，返回完整交付资料供内存比对
    def archive(self, account_id: int) -> bool: ...  # 对该来源归档并确认
```

适配器可注入传输：`transport(path: str, body: dict) -> dict` 表示已解析 JSON；默认传输自行提供鉴权、限时和业务码转换。来源远端传输额外支持 `method` 或用内部 request 对象；测试夹具按实际实现统一。

完整交付资料只在适配器返回及 service 内存中使用，不进入 HTTP 公开 API 或 operation data。协议错误、鉴权、超时、网络、商品不存在、重复项、匹配歧义和来源无匹配均有明确分类。

## 服务和运行时

`core.sales.service` 消费仓储与适配器，HTTP 封装在 `webui/routes/sales.py`。适配器工厂可替换以支持模拟小铺。

```python
add_accounts(source_id: str, account_ids: list[int]) -> dict
change_status(data: dict) -> dict
check_shop(shop_id: int) -> dict
submit_sync(shop_id: int, request_key: str | None = None) -> dict
submit_listing(shop_id: int, product_id: int, item_ids: list[int], request_key: str) -> dict
execute_sync(shop_id: int) -> dict
execute_listing(shop_id: int, product_id: int, item_ids: list[int]) -> dict
process_archives(*, limit=100) -> dict
list_jobs(*, limit=20) -> list[dict]
```

批量结果包含 `items`，逐项 `id/status/error_code/message`，附计数。任务受理返回 `accepted/task_id/run_id`。表单 request_key 使用前端生成的 UUID；不得把网络重复提交变成新目标。

`core.sales.runtime.register_handler()` 注册 `sales_sync`，`data.action=sync|list`；`start_periodic_sync()` 只定时提交同步任务，`stop_periodic_sync(timeout)` 真实停止。执行端身份与 store.owner_id 一致才准许写入或提交；不依赖 WebUI 是否显示按钮。

销售任务 `account_id=None,email=""`。启动与周期检查已冻结未完成意图，按原目标排恢复 Run，活动 Run 存在时不重复排队。源账号归档前先读取 archived，已归档直接完成待办，避免重写历史归档时间。历史匹配必须覆盖所有启用来源；任何来源不可达时不把剩余来源命中直接算成全局唯一。

`SALES_EXECUTOR_ID` 默认 `local`，`SALES_SYNC_WORKERS` 默认 1，配置由协调者集成。只允许 http/https 的无凭据 base_url；远端和店铺 URL 取已保存配置，不接受请求临时注入的任意地址。
