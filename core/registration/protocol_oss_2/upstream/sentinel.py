"""Compatibility alias for the kernel-owned upstream implementation."""
from importlib import import_module
import sys

_implementation = import_module("core.kernels.protocol.protocol_oss_2.upstream.sentinel")
sys.modules[__name__] = _implementation
