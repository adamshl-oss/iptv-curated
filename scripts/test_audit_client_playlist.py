import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from audit_client_playlist import infrastructure_circuit


class InfrastructureCircuitTests(unittest.TestCase):
    def row(self, channel, successes, host="relay.example"):
        return {
            "tvg_id": channel,
            "url": f"https://{host}/{channel}.m3u8",
            "successes": successes,
            "audit_error": False,
        }

    def test_opens_on_correlated_majority_startup_failure(self):
        rows = [self.row(str(index), 0 if index < 3 else 3) for index in range(5)]
        self.assertTrue(infrastructure_circuit(rows)["open"])

    def test_stays_closed_for_one_dead_channel(self):
        rows = [self.row(str(index), 0 if index == 0 else 3) for index in range(5)]
        self.assertFalse(infrastructure_circuit(rows)["open"])

    def test_different_hosts_are_independent(self):
        rows = [self.row(str(index), 0, f"host-{index}.example") for index in range(5)]
        self.assertFalse(infrastructure_circuit(rows)["open"])


if __name__ == "__main__":
    unittest.main()
