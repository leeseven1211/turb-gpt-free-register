from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from webui.assets import page_asset_version


class ConfigPageAssetLinkTests(unittest.TestCase):
    def test_actual_config_mount_uses_the_index_content_version_for_both_assets(self):
        from flask import Flask, render_template
        from html.parser import HTMLParser
        from urllib.parse import parse_qs, urlsplit

        class ConfigMountParser(HTMLParser):
            attributes = None

            def handle_starttag(self, tag, attributes):
                values = dict(attributes)
                if values.get("id") == "config-page-root":
                    self.attributes = values

        root = Path(__file__).resolve().parents[2] / "webui"
        app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"))
        with app.test_request_context("/"):
            rendered = render_template("index.html", task_center_version="synthetic-content-version")
        parser = ConfigMountParser()
        parser.feed(rendered)
        self.assertIsNotNone(parser.attributes)
        for key, suffix in (("data-module-url", "/task-center/config.js"),
                            ("data-style-url", "/task-center/task-center.css")):
            with self.subTest(asset=key):
                url = urlsplit(parser.attributes[key])
                self.assertTrue(url.path.endswith(suffix))
                self.assertEqual(parse_qs(url.query).get("v"), ["synthetic-content-version"])


class PageAssetVersionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="turb-page-assets-"))
        self.static = self.root / "static"
        self.bundle = self.static / "task-center"
        self.bundle.mkdir(parents=True)
        (self.root / "templates").mkdir()
        self.template = self.root / "templates/index.html"
        self.template.write_text("<script src=\"{{ url_for('static', filename='js/bridge.js', v=task_center_version) }}\"></script>\n", encoding="utf-8")
        self.legacy = self.static / "js/bridge.js"
        self.legacy.parent.mkdir()
        self.legacy.write_bytes(b"legacy-one")
        self.entry = self.bundle / "accounts.js"
        self.entry.write_bytes(b"entry-one")
        self.shared = self.bundle / "shared-a.js"
        self.shared.write_bytes(b"shared-one")
        self.css = self.bundle / "task-center.css"
        self.css.write_bytes(b"css-one")
        self.app = SimpleNamespace(root_path=str(self.root), static_folder=str(self.static), template_folder="templates")
        self.addCleanup(self.remove_synthetic_files)

    def remove_synthetic_files(self):
        # Each file and directory is removed individually; no recursive removal.
        paths = sorted(self.root.rglob("*"), key=lambda path: len(path.parts), reverse=True)
        for path in paths:
            if path.is_file() or path.is_symlink():
                path.unlink()
            else:
                path.rmdir()
        self.root.rmdir()

    def version(self):
        return page_asset_version(self.app)

    def test_actual_linked_legacy_template_entry_css_and_shared_chunk_changes(self):
        previous = self.version()
        for target in [self.legacy, self.template, self.entry, self.css, self.shared]:
            with self.subTest(target=target.name):
                target.write_bytes(target.read_bytes() + b"\nchanged")
                current = self.version()
                self.assertNotEqual(current, previous)
                previous = current

    def test_equal_content_and_metadata_only_changes_keep_same_version(self):
        version = self.version()
        self.legacy.touch()
        self.assertEqual(self.version(), version)
        self.legacy.write_bytes(b"legacy-one")
        self.assertEqual(self.version(), version)

    def test_same_mtime_and_size_content_overwrite_is_detected_by_ctime(self):
        before = self.legacy.stat()
        version = self.version()
        self.legacy.write_bytes(b"legacy-two")
        os.utime(self.legacy, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(self.legacy.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(self.legacy.stat().st_size, before.st_size)
        self.assertNotEqual(self.version(), version)

    def test_same_mtime_atomic_replacement_is_detected_by_identity(self):
        before = self.legacy.stat()
        version = self.version()
        replacement = self.legacy.with_suffix(".replacement")
        replacement.write_bytes(b"legacy-two")
        os.utime(replacement, ns=(before.st_atime_ns, before.st_mtime_ns))
        replacement.replace(self.legacy)
        self.assertEqual(self.legacy.stat().st_mtime_ns, before.st_mtime_ns)
        self.assertNotEqual(self.legacy.stat().st_ino, before.st_ino)
        self.assertNotEqual(self.version(), version)

    def test_unchanged_requests_do_not_reread_files_or_unlinked_vendor(self):
        vendor = self.static / "vendor.js"
        vendor.write_bytes(b"large unlinked vendor")
        reads = []
        original = Path.read_bytes

        def read(path):
            reads.append(path)
            return original(path)

        with mock.patch.object(Path, "read_bytes", read):
            version = self.version()
            first = list(reads)
            self.assertEqual(set(first), {self.template, self.legacy, self.entry, self.shared, self.css})
            self.assertEqual(len(first), 5)
            for _ in range(3):
                self.assertEqual(self.version(), version)
            self.assertEqual(reads, first)
            vendor.write_bytes(b"unlinked change")
            self.assertEqual(self.version(), version)
            self.assertEqual(reads, first)
            self.legacy.write_bytes(b"legacy-two")
            self.assertNotEqual(self.version(), version)
            self.assertEqual(reads[len(first):], [self.legacy])

    def test_template_reference_add_remove_and_missing_file_appearance(self):
        version = self.version()
        self.template.write_text(self.template.read_text() + "<link href=\"{{ url_for('static', filename='css/theme.css') }}\">", encoding="utf-8")
        missing = self.version()
        self.assertNotEqual(missing, version)
        linked = self.static / "css/theme.css"
        linked.parent.mkdir()
        linked.write_bytes(b"theme")
        present = self.version()
        self.assertNotEqual(present, missing)
        linked.unlink()
        self.assertEqual(self.version(), missing)
        self.template.write_text("<main>no linked assets</main>", encoding="utf-8")
        self.assertNotEqual(self.version(), present)

    def test_chunk_add_remove_and_ignored_source_maps(self):
        version = self.version()
        source_map = self.bundle / "accounts.js.map"
        source_map.write_bytes(b"map")
        self.assertEqual(self.version(), version)
        chunk = self.bundle / "new-hash.js"
        chunk.write_bytes(b"new shared chunk")
        self.assertNotEqual(self.version(), version)
        chunk.unlink()
        self.assertEqual(self.version(), version)

    def test_absolute_template_folder_and_empty_development_tree(self):
        absolute = SimpleNamespace(root_path="ignored", static_folder=str(self.static), template_folder=str(self.template.parent))
        self.assertEqual(page_asset_version(absolute), self.version())
        empty = SimpleNamespace(root_path=str(self.root / "empty"), static_folder=str(self.root / "empty/static"), template_folder="templates")
        self.assertEqual(page_asset_version(empty), "development")


if __name__ == "__main__":
    unittest.main()
