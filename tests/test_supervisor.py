import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

ROOT = Path(__file__).resolve().parents[1] / "moonlight-voice"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from moonlight_voice.supervisor import (
    _request_json,
    publish_discovery,
    publish_discovery_with_retry,
)


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

    @patch.dict("os.environ", {"SUPERVISOR_TOKEN": "token"})
    @patch("moonlight_voice.supervisor._request_json")
    def test_replaces_previous_discovery_before_publishing(self, request_json) -> None:
        request_json.side_effect = [
            {"ip_address": "172.30.33.8"},
            {},
            {"uuid": "new-discovery-id"},
        ]
        with tempfile.TemporaryDirectory() as tmpdir:
            state_path = Path(tmpdir) / "discovery.json"
            state_path.write_text(json.dumps({"uuid": "old-discovery-id"}), encoding="utf-8")

            endpoint = publish_discovery(8031, state_path)

            self.assertEqual(endpoint, "http://172.30.33.8:8031")
            self.assertEqual(
                request_json.call_args_list[1].args,
                ("token", "/discovery/old-discovery-id"),
            )
            self.assertEqual(request_json.call_args_list[1].kwargs, {"method": "DELETE"})
            self.assertEqual(request_json.call_args_list[2].args, ("token", "/discovery"))
            self.assertEqual(
                json.loads(state_path.read_text(encoding="utf-8")),
                {"uuid": "new-discovery-id"},
            )

    @patch("moonlight_voice.supervisor.urlopen")
    def test_accepts_supervisor_success_response_with_null_data(self, urlopen) -> None:
        response = MagicMock()
        response.read.return_value = b'{"result":"ok","data":null}'
        urlopen.return_value.__enter__.return_value = response

        self.assertEqual(_request_json("token", "/discovery/id", method="DELETE"), {})

    @patch.dict("os.environ", {}, clear=True)
    def test_skips_discovery_without_supervisor_token(self) -> None:
        self.assertIsNone(publish_discovery(8031))

    @patch("moonlight_voice.supervisor.publish_discovery")
    def test_retries_discovery_until_supervisor_accepts_it(self, publish) -> None:
        publish.side_effect = [None, None, "http://172.30.33.9:8031"]
        sleep = MagicMock()

        endpoint = publish_discovery_with_retry(
            8031,
            retry_delays=(1.0, 2.0, 5.0),
            sleep=sleep,
        )

        self.assertEqual(endpoint, "http://172.30.33.9:8031")
        self.assertEqual(publish.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(1.0), call(2.0)])
