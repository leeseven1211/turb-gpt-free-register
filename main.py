# -*- coding: utf-8 -*-
"""CLI 批量注册入口；统一注册分发由 `core.registration.dispatcher` 承担。"""
import sys
import argparse
import logging
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait

from config import REGISTER_EMAIL, REGISTER_NAME  # 这两个一般不在 WebUI 改
# 可热改的，按模块属性方式读
from config import email as _email_cfg
from core.email_provider import acquire_email
from core.humanize import delay as human_delay
from core.name_samples import random_display_name
from core.profile_utils import generate_random_birthday
from core.registration.dispatcher import run_registration as _run_registration

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

_FINALIZE_SESSION_MAX_ATTEMPTS = 5
_FINALIZE_SESSION_BACKOFF_BASE = 2.0


def configure_logging(verbose: bool = False) -> None:
    """配置 CLI 日志：默认简洁，--verbose 时显示完整步骤细节。"""
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if verbose else logging.INFO)
    for handler in root.handlers:
        handler.setLevel(logging.DEBUG if verbose else logging.INFO)

    if verbose:
        logging.getLogger("core").setLevel(logging.DEBUG)
        return

    logging.getLogger("core").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)


def _is_success(result: dict) -> bool:
    """判断单次注册结果是否成功，集中收敛批量统计规则。"""
    return isinstance(result, dict) and bool(result.get("success"))


def generate_display_name() -> str:
    """生成只包含英文字母和空格的显示名，符合注册接口限制。"""
    return random_display_name()


def prepare_registration_inputs(*, email_source: str | None = None,
                                owner_kind: str | None = None,
                                owner_id: str | int | None = None,
                                acquisition_id: str | None = None) -> tuple[str, str, str]:
    """按 CLI 规则准备一次注册所需的邮箱、显示名和生日。"""
    email = REGISTER_EMAIL
    name = REGISTER_NAME
    birthday = generate_random_birthday()

    # 邮箱：留空 + USE_EMAIL_SERVICE=True 时从 Outlook 池领取
    if not email:
        if _email_cfg.USE_EMAIL_SERVICE:
            selected_cli_source = str(email_source or "").strip().lower()
            if not selected_cli_source:
                from core.email_provider import parse_email_sources
                selected_cli_source = parse_email_sources(getattr(_email_cfg, "EMAIL_SOURCE", ""))[0]
            from core.email_provider import requires_acquisition_identity

            if (not requires_acquisition_identity(selected_cli_source)
                    and owner_kind is None and owner_id is None and acquisition_id is None):
                email = acquire_email(email_source) if email_source is not None else acquire_email()
            else:
                email = acquire_email(
                    email_source,
                    owner_kind=owner_kind,
                    owner_id=owner_id,
                    acquisition_id=acquisition_id,
                )
            logger.debug(f"自动获取邮箱: {email}")
        else:
            email = input("请输入注册邮箱: ").strip()

    # 显示名称：未填则随机生成
    # OpenAI 限制：name_invalid_chars —— 只允许字母和空格，不能含数字/标点
    if not name:
        if _email_cfg.USE_EMAIL_SERVICE:
            name = generate_display_name()
            logger.debug(f"自动生成显示名称: {name}")
        else:
            name = input("请输入显示名称: ").strip()

    if not all([email, name]):
        raise RuntimeError("邮箱和名称不能为空")

    return email, name, birthday


def run_registration(
    email: str,
    name: str,
    birthday: str | None = None,
    proxy: str | None = None,
    otp_code: str | None = None,
    existing_password: str | None = None,
    existing_totp_secret: str | None = None,
    email_source: str | None = None,
):
    """兼容入口：转发到 core.registration.dispatcher。"""
    kwargs = dict(
        email=email,
        name=name,
        birthday=birthday,
        proxy=proxy,
        otp_code=otp_code,
        existing_password=existing_password,
        existing_totp_secret=existing_totp_secret,
    )
    if email_source is not None:
        kwargs["email_source"] = email_source
    return _run_registration(**kwargs)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="ChatGPT 协议注册 CLI")
    parser.add_argument("-n", "--count", type=int, default=1, help="连续注册数量，默认 1")
    parser.add_argument("--workers", type=int, default=1, help="并发注册线程数，默认 1（串行）")
    parser.add_argument("--delay", type=float, default=0, help="每次注册结束后的间隔秒数")
    parser.add_argument("--continue-on-fail", action="store_true", help="单个账号失败后继续注册下一个")
    parser.add_argument("--email-source", default=None, help="本批明确使用的邮箱来源，例如 remail")
    parser.add_argument(
        "--remail-acquisition-id", "--mail-acquisition-id",
        default=None,
        help="继续原付费或派生邮箱领取意图的稳定 ID 前缀；原任务重跑时复用原值",
    )
    parser.add_argument("--verbose", action="store_true", help="显示详细步骤日志和错误堆栈")
    args = parser.parse_args()
    configure_logging(args.verbose)

    # CLI 与 WebUI 写同一份数据；PostgreSQL 连不上就直接退出，避免半路写丢。
    from core import postgres_store
    postgres_store.require_ready()

    if args.count < 1:
        logger.error("注册数量必须大于 0")
        sys.exit(1)

    if args.workers < 1:
        logger.error("并发线程数必须大于 0")
        sys.exit(1)

    if args.count > 1 and REGISTER_EMAIL:
        logger.error("config.REGISTER_EMAIL 已固定邮箱，不适合批量注册；请留空后再使用 --count")
        sys.exit(1)

    if args.workers > 1 and not _email_cfg.USE_EMAIL_SERVICE:
        logger.error("多线程注册需要启用 Outlook 自动取件；请开启 USE_EMAIL_SERVICE 或改用 --workers 1")
        sys.exit(1)

    if args.workers > args.count:
        logger.info(f"[批量] 并发线程数 {args.workers} 大于目标数量，已按 {args.count} 个任务执行")
        args.workers = args.count

    if args.workers > 1:
        results = run_parallel_batch(
            args.count, args.workers, args.delay, args.continue_on_fail,
            args.email_source, args.remail_acquisition_id,
        )
    else:
        results = run_serial_batch(
            args.count, args.delay, args.continue_on_fail,
            args.email_source, args.remail_acquisition_id,
        )

    success_count = sum(1 for r in results if _is_success(r))
    flow_success_count = sum(
        1 for r in results
        if _is_success(r) and isinstance(r.get("flow"), dict) and r["flow"].get("ok")
    )
    flow_failed_count = sum(
        1 for r in results
        if _is_success(r)
        and isinstance(r.get("flow"), dict)
        and r["flow"].get("status") == "failed"
    )
    flow_skipped_count = sum(
        1 for r in results
        if _is_success(r)
        and isinstance(r.get("flow"), dict)
        and r["flow"].get("status") == "skipped"
    )
    codex_success_count = sum(
        1 for r in results
        if _is_success(r) and isinstance(r.get("codex"), dict) and r["codex"].get("ok")
    )
    codex_failed_count = sum(
        1 for r in results
        if _is_success(r)
        and isinstance(r.get("codex"), dict)
        and r["codex"].get("status") == "failed"
    )
    codex_skipped_count = sum(
        1 for r in results
        if _is_success(r)
        and isinstance(r.get("codex"), dict)
        and r["codex"].get("status") == "skipped"
    )
    logger.info(f"[批量] 完成：成功 {success_count} / 尝试 {len(results)} / 目标 {args.count}")
    if success_count:
        logger.info(
            f"[批量] Flow：成功 {flow_success_count} / 失败 {flow_failed_count} / 跳过 {flow_skipped_count}"
        )
        logger.info(
            f"[批量] Codex：成功 {codex_success_count} / 失败 {codex_failed_count} / 跳过 {codex_skipped_count}"
        )
    sys.exit(0 if success_count == args.count else 1)


def run_one_batch_item(
    index: int,
    total: int,
    batch_id: str | None = None,
    batch_workers: int = 1,
    email_source: str | None = None,
    acquisition_id_prefix: str | None = None,
) -> dict:
    """执行批量注册中的一个任务，返回结构化结果。"""
    logger.info(f"[批量] 开始第 {index + 1}/{total} 个注册")
    proxy_lease = None
    from core import sms_provider

    if batch_id:
        sms_provider.set_sms_batch_context(batch_id)
    try:
        from core.proxy_provider import acquire_registration_proxy

        proxy_lease = acquire_registration_proxy(
            job_id=f"cli-{index + 1}",
            batch_id=batch_id if total > 1 else None,
            batch_size=total,
            batch_workers=batch_workers,
        )
        prefix = str(acquisition_id_prefix or f"cli:{batch_id or 'single'}").strip().rstrip(":")
        stable_acquisition_id = f"{prefix}:{index + 1}"
        email, name, birthday = prepare_registration_inputs(
            email_source=email_source,
            owner_kind="cli",
            owner_id=stable_acquisition_id,
            acquisition_id=stable_acquisition_id,
        )
        return run_registration(
            email=email,
            name=name,
            birthday=birthday,
            proxy=proxy_lease.proxy_url,
            email_source=email_source,
        )
    except Exception as exc:
        logger.error(f"[批量] 第 {index + 1} 个注册准备阶段失败: {type(exc).__name__}: {exc}")
        logger.debug("准备阶段错误详情:", exc_info=True)
        return {"success": False, "error": str(exc),
                **({"request_unknown": True, "status": "request_unknown"} if getattr(exc, "request_unknown", False) else {})}
    finally:
        if proxy_lease is not None:
            from core.proxy_provider import release_proxy

            release_proxy(proxy_lease, reason="cli_task_finished")
        if batch_id and total > 1:
            from core.proxy_provider import finalize_registration_proxy_batch

            finalize_registration_proxy_batch(batch_id)
        sms_provider.clear_sms_batch_context()


def run_serial_batch(count: int, delay: float, continue_on_fail: bool,
                     email_source: str | None = None,
                     acquisition_id_prefix: str | None = None) -> list[dict]:
    """按原有串行方式执行批量注册。"""
    results = []
    batch_id = f"cli:{time.time_ns()}"
    try:
        for index in range(count):
            result = run_one_batch_item(index, count, batch_id, 1, email_source, acquisition_id_prefix)
            results.append(result)
            if not _is_success(result) and not continue_on_fail:
                logger.error("[批量] 当前账号失败，已停止。需要继续跑可加 --continue-on-fail")
                break

            if delay > 0 and index < count - 1:
                logger.info(f"[批量] 等待 {delay} 秒后继续")
                time.sleep(delay)
    finally:
        if count > 1:
            from core.proxy_provider import discard_registration_proxy_batch

            discard_registration_proxy_batch(batch_id)
    return results


def run_parallel_batch(
    count: int,
    workers: int,
    delay: float,
    continue_on_fail: bool,
    email_source: str | None = None,
    acquisition_id_prefix: str | None = None,
) -> list[dict]:
    """使用线程池并发执行批量注册。"""
    logger.info(f"[批量] 启用多线程注册：目标 {count}，并发 {workers}")
    if delay > 0:
        logger.info(f"[批量] 并发模式下 --delay={delay} 表示提交任务之间的错峰间隔")

    results: list[dict] = []
    batch_id = f"cli:{time.time_ns()}"
    future_to_index = {}
    next_index = 0
    stop_submitting = False

    def submit_next(executor: ThreadPoolExecutor) -> bool:
        nonlocal next_index
        if stop_submitting or next_index >= count:
            return False
        future = executor.submit(
            run_one_batch_item, next_index, count, batch_id, workers,
            email_source, acquisition_id_prefix,
        )
        future_to_index[future] = next_index
        next_index += 1
        if delay > 0 and next_index < count:
            time.sleep(delay)
        return True

    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="reg-cli") as executor:
            while len(future_to_index) < workers and submit_next(executor):
                pass

            while future_to_index:
                done, _ = wait(future_to_index, return_when=FIRST_COMPLETED)
                for future in done:
                    index = future_to_index.pop(future)
                    try:
                        result = future.result()
                    except Exception as exc:
                        logger.error(f"[批量] 第 {index + 1}/{count} 个注册线程异常: {type(exc).__name__}: {exc}")
                        logger.debug("线程错误详情:", exc_info=True)
                        result = {"success": False, "error": str(exc)}
                    results.append(result)

                    if not _is_success(result) and not continue_on_fail:
                        stop_submitting = True
                        logger.error("[批量] 当前账号失败，已停止提交新任务。已开始的任务会继续跑完。")

                while len(future_to_index) < workers and submit_next(executor):
                    pass
    finally:
        if count > 1:
            from core.proxy_provider import discard_registration_proxy_batch

            discard_registration_proxy_batch(batch_id)

    return results


if __name__ == "__main__":
    main()
