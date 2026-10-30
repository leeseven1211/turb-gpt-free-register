"""只在隔离测试库构造迁移前子地址事实，不调用已退役的服务生成入口。"""
from core.storage import records as record_store
from core.storage.email import address_allocations as store


def seed_legacy_inventory(source, count, request_id, *, parent_id=None, **allocation_options):
    """直接使用仓储构造历史未领取地址；返回实际存在的记录，不解释业务结果。"""
    request = {"request_id": request_id, "source": source, "count": count, "parent_id": parent_id}
    rows = []
    with record_store.transaction() as conn:
        for number in range(count):
            row = store.allocate_address(
                source=source, acquisition_id=None, owner_kind=None, owner_id=None,
                parent_id=parent_id, generation_key=f"legacy-fixture:{request_id}:{number}",
                generation_request=request, conn=conn, **allocation_options,
            )
            if row is None:
                break
            rows.append(row)
    return rows


def seed_legacy_generation_receipt(source, count, request_id, result, *, parent_id=None):
    """历史返回值由各用例明确给出，覆盖零结果和部分结果的不可变恢复。"""
    return record_store.insert_row(record_store.EMAIL_ADDRESS_GENERATION_REQUESTS, {
        "request_id": request_id, "source": source, "requested": count,
        "parent_id": parent_id, "result": dict(result),
    })
