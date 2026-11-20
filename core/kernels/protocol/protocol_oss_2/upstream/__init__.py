"""固定上游协议引擎；本地修改与来源见 UPSTREAM.md。"""
import logging


# Upstream response/body logging is private even when AuthFlow is imported alone.
_logger = logging.getLogger(__name__)
_logger.addHandler(logging.NullHandler())
_logger.propagate = False
