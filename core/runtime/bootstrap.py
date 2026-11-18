"""Validated immutable process bootstrap; no configuration or DB import."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import sys
from collections.abc import Mapping

_INSTANCE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$')


@dataclass(frozen=True)
class RuntimeBootstrap:
    mode: str
    instance_id: str
    runtime_dir: Path
    release: str
    legacy_paths: bool = False

    @classmethod
    def from_environment(cls, *, project_root: Path, environment: Mapping | None = None):
        env = os.environ if environment is None else environment
        root = Path(project_root).resolve()
        mode = str(env.get('TURB_RUNTIME_MODE') or 'combined').strip().lower()
        if mode not in {'combined', 'web', 'worker'}:
            raise ValueError('runtime_mode_invalid')
        instance = str(env.get('TURB_INSTANCE_ID') or 'default').strip()
        if not _INSTANCE.fullmatch(instance):
            raise ValueError('runtime_instance_invalid')
        raw = str(env.get('TURB_RUNTIME_DIR') or '').strip()
        if mode != 'combined' and not raw:
            raise ValueError('runtime_directory_required')
        directory = Path(raw) if raw else root / 'logs' / 'run'
        if not directory.is_absolute():
            raise ValueError('runtime_directory_absolute_required')

        manifest_marker = root / 'release-manifest.json'
        if manifest_marker.exists() or manifest_marker.is_symlink():
            previous_dont_write_bytecode = sys.dont_write_bytecode
            sys.dont_write_bytecode = True
            try:
                from tools.release import check_release

                report = check_release(root, validate_project=True)
            except (OSError, ValueError, TypeError, ImportError) as exc:
                raise ValueError('runtime_release_manifest_invalid') from exc
            finally:
                sys.dont_write_bytecode = previous_dont_write_bytecode
            release = str(report.get('source_commit') or '').strip()
            if not re.fullmatch(r'(?:[a-fA-F0-9]{40}|[a-fA-F0-9]{64})', release):
                raise ValueError('runtime_release_manifest_invalid')
        else:
            try:
                source_root = subprocess.run(
                    ['git', '-C', str(root), 'rev-parse', '--show-toplevel'],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=True,
                ).stdout.strip()
                if not source_root or not Path(source_root).is_absolute() or Path(source_root).resolve() != root:
                    raise ValueError('runtime_release_unavailable')
                release = subprocess.run(
                    ['git', '-C', str(root), 'rev-parse', 'HEAD'],
                    capture_output=True,
                    text=True,
                    timeout=3,
                    check=True,
                ).stdout.strip()
            except ValueError:
                raise
            except (OSError, subprocess.SubprocessError):
                raise ValueError('runtime_release_unavailable') from None
            if not re.fullmatch(r'[a-fA-F0-9]{40,64}', release):
                raise ValueError('runtime_release_invalid')
        return cls(mode, instance, directory.resolve(), release, mode == 'combined' and not raw)

    def prepare_log_environment(self, environment: dict | None = None) -> None:
        """Call before importing any domain that caches its shared log root."""
        env = os.environ if environment is None else environment
        if self.mode == 'combined':
            return
        raw = str(env.get('TASK_RUN_LOG_ROOT') or '').strip()
        if raw and not Path(raw).is_absolute():
            raise ValueError('runtime_log_directory_absolute_required')
        env.setdefault('TASK_RUN_LOG_ROOT', str(self.runtime_dir / 'logs'))
