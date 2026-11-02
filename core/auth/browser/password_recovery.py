"""浏览器密码恢复的私有检查点会话，不把候选凭据放入任务数据。"""
from __future__ import annotations

from core.storage.accounts import password_recovery as store


class PasswordRecoverySession:
    """绑定真实执行归属，所有读取和推进仍经过存储层执行围栏。"""

    def __init__(self, **owner):
        self._owner = dict(owner)
        self._checkpoint: store.PrivateCheckpoint | None = None

    @property
    def checkpoint(self) -> store.PrivateCheckpoint | None:
        return self._checkpoint

    def resume(self) -> bool:
        self._checkpoint = store.resume_password_recovery(**self._owner)
        return self._checkpoint is not None

    def prepare(self, candidate_factory) -> str:
        if self._checkpoint is None:
            self._checkpoint = store.prepare_password_recovery(
                **self._owner, candidate_factory=candidate_factory,
            )
        else:
            self._checkpoint = store.get_password_recovery(self._checkpoint.recovery_id, **self._owner)
        return self._checkpoint.password

    def _transition(self, state: str, confirmation: str | None = None) -> str:
        if self._checkpoint is None:
            raise store.PasswordRecoveryError("checkpoint_missing")
        self._checkpoint = store.transition_password_recovery(
            self._checkpoint.recovery_id, **self._owner,
            expected_version=self._checkpoint.version, state=state, confirmation=confirmation,
        )
        return self._checkpoint.password

    def mark_started(self) -> None:
        self._transition("started")

    def mark_unknown(self) -> None:
        self._transition("unknown")

    def confirm(self, confirmation: str) -> str:
        return self._transition("confirmed", confirmation)


__all__ = ["PasswordRecoverySession"]
