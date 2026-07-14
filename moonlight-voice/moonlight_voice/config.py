import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_OPTIONS_PATH = Path("/data/options.json")
DEFAULT_AUDIO_DIR = Path("/data/moonlight-voice")
DEFAULT_WEBUI_SETTINGS_PATH = DEFAULT_AUDIO_DIR / "settings.json"
SERVICE_VERSION = "1.4.0"
DEFAULT_MAX_UPLOAD_SIZE_MB = 20
TTS_MODES = {"openai_compatible", "home_assistant"}
WEBUI_SETTINGS_FIELDS = {"tts_mode", "output_format"}
LOGGER = logging.getLogger("moonlight_voice.config")


@dataclass
class ServiceConfig:
    host: str = "0.0.0.0"
    port: int = 8031
    tts_mode: str = "openai_compatible"
    output_format: str = "mp3"
    output_file: str = str(DEFAULT_AUDIO_DIR / "default.mp3")
    log_level: str = "info"
    cache_headers: bool = False
    max_upload_size_mb: int = DEFAULT_MAX_UPLOAD_SIZE_MB
    version: str = SERVICE_VERSION
    notes: list[str] = field(default_factory=list, repr=False, compare=False)
    webui_settings_path: Path = field(
        default=DEFAULT_WEBUI_SETTINGS_PATH, repr=False, compare=False
    )

    @classmethod
    def load(
        cls,
        options_path: Path = DEFAULT_OPTIONS_PATH,
        webui_settings_path: Path = DEFAULT_WEBUI_SETTINGS_PATH,
    ) -> "ServiceConfig":
        """
        Load configuration from the Home Assistant options file if present.
        Falls back to sensible defaults so the service can run outside of Supervisor.
        """
        config = cls(webui_settings_path=Path(webui_settings_path))
        if options_path.exists():
            try:
                with options_path.open("r", encoding="utf-8") as f:
                    data = json.load(f) or {}
                config.tts_mode = str(data.get("tts_mode", config.tts_mode)).lower()
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
        config._load_webui_settings()
        return config

    def _load_webui_settings(self) -> None:
        if not self.webui_settings_path.exists():
            return
        try:
            with self.webui_settings_path.open("r", encoding="utf-8") as file:
                settings = json.load(file)
            self._apply_webui_settings(settings)
            self.notes.append(f"Loaded WebUI settings from {self.webui_settings_path}")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            self.notes.append(
                f"Failed to parse WebUI settings from {self.webui_settings_path}: {exc!r}."
            )
            LOGGER.warning(
                "Failed to parse WebUI settings from %s: %s", self.webui_settings_path, exc
            )

    def _apply_webui_settings(self, settings: object) -> None:
        if not isinstance(settings, dict):
            raise ValueError("settings must be an object")
        unknown = set(settings) - WEBUI_SETTINGS_FIELDS
        if unknown:
            raise ValueError(f"unsupported settings: {', '.join(sorted(unknown))}")
        tts_mode = settings.get("tts_mode", self.tts_mode)
        output_format = settings.get("output_format", self.output_format)
        if not isinstance(tts_mode, str) or tts_mode.lower() not in TTS_MODES:
            raise ValueError("tts_mode must be openai_compatible or home_assistant")
        if not isinstance(output_format, str) or output_format.lower() not in {"mp3", "wav"}:
            raise ValueError("output_format must be mp3 or wav")
        self.tts_mode = tts_mode.lower()
        self.output_format = output_format.lower()

    def update_webui_settings(self, settings: object) -> None:
        previous_tts_mode = self.tts_mode
        previous_output_format = self.output_format
        self._apply_webui_settings(settings)
        try:
            self.webui_settings_path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = self.webui_settings_path.with_name(
                f".{self.webui_settings_path.name}.tmp"
            )
            temporary_path.write_text(
                json.dumps(
                    {
                        "tts_mode": self.tts_mode,
                        "output_format": self.output_format,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.webui_settings_path)
        except OSError:
            self.tts_mode = previous_tts_mode
            self.output_format = previous_output_format
            raise

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
        if self.tts_mode not in TTS_MODES:
            self.tts_mode = "openai_compatible"
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
