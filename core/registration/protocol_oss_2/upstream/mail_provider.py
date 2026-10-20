"""上游邮箱协议类型；实际取码由本地邮箱服务提供。"""
from abc import ABC, abstractmethod

class MailProvider(ABC):
    @abstractmethod
    def create_mailbox(self) -> str:
        """返回已由本地任务领取的邮箱。"""

    @abstractmethod
    def wait_for_otp(self, email_addr: str, timeout: int = 120, issued_after=None) -> str:
        """通过原邮箱来源等待验证码。"""
