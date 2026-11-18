from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[2]


def run_contract(name):
    result = subprocess.run(
        ["node", "tests/email/vue_migration_contracts.cjs", name],
        cwd=ROOT, capture_output=True, text=True, check=False, timeout=20,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_replaced_email_status_is_labeled_and_not_restorable_in_ui():
    run_contract("retired_status")


def test_local_inventory_stays_visible_when_registration_source_is_disabled():
    run_contract("overview_visibility")
