import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_OPTIONS_PATH = Path("/data/options.json")
DEFAULT_AUDIO_DIR = Path("/data/moonlight-voice")
SERVICE_VERSION = "1.0.0"
DEFAULT_MAX_UPLOAD_SIZE_MB = 20
LOGGER = logging.getLogger("moonlight_voice.config")


@dataclass
class ServiceConfig:
    host: str = "0.0.0.0"
    port: int = 8031
    output_format: str = "mp3"
    output_file: str = str(DEFAULT_AUDIO_DIR / "default.mp3")
    log_level: str = "info"
    cache_headers: bool = False
    max_upload_size_mb: int = DEFAULT_MAX_UPLOAD_SIZE_MB
    version: str = SERVICE_VERSION
    notes: list[str] = field(default_factory=list, repr=False, compare=False)

    @classmethod
    def load(cls, options_path: Path = DEFAULT_OPTIONS_PATH) -> "ServiceConfig":
        """
        Load configuration from the Home Assistant options file if present.
        Falls back to sensible defaults so the service can run outside of Supervisor.
        """
        config = cls()
        if options_path.exists():
            try:
                with options_path.open("r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                config.output_format = str(data.get("output_format", config.output_format)).lower()
                config.output_file = str(data.get("output_file", config.output_file))
                config.log_level = str(data.get("log_level", config.log_level)).lower()
                config.cache_headers = bool(data.get("cache_headers", config.cache_headers))
                config.max_upload_size_mb = int(
                    data.get("max_upload_size_mb", config.max_upload_size_mb)
                )
                if "port" in data:
                    config.port = int(data["port"])
                config.notes.append(f"Loaded configuration from {options_path}")
            except Exception as exc:
                config.notes.append(f"Failed to parse {options_path}: {exc!r}. Using defaults.")
                LOGGER.warning("Failed to parse %s: %s", options_path, exc)
        else:
            config.notes.append(f"No options file found at {options_path}; using defaults.")
        return config

    def resolved_audio_path(self) -> Path:
        """
        Resolve the audio file path, allowing both absolute and relative inputs.
        Relative paths are resolved against DEFAULT_AUDIO_DIR.
        """
        candidate = Path(self.output_file)
        if not candidate.is_absolute():
            candidate = DEFAULT_AUDIO_DIR / candidate
        return candidate

    def normalize(self) -> None:
        """
        Ensure configuration values are valid.
        """
        if self.output_format not in {"mp3", "wav"}:
            self.output_format = "mp3"
        if self.log_level not in {"debug", "info", "warn", "warning", "error"}:
            self.log_level = "info"
        if self.log_level == "warning":
            self.log_level = "warn"
        self.max_upload_size_mb = min(max(int(self.max_upload_size_mb), 1), 1024)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


def setup_logging(level: str) -> None:
    """
    Configure application logging for stdout visibility.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
