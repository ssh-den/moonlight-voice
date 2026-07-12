import unittest
from pathlib import Path

DOCKERFILE_PATH = Path(__file__).resolve().parents[1] / "moonlight-voice" / "Dockerfile"
CONFIG_PATH = Path(__file__).resolve().parents[1] / "moonlight-voice" / "config.yaml"
DOCKERIGNORE_PATH = Path(__file__).resolve().parents[1] / "moonlight-voice" / ".dockerignore"


class DockerfileTest(unittest.TestCase):
    def test_base_image_uses_supervisor_build_architecture(self) -> None:
        dockerfile = DOCKERFILE_PATH.read_text(encoding="utf-8")
        self.assertIn("ARG BUILD_ARCH", dockerfile)
        self.assertNotIn("ARG BUILD_ARCH=amd64", dockerfile)
        self.assertIn("FROM ghcr.io/home-assistant/${BUILD_ARCH}-base:latest", dockerfile)
        self.assertNotIn("amd64-base:latest", dockerfile)
        self.assertIn("WORKDIR /opt/moonlight-voice", dockerfile)
        self.assertIn("COPY moonlight_voice /opt/moonlight-voice/moonlight_voice", dockerfile)

    def test_advertised_architectures_are_explicit_and_use_the_build_arch_argument(
        self,
    ) -> None:
        manifest = CONFIG_PATH.read_text(encoding="utf-8")
        self.assertIn("  - amd64", manifest)
        self.assertIn("  - armv7", manifest)
        self.assertIn("  - aarch64", manifest)
        self.assertIn(
            "FROM ghcr.io/home-assistant/${BUILD_ARCH}-base:latest",
            DOCKERFILE_PATH.read_text(encoding="utf-8"),
        )

    def test_docker_context_excludes_development_cache_files(self) -> None:
        dockerignore = DOCKERIGNORE_PATH.read_text(encoding="utf-8")
        for ignored_path in (
            "__pycache__/",
            "*.py[cod]",
            "tests/",
            ".DS_Store",
            ".env",
            ".venv/",
            "node_modules/",
            "*.log",
            "*.mp3",
            "*.wav",
        ):
            self.assertIn(ignored_path, dockerignore)


if __name__ == "__main__":
    unittest.main()
