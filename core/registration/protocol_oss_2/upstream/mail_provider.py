"""Compatibility alias for the kernel-owned upstream implementation."""
from importlib import import_module
import sys

_implementation = import_module("core.kernels.protocol.protocol_oss_2.upstream.mail_provider")
sys.modules[__name__] = _implementation
