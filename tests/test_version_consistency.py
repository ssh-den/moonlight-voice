import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_ROOT = ROOT / "moonlight-voice"
ROOT_CHANGELOG_PATH = ROOT / "CHANGELOG.md"
ADDON_CHANGELOG_PATH = ADDON_ROOT / "CHANGELOG.md"
CONFIG_YAML_PATH = ADDON_ROOT / "config.yaml"

if str(ADDON_ROOT) not in sys.path:
    sys.path.insert(0, str(ADDON_ROOT))

from moonlight_voice.config import SERVICE_VERSION


def _read_addon_version() -> str:
    for line in CONFIG_YAML_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("version:"):
            return stripped.split(":", 1)[1].strip()
    raise AssertionError("version not found in config.yaml")


class VersionConsistencyTest(unittest.TestCase):
    def test_addon_and_service_versions_match(self) -> None:
        addon_version = _read_addon_version()

        self.assertEqual(addon_version, SERVICE_VERSION)

    def test_github_and_addon_changelogs_are_identical(self) -> None:
        self.assertEqual(
            ROOT_CHANGELOG_PATH.read_text(encoding="utf-8"),
            ADDON_CHANGELOG_PATH.read_text(encoding="utf-8"),
        )

    def test_addon_manifest_enables_ingress_on_service_port(self) -> None:
        manifest = CONFIG_YAML_PATH.read_text(encoding="utf-8")
        self.assertIn("ingress: true", manifest)
        self.assertIn("ingress_port: 8031", manifest)


if __name__ == "__main__":
    unittest.main()
