import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "moonlight-voice"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from moonlight_voice.supervisor import publish_discovery


class SupervisorDiscoveryTest(unittest.TestCase):
    @patch.dict("os.environ", {"SUPERVISOR_TOKEN": "token"})
    @patch("moonlight_voice.supervisor._request_json")
    def test_publishes_configured_port_and_records_discovery_id(self, request_json) -> None:
        request_json.side_effect = [
            {"ip_address": "172.30.33.7"},
            {"uuid": "discovery-id"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "discovery.json"

            endpoint = publish_discovery(9123, state_path)

            self.assertEqual(endpoint, "http://172.30.33.7:9123")
            discovery_call = request_json.call_args_list[1]
            self.assertEqual(discovery_call.args, ("token", "/discovery"))
            self.assertEqual(
                discovery_call.kwargs,
                {
                    "method": "POST",
                    "payload": {
                        "service": "moonlight_voice",
                        "config": {"host": "172.30.33.7", "port": 9123},
                    },
                },
            )
            self.assertEqual(
                json.loads(state_path.read_text(encoding="utf-8")), {"uuid": "discovery-id"}
            )

    @patch.dict("os.environ", {}, clear=True)
    def test_skips_discovery_without_supervisor_token(self) -> None:
        self.assertIsNone(publish_discovery(8031))
