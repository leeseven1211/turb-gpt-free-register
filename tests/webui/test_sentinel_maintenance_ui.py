"""Sentinel controls exercise the real Vue page and visibility lifecycle."""

from pathlib import Path
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]


class SentinelMaintenanceUiTests(unittest.TestCase):
    def run_contract(self, name):
        completed = subprocess.run(
            ["node", "tests/config/vue_migration_contracts.cjs", name],
            cwd=ROOT, capture_output=True, text=True, check=False, timeout=15,
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_card_lives_in_general_configuration_and_initial_load_never_checks(self):
        self.run_contract("sentinel_initial")

    def test_explicit_check_is_single_flight_and_updates_only_the_card(self):
        self.run_contract("sentinel_single_flight")

    def test_navigation_cancels_polling_and_stale_get_does_not_restart_it(self):
        self.run_contract("sentinel_navigation")

    def test_failure_retains_candidate_and_retries_without_showing_debug_details(self):
        self.run_contract("sentinel_failure")

    def test_status_read_failure_has_a_get_retry_and_escapes_versions(self):
        self.run_contract("sentinel_read_retry")

    def test_corrupt_status_retains_last_candidate_and_offers_a_new_check(self):
        self.run_contract("sentinel_corrupt")

    def test_hidden_document_pauses_polling_and_resumes_with_only_a_status_read(self):
        self.run_contract("sentinel_document")


if __name__ == "__main__":
    unittest.main()
