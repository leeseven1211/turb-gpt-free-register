"""独立支付领域，不依赖 WebUI 或具体提链平台。"""
from core.payments.xxsyun import PaymentError, XXSYUNClient, select_payment_url

__all__ = ["PaymentError", "XXSYUNClient", "select_payment_url"]
