"""One content version for the page template, linked assets and Vue build."""
from __future__ import annotations

import hashlib
import re
import stat
from functools import lru_cache
from pathlib import Path
from typing import Any

_STATIC_LINK = re.compile(r"url_for\(\s*['\"]static['\"]\s*,\s*filename\s*=\s*(['\"])([^'\"]+)\1")
_ASSET_SUFFIXES = {".js", ".css"}


def _stamp(path: Path) -> tuple:
    try:
        info = path.stat()
    except FileNotFoundError:
        return (str(path),)
    if not stat.S_ISREG(info.st_mode):
        return (str(path),)
    # ctime and inode detect writes/replacements even when deployment preserves mtime.
    return (str(path), info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_ino, info.st_dev)


@lru_cache(maxsize=32)
def _template_info(stamp: tuple) -> tuple[bytes, tuple[str, ...]]:
    if len(stamp) == 1:
        return b"missing", ()
    content = Path(stamp[0]).read_bytes()
    links = tuple(sorted({match.group(2) for match in _STATIC_LINK.finditer(content.decode("utf-8"))}))
    return hashlib.sha256(content).digest(), links


@lru_cache(maxsize=256)
def _content_digest(stamp: tuple) -> bytes:
    if len(stamp) == 1:
        return b"missing"
    return hashlib.sha256(Path(stamp[0]).read_bytes()).digest()


def page_asset_version(app: Any) -> str:
    """Invalidate linked URLs together; unchanged requests perform metadata reads only."""
    static_root = Path(app.static_folder)
    template_root = Path(app.template_folder or "templates")
    if not template_root.is_absolute():
        template_root = Path(app.root_path) / template_root
    templates = {}
    names = set()
    for name in ("index.html", "partials/extract_stats.html"):
        stamp = _stamp(template_root / name)
        if len(stamp) > 1:
            templates[name], links = _template_info(stamp)
            names.update(links)
    for name in ("dashboard", "proxy", "extractStats", "emailHistory", "bulk"):
        bundle = static_root / name
        if bundle.is_dir():
            names.update(path.relative_to(static_root).as_posix() for path in bundle.iterdir()
                         if path.is_file() and path.suffix in _ASSET_SUFFIXES)
    assets = [(name, _stamp(static_root / name)) for name in sorted(names)]
    if not templates and not any(len(stamp) > 1 for _, stamp in assets):
        return "development"
    digest = hashlib.sha256()
    for name, content in [*templates.items(), *((name, _content_digest(stamp)) for name, stamp in assets)]:
        encoded = name.encode("utf-8")
        digest.update(len(encoded).to_bytes(4, "big"))
        digest.update(encoded)
        digest.update(len(content).to_bytes(4, "big"))
        digest.update(content)
    return digest.hexdigest()[:20]
