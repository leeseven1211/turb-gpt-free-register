"""验证功能地图没有引用已经移除的入口、配置或测试。"""

import json
from pathlib import Path

from config.schema import CONFIG_SCHEMA


ROOT = Path(__file__).resolve().parents[2]
MAP_PATH = ROOT / "docs/architecture/functional-map.json"


def test_functional_map_has_unique_flows_and_existing_references():
    data = json.loads(MAP_PATH.read_text(encoding="utf-8"))
    flows = data["flows"]
    ids = [flow["id"] for flow in flows]
    assert data["version"] == 1
    assert len(ids) == len(set(ids))
    assert {"registration", "registration_resume", "live_check", "at_refresh", "codex_token_refresh"}.issubset(ids)

    known_config = {field.key for field in CONFIG_SCHEMA.fields}
    for flow in flows:
        assert flow["entrypoints"]
        assert flow["tests"]
        for category in ("entrypoints", "shared_components", "acceptance", "tests"):
            for relative_path in flow[category]:
                assert (ROOT / relative_path).is_file(), f"地图引用不存在的路径: {relative_path}"
        for key in flow["config_keys"]:
            assert key in known_config, f"地图引用不存在的配置键: {key}"


def test_functional_map_markdown_links_machine_readable_data_and_verification_rules():
    markdown = (ROOT / "docs/architecture/functional-map.md").read_text(encoding="utf-8")
    assert "functional-map.json" in markdown
    assert "test_functional_map.py" in markdown
    assert "指定路径的 `all` 不等于项目全量" in markdown
