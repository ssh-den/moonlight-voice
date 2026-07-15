import json
import logging
import subprocess
import tempfile
import time
from dataclasses import asdict, dataclass
from hashlib import sha256
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from typing import Dict, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from .config import DEFAULT_AUDIO_DIR, SERVICE_VERSION, ServiceConfig
from .responses import ResponseLibrary
from .supervisor import publish_discovery_with_retry
from .web import get_static_dir, load_index_html, load_static_asset

LOGGER = logging.getLogger("moonlight_voice.server")
SENSITIVE_DEBUG_FIELDS = {"authorization", "cookie", "key", "password", "secret", "token"}
DEBUG_BODY_LIMIT = 4_096
INGRESS_PORT = 8031


def _redact_debug_value(value):
    if isinstance(value, dict):
        return {
            key: (
                "<redacted>"
                if any(field in key.lower() for field in SENSITIVE_DEBUG_FIELDS)
                else _redact_debug_value(item)
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_debug_value(item) for item in value]
    return value


def _format_debug_body(body: bytes, content_type: Optional[str]) -> str:
    """Format a request body for debug logs without exposing binary uploads."""
    if not body:
        return "<empty>"
    if content_type and "json" not in content_type.lower() and not content_type.startswith("text/"):
        return f"<{len(body)} bytes of binary data>"
    try:
        payload = json.loads(body.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        try:
            payload = body.decode("utf-8")
        except UnicodeDecodeError:
            return f"<{len(body)} bytes of binary data>"
    rendered = json.dumps(_redact_debug_value(payload), ensure_ascii=False, default=str)
    if len(rendered) > DEBUG_BODY_LIMIT:
        return f"{rendered[:DEBUG_BODY_LIMIT]}... <truncated>"
    return rendered


def _describe_tts_payload(parsed, body: bytes) -> str:
    query = parse_qs(parsed.query or "")
    if "text" in query:
        return "query:text"
    if not body:
        return "empty"
    try:
        payload = json.loads(body.decode("utf-8"))
    except UnicodeDecodeError, json.JSONDecodeError:
        return "non-json"
    if isinstance(payload, dict):
        if "message" in payload:
            return "home_assistant:message"
        if "input" in payload:
            return "openai_compatible:input"
        if "text" in payload:
            return "openai_compatible:text"
        return "json:object"
    if isinstance(payload, list):
        return "json:array"
    return f"json:{type(payload).__name__}"


@dataclass
class UploadResult:
    saved_path: Path
    saved_format: str
    normalized_filename: str
    renamed: bool
    converted: bool
    converted_format: Optional[str] = None
    converted_path: Optional[Path] = None
    conversion_error: Optional[str] = None


def _transcode_audio(
    data: bytes, source_format: str, target_format: str
) -> Tuple[Optional[bytes], Optional[str]]:
    if source_format == target_format:
        return data, None

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / f"input.{source_format}"
            dest = Path(tmpdir) / f"output.{target_format}"
            src.write_bytes(data)

            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(src),
                str(dest),
            ]
            result = subprocess.run(cmd, check=False, capture_output=True)
            if result.returncode != 0:
                stderr = (result.stderr or b"").decode("utf-8", errors="ignore").strip()
                message = f"ffmpeg exited with {result.returncode}: {stderr or 'unknown error'}"
                LOGGER.warning(
                    "Failed to convert %s to %s: %s",
                    source_format,
                    target_format,
                    message,
                )
                return None, message

            if not dest.exists():
                message = (
                    f"Conversion {source_format} -> {target_format} completed without output file"
                )
                LOGGER.warning(message)
                return None, message

            return dest.read_bytes(), None
    except FileNotFoundError:
        message = f"ffmpeg not available; unable to convert {source_format} to {target_format}"
        LOGGER.warning(message)
        return None, message
    except Exception:  # pragma: no cover - logged for visibility
        LOGGER.exception("Unexpected error converting %s to %s", source_format, target_format)
        return None, "Unexpected error during conversion"


def _detect_format(filename: Optional[str], content_type: Optional[str]) -> Optional[str]:
    if filename:
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext in {"mp3", "wav"}:
            return ext
    if content_type:
        content_type = content_type.lower()
        if "mpeg" in content_type or "mp3" in content_type:
            return "mp3"
        if "wav" in content_type or "wave" in content_type:
            return "wav"
    return None


def _validate_audio_content(data: bytes, audio_format: str) -> None:
    """Reject clearly invalid audio before it can replace an active clip."""
    if audio_format == "wav" and data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return
    if audio_format == "mp3" and (
        data.startswith(b"ID3") or (len(data) >= 2 and data[0] == 0xFF and data[1] & 0xE0 == 0xE0)
    ):
        return
    raise RuntimeError(f"Uploaded data is not recognizable {audio_format.upper()} audio")


class MoonlightVoiceRequestHandler(BaseHTTPRequestHandler):
    server_version = f"MoonlightVoice/{SERVICE_VERSION}"
    server: "MoonlightVoiceServer"

    def log_message(self, format: str, *args) -> None:  # pylint: disable=redefined-builtin
        LOGGER.info("%s - %s", self.address_string(), format % args)

    def _json_response(self, payload: Dict, status: int = 200) -> None:
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self._add_cache_headers()
        self.end_headers()
        self.wfile.write(data)

    def _send_audio(self, body: bytes, content_type: str) -> None:
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._add_cache_headers()
        self.end_headers()
        self.wfile.write(body)

    def _add_cache_headers(self) -> None:
        if self.server.config.cache_headers:
            self.send_header("Cache-Control", "public, max-age=86400")
        else:
            self.send_header("Cache-Control", "no-store")

    def _debug_request(self, parsed) -> None:
        if not LOGGER.isEnabledFor(logging.DEBUG):
            return
        headers = _redact_debug_value(dict(self.headers.items()))
        query = _redact_debug_value(parse_qs(parsed.query or "", keep_blank_values=True))
        LOGGER.debug(
            "Incoming HTTP request from %s | method=%s | path=%s | query=%s | "
            "tts_mode=%s | headers=%s",
            self.client_address[0],
            self.command,
            parsed.path,
            query,
            self.server.config.tts_mode,
            headers,
        )

    def _debug_request_body(self, body: bytes) -> None:
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug(
                "Incoming HTTP request body | method=%s | path=%s | content_type=%s | payload=%s",
                self.command,
                urlparse(self.path).path,
                self.headers.get("Content-Type"),
                _format_debug_body(body, self.headers.get("Content-Type")),
            )

    def _debug_tts_request(self, parsed, body: bytes) -> None:
        if LOGGER.isEnabledFor(logging.DEBUG):
            LOGGER.debug(
                "Incoming TTS request format=%s | configured_tts_mode=%s",
                _describe_tts_payload(parsed, body),
                self.server.config.tts_mode,
            )

    def _read_request_body(self, *, required: bool = False) -> Optional[bytes]:
        header = self.headers.get("Content-Length")
        if header is None:
            if required:
                self._json_response(
                    {"error": "Content-Length header is required"},
                    status=HTTPStatus.LENGTH_REQUIRED,
                )
                return None
            return b""
        try:
            content_length = int(header)
        except ValueError:
            self._json_response({"error": "invalid Content-Length"}, status=HTTPStatus.BAD_REQUEST)
            return None
        if content_length < 0:
            self._json_response({"error": "invalid Content-Length"}, status=HTTPStatus.BAD_REQUEST)
            return None
        if content_length > self.server.config.max_upload_bytes:
            self._json_response(
                {
                    "error": (
                        f"request body exceeds {self.server.config.max_upload_size_mb} MiB limit"
                    )
                },
                status=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            )
            return None
        if required and content_length == 0:
            self._json_response({"error": "audio body required"}, status=HTTPStatus.BAD_REQUEST)
            return None
        body = self.rfile.read(content_length)
        self._debug_request_body(body)
        return body

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        self._debug_request(parsed)
        if parsed.path == "/":
            self._serve_root()
        elif parsed.path.startswith("/static/"):
            self._serve_static(parsed.path[len("/static/") :])
        elif parsed.path == "/health":
            self._json_response(
                {
                    "status": "ok",
                    "uptime_seconds": self.server.uptime_seconds(),
                    "started_at": self.server.started_at,
                }
            )
        elif parsed.path == "/version":
            self._json_response({"version": self.server.config.version})
        elif parsed.path == "/config":
            self._json_response(self.server.describe_config())
        elif parsed.path == "/audio":
            if parse_qs(parsed.query or "").get("stream"):
                self._serve_default_audio(parsed)
            else:
                self._json_response(self.server.describe_audio())
        elif parsed.path == "/audio/file":
            self._serve_default_audio(parsed)
        elif parsed.path == "/responses":
            self._handle_responses_list(parsed)
        elif parsed.path == "/responses/file":
            self._serve_response_audio(parsed)
        elif parsed.path == "/tts":
            self._debug_tts_request(parsed, b"")
            self._handle_tts(parsed, b"")
        else:
            self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        self._debug_request(parsed)
        if parsed.path == "/tts":
            body = self._read_request_body()
            if body is None:
                return
            self._debug_tts_request(parsed, body)
            self._handle_tts(parsed, body)
        elif parsed.path == "/audio":
            self._handle_audio_upload(parsed)
        elif parsed.path == "/responses":
            self._handle_response_upload(parsed)
        else:
            self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_DELETE(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        self._debug_request(parsed)
        if parsed.path == "/audio":
            self._handle_audio_delete(parsed)
        elif parsed.path == "/responses":
            self._handle_response_delete(parsed)
        elif parsed.path == "/storage":
            self._handle_storage_delete()
        else:
            self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_PATCH(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        self._debug_request(parsed)
        if parsed.path == "/responses":
            body = self._read_request_body()
            if body is None:
                return
            self._handle_response_update(body)
        elif parsed.path == "/config":
            body = self._read_request_body(required=True)
            if body is None:
                return
            self._handle_config_update(body)
        else:
            self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    # --- Internal helpers -------------------------------------------------
    def _serve_root(self) -> None:
        try:
            body, content_type = load_index_html(self.server.static_dir)
        except FileNotFoundError:
            LOGGER.error("index.html missing in static directory: %s", self.server.static_dir)
            self._json_response(
                {"error": "UI unavailable"}, status=HTTPStatus.INTERNAL_SERVER_ERROR
            )
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._add_cache_headers()
        self.end_headers()
        self.wfile.write(body)

    def _serve_static(self, relative_path: str) -> None:
        try:
            body, content_type = load_static_asset(relative_path, self.server.static_dir)
        except FileNotFoundError, ValueError:
            self._json_response({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)
            return
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self._add_cache_headers()
        self.end_headers()
        self.wfile.write(body)

    def _extract_tts_text(self, parsed, body: bytes) -> str:
        query = parse_qs(parsed.query or "")
        if "text" in query:
            return str((query.get("text") or [""])[0])
        if not body:
            return ""
        try:
            payload = json.loads(body.decode("utf-8"))
            if isinstance(payload, dict):
                # The native Home Assistant integration sends `message`; the
                # OpenAI-compatible shim uses `input` or `text`.  Supporting
                # both makes switching modes non-destructive for existing clients.
                if "message" in payload:
                    return str(payload.get("message") or "")
                if "text" in payload:
                    return str(payload.get("text") or "")
                if "input" in payload:
                    candidate = payload["input"]
                    if isinstance(candidate, list):
                        return " ".join(
                            str(item.get("text") if isinstance(item, dict) else item)
                            for item in candidate
                        )
                    return str(candidate)
            elif isinstance(payload, list):
                return " ".join(str(item) for item in payload)
        except Exception:
            return ""
        return ""

    def _handle_tts(self, parsed, body: bytes) -> None:
        query = parse_qs(parsed.query or "")
        format_values = query.get("format") or query.get("output")
        requested_format = format_values[0] if format_values else None
        requested_format = requested_format.lower() if requested_format else None
        selected_format = requested_format or self.server.config.output_format
        if selected_format not in {"mp3", "wav"}:
            selected_format = self.server.config.output_format

        text = self._extract_tts_text(parsed, body)
        if body:
            try:
                payload = json.loads(body.decode("utf-8"))
                if isinstance(payload, dict):
                    selected_format = str(payload.get("format", selected_format))
                if selected_format not in {"mp3", "wav"}:
                    selected_format = self.server.config.output_format
            except Exception:
                pass

        response_entry = self.server.response_library.find_match(text)
        audio_bytes = None
        content_type = None
        response_source = "default"
        served_format = selected_format
        if response_entry:
            audio_bytes, response_format = self.server.response_library.audio_for_preferred_format(
                response_entry.code, selected_format
            )
            if audio_bytes is not None and response_format is not None:
                served_format = response_format
                content_type = "audio/mpeg" if served_format == "mp3" else "audio/wav"
                response_source = response_entry.code

        if audio_bytes is None or content_type is None:
            audio_bytes, content_type = self.server.get_audio(selected_format)

        if audio_bytes is None or content_type is None:
            self._json_response(
                {"error": f"Static audio file for format '{selected_format}' is missing"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return

        truncated = (text or "").strip()
        if len(truncated) > 120:
            truncated = truncated[:117] + "..."
        LOGGER.info(
            'TTS request from %s | mode=%s | format=%s | text="%s" | served=%s',
            self.client_address[0],
            self.server.config.tts_mode,
            served_format,
            truncated,
            response_source,
        )
        self._send_audio(audio_bytes, content_type)

    def _handle_audio_upload(self, parsed) -> None:
        query = parse_qs(parsed.query or "")
        filename = (query.get("filename") or [None])[0]
        fmt = (query.get("format") or [None])[0]
        fmt = fmt.lower() if fmt else None
        body = self._read_request_body(required=True)
        if body is None:
            return
        try:
            detected = _detect_format(filename, self.headers.get("Content-Type"))
            selected_format = fmt or detected or ""
            result = self.server.set_audio(
                selected_format, body, filename, self.headers.get("Content-Type")
            )
        except ValueError:
            self._json_response({"error": "invalid filename"}, status=HTTPStatus.BAD_REQUEST)
            return
        except RuntimeError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return

        response = {
            "status": "ok",
            "format": result.saved_format,
            "path": str(result.saved_path),
            "filename": result.normalized_filename,
            "renamed": result.renamed,
            "converted": result.converted,
        }
        if result.converted_format:
            response["converted_format"] = result.converted_format
        if result.converted_path:
            response["converted_path"] = str(result.converted_path)
        if result.conversion_error:
            response["conversion_error"] = result.conversion_error

        LOGGER.info(
            "Uploaded audio for %s saved to %s%s",
            result.saved_format,
            result.saved_path,
            (
                f"; auto-converted to {result.converted_format} at {result.converted_path}"
                if result.converted
                else ""
            ),
        )
        if result.renamed:
            LOGGER.info("Filename normalized to %s", result.normalized_filename)
        if result.conversion_error:
            LOGGER.warning(
                "Auto-convert %s -> %s failed: %s",
                result.saved_format,
                result.converted_format or "unknown",
                result.conversion_error,
            )
        self._json_response(response)

    def _handle_audio_delete(self, _parsed) -> None:
        removed = self.server.delete_audio()
        LOGGER.info("Deleted default audio: %s", removed)
        self._json_response({"status": "ok", "deleted": removed})

    def _handle_storage_delete(self) -> None:
        result = self.server.clear_storage()
        LOGGER.info("Cleared all stored audio: %s", result)
        self._json_response({"status": "ok", **result})

    def _handle_responses_list(self, parsed) -> None:
        query = parse_qs(parsed.query or "")
        search = (query.get("search") or [""])[0]
        try:
            page = int((query.get("page") or ["1"])[0])
        except ValueError:
            page = 1
        try:
            page_size = int((query.get("page_size") or ["10"])[0])
        except ValueError:
            page_size = 10
        sort_by = (query.get("sort_by") or ["code"])[0]
        sort_dir = (query.get("sort_dir") or ["asc"])[0]
        data = self.server.response_library.list(
            search,
            page,
            min(max(page_size, 1), 100),
            sort_by=sort_by,
            sort_dir=sort_dir,
        )
        data["defaults"] = {
            "preferred_format": self.server.config.output_format,
            "default_files": self.server.active_files,
        }
        self._json_response(data)

    def _handle_response_upload(self, parsed) -> None:
        query = parse_qs(parsed.query or "")
        code = (query.get("code") or [None])[0]
        filename = (query.get("filename") or [None])[0]
        if not code:
            self._json_response({"error": "code is required"}, status=HTTPStatus.BAD_REQUEST)
            return
        body = self._read_request_body(required=True)
        if body is None:
            return
        try:
            result = self.server.response_library.store_audio(
                code, body, filename, self.headers.get("Content-Type")
            )
        except (ValueError, RuntimeError) as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            return
        except Exception:
            LOGGER.exception("Unexpected error saving response audio")
            self._json_response(
                {"error": "failed to save response"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )
            return
        self._json_response({"status": "ok", **result})

    def _handle_response_update(self, body: bytes) -> None:
        try:
            payload = json.loads(body.decode("utf-8"))
        except Exception:
            self._json_response({"error": "invalid json"}, status=HTTPStatus.BAD_REQUEST)
            return
        code = payload.get("code")
        new_code = payload.get("new_code")
        if not code or not new_code:
            self._json_response(
                {"error": "code and new_code are required"},
                status=HTTPStatus.BAD_REQUEST,
            )
            return
        try:
            updated = self.server.response_library.rename(code, new_code)
            self._json_response({"status": "ok", "response": updated})
        except ValueError as exc:
            self._json_response({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
        except KeyError:
            self._json_response({"error": "response not found"}, status=HTTPStatus.NOT_FOUND)
        except Exception:
            LOGGER.exception("Unexpected error renaming response")
            self._json_response(
                {"error": "failed to update response"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _handle_config_update(self, body: bytes) -> None:
        try:
            settings = json.loads(body.decode("utf-8"))
            self._json_response(self.server.update_webui_settings(settings))
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            self._json_response(
                {"error": str(exc) or "invalid json"}, status=HTTPStatus.BAD_REQUEST
            )
        except OSError:
            LOGGER.exception("Failed to save WebUI settings")
            self._json_response(
                {"error": "failed to save settings"},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _handle_response_delete(self, parsed) -> None:
        query = parse_qs(parsed.query or "")
        codes = [code for code in query.get("code", []) if code]
        fmt = (query.get("format") or [None])[0]
        if (query.get("all") or [""])[0].lower() == "true":
            result = self.server.response_library.clear()
            self._json_response({**result, "status": "ok"})
            return
        if not codes:
            self._json_response({"error": "code is required"}, status=HTTPStatus.BAD_REQUEST)
            return
        if len(codes) > 1:
            if fmt:
                self._json_response(
                    {"error": "format is only supported for a single code"},
                    status=HTTPStatus.BAD_REQUEST,
                )
                return
            result = self.server.response_library.delete_many(codes)
            self._json_response({**result, "status": "ok"})
            return
        result = self.server.response_library.delete(codes[0], fmt)
        self._json_response({**result, "status": "ok"})

    def _serve_response_audio(self, parsed) -> None:
        query = parse_qs(parsed.query or "")
        code = (query.get("code") or [None])[0]
        fmt = (query.get("format") or [None])[0]
        if not code:
            self._json_response({"error": "code is required"}, status=HTTPStatus.BAD_REQUEST)
            return
        fmt = (fmt or self.server.config.output_format).lower()
        if fmt not in {"mp3", "wav"}:
            fmt = self.server.config.output_format
        data = self.server.response_library.audio_for(code, fmt)
        if data is None:
            self._json_response({"error": "audio not found"}, status=HTTPStatus.NOT_FOUND)
            return
        content_type = "audio/mpeg" if fmt == "mp3" else "audio/wav"
        self._send_audio(data, content_type)

    def _serve_default_audio(self, parsed) -> None:
        query = parse_qs(parsed.query or "")
        fmt = (query.get("format") or [None])[0]
        fmt = (fmt or self.server.config.output_format).lower()
        if fmt not in {"mp3", "wav"}:
            fmt = self.server.config.output_format
        audio, content_type = self.server.get_audio(fmt, prefer_disk=True)
        if audio is None or content_type is None:
            self._json_response({"error": "default audio not found"}, status=HTTPStatus.NOT_FOUND)
            return
        self._send_audio(audio, content_type)


class MoonlightVoiceServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(
        self,
        server_address: Tuple[str, int],
        config: ServiceConfig,
        audio_cache: Dict[str, bytes],
        active_files: Dict[str, str],
        audio_dir: Path,
        static_dir: Optional[Path] = None,
    ):
        super().__init__(server_address, MoonlightVoiceRequestHandler)
        self.config = config
        self.active_files: Dict[str, str] = active_files
        self.audio_cache = audio_cache
        self.started_at = time.time()
        self.audio_dir = audio_dir
        self.static_dir = static_dir or get_static_dir()
        self.response_library = ResponseLibrary(
            audio_dir, converter=_transcode_audio, validator=_validate_audio_content
        )

    def uptime_seconds(self) -> float:
        return time.time() - self.started_at

    def describe_config(self) -> Dict:
        safe_config = asdict(self.config)
        safe_config.pop("webui_settings_path", None)
        safe_config["output_file"] = str(self.config.resolved_audio_path())
        safe_config["available_formats"] = sorted(self.audio_cache.keys())
        safe_config["tts_cache_key"] = self.tts_cache_key()
        return safe_config

    def update_webui_settings(self, settings: object) -> Dict:
        self.config.update_webui_settings(settings)
        return self.describe_config()

    def get_audio(
        self, output_format: str, prefer_disk: bool = False
    ) -> Tuple[Optional[bytes], Optional[str]]:
        content_type = "audio/mpeg" if output_format == "mp3" else "audio/wav"
        audio = self.audio_cache.get(output_format)
        if prefer_disk:
            path = self.active_files.get(output_format)
            if path and Path(path).exists():
                try:
                    audio = Path(path).read_bytes()
                    self.audio_cache[output_format] = audio
                except Exception:
                    LOGGER.warning("Failed to read audio from disk at %s", path)
        if audio is None:
            fallback_format = "wav" if output_format == "mp3" else "mp3"
            audio = self.audio_cache.get(fallback_format)
            if audio:
                content_type = "audio/mpeg" if fallback_format == "mp3" else "audio/wav"
        if audio is None:
            return None, None
        return audio, content_type

    def _register_audio(self, output_format: str, path: Path, data: bytes) -> None:
        self.audio_cache[output_format] = data
        self.active_files[output_format] = str(path)
        if output_format == self.config.output_format:
            self.config.output_file = str(path)

    def set_audio(
        self,
        output_format: str,
        data: bytes,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> UploadResult:
        fmt = (output_format or "").lower()
        detected = _detect_format(filename, content_type)
        if detected and detected != fmt:
            fmt = detected
        if fmt not in {"mp3", "wav"}:
            fmt = detected or fmt
        if fmt not in {"mp3", "wav"}:
            raise RuntimeError("Unable to detect audio format. Please upload .mp3 or .wav")
        _validate_audio_content(data, fmt)
        base = self.audio_dir.resolve()
        name = Path(filename).name if filename else f"default.{fmt}"
        base_name = "default"
        normalized = f"{base_name}.{fmt}"
        renamed = normalized != name
        path = (base / normalized).resolve()
        try:
            path.relative_to(base)
        except ValueError as exc:
            raise ValueError("Invalid filename path") from exc
        # Remove any existing default audio so replacements never reuse stale files.
        self._purge_default_files()
        self._clear_default_cache()
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = path.with_suffix(path.suffix + ".tmp")
        temporary_path.write_bytes(data)
        temporary_path.replace(path)
        self._register_audio(fmt, path, data)

        target_format = "wav" if fmt == "mp3" else "mp3"
        converted_bytes, error = _transcode_audio(data, fmt, target_format)
        converted = bool(converted_bytes)
        converted_path: Optional[Path] = None
        if converted_bytes:
            target_name = Path("default").with_suffix(f".{target_format}").name
            converted_path = (base / target_name).resolve()
            try:
                converted_path.relative_to(base)
            except ValueError as exc:
                raise ValueError("Invalid filename path") from exc
            temporary_converted_path = converted_path.with_suffix(converted_path.suffix + ".tmp")
            temporary_converted_path.write_bytes(converted_bytes)
            temporary_converted_path.replace(converted_path)
            LOGGER.info(
                "Auto-converted %s upload to %s at %s",
                fmt,
                target_format,
                converted_path,
            )
            self._register_audio(target_format, converted_path, converted_bytes)
        elif error:
            LOGGER.warning("Could not auto-convert %s upload to %s: %s", fmt, target_format, error)
            # Ensure stale alternates are removed so outdated audio is never served.
            self._purge_default_files({target_format})
            self._clear_default_cache({target_format})

        return UploadResult(
            saved_path=path,
            saved_format=fmt,
            normalized_filename=normalized,
            renamed=renamed,
            converted=converted,
            converted_format=target_format,
            converted_path=converted_path,
            conversion_error=error if not converted else None,
        )

    def _clear_default_cache(self, formats: Optional[set[str]] = None) -> None:
        fmts = formats or {"mp3", "wav"}
        for fmt in fmts:
            self.audio_cache.pop(fmt, None)
            self.active_files.pop(fmt, None)

    def _purge_default_files(self, formats: Optional[set[str]] = None) -> None:
        fmts = formats or {"mp3", "wav"}
        if not self.audio_dir.exists():
            return
        for candidate in self.audio_dir.iterdir():
            if not candidate.is_file():
                continue
            ext = candidate.suffix.lower().lstrip(".")
            if ext in fmts:
                try:
                    candidate.unlink()
                except FileNotFoundError:
                    continue

    def delete_audio(self, output_format: Optional[str] = None) -> bool:
        removed = False
        targets = [output_format] if output_format else list({"mp3", "wav"})
        for fmt in targets:
            if fmt is None:
                continue
            current = self.active_files.get(fmt)
            if current:
                path = Path(current)
                if path.exists():
                    path.unlink()
                    removed = True
            removed = self.audio_cache.pop(fmt, None) is not None or removed
            self.active_files.pop(fmt, None)
        # Remove any stray default audio files to keep storage tidy.
        self._purge_default_files(set(targets))
        # Reset reference to default location so UI shows missing state.
        self.config.output_file = str(self.audio_dir / f"default.{self.config.output_format}")
        return removed

    def clear_storage(self) -> Dict:
        """Clear default audio and every stored response clip."""
        return {
            "default_audio_deleted": self.delete_audio(),
            "responses": self.response_library.clear(),
        }

    def tts_cache_key(self) -> str:
        """Return a fingerprint for every clip that may be served by `/tts`."""
        digest = sha256(self.response_library.tts_cache_key().encode("ascii"))
        for fmt, path_str in sorted(self.active_files.items()):
            path = Path(path_str)
            try:
                stat = path.stat()
            except FileNotFoundError:
                continue
            digest.update(fmt.encode("ascii"))
            digest.update(str(stat.st_size).encode("ascii"))
            digest.update(str(stat.st_mtime_ns).encode("ascii"))
        return digest.hexdigest()

    def describe_audio(self) -> Dict:
        default_files = []
        total_default_bytes = 0
        for fmt, path_str in sorted(self.active_files.items()):
            path = Path(path_str)
            if not path.exists():
                continue
            size = path.stat().st_size
            default_files.append(
                {
                    "format": fmt,
                    "path": str(path),
                    "size": size,
                    "updated_at": path.stat().st_mtime,
                }
            )
            total_default_bytes += size
        responses_stats = self.response_library.storage_stats()
        return {
            "available_formats": sorted(self.audio_cache.keys()),
            "files": self.active_files,
            "storage": {
                "audio_dir": str(self.audio_dir),
                "default_bytes": total_default_bytes,
                "default_files": len(default_files),
                "responses_bytes": responses_stats["bytes"],
                "responses_files": responses_stats["files"],
                "responses_entries": responses_stats["entries"],
                "total_bytes": total_default_bytes + responses_stats["bytes"],
            },
            "default_file_details": default_files,
        }


class MoonlightVoiceIngressServer(ThreadingHTTPServer):
    """Serve the same application state on the stable Supervisor Ingress port."""

    allow_reuse_address = True

    def __init__(self, server_address: Tuple[str, int], backend: MoonlightVoiceServer):
        super().__init__(server_address, MoonlightVoiceRequestHandler)
        self._backend = backend

    def __getattr__(self, name: str):
        return getattr(self._backend, name)


def load_audio_files(
    config: ServiceConfig,
) -> Tuple[Dict[str, bytes], Dict[str, str], Path]:
    """
    Preload audio bytes for quick responses.
    """
    audio: Dict[str, bytes] = {}
    file_map: Dict[str, str] = {}
    primary_path = config.resolved_audio_path()
    audio_dir = primary_path.parent if primary_path.parent != Path("/") else DEFAULT_AUDIO_DIR
    audio_dir.mkdir(parents=True, exist_ok=True)

    def try_load(path: Path, fmt: str) -> None:
        if path.exists() and path.is_file():
            audio[fmt] = path.read_bytes()
            file_map[fmt] = str(path)

    try_load(primary_path, config.output_format)

    # Attempt to load standard names in the audio directory for both formats.
    try_load(audio_dir / "default.mp3", "mp3")
    try_load(audio_dir / "default.wav", "wav")

    return audio, file_map, audio_dir


def run_server(config: ServiceConfig) -> None:
    config.normalize()
    LOGGER.info("Configured output file: %s", config.resolved_audio_path())
    audio_cache, file_map, audio_dir = load_audio_files(config)
    LOGGER.info("Audio directory resolved to %s", audio_dir)
    if file_map:
        for fmt, path in sorted(file_map.items()):
            LOGGER.info(
                "Preloaded audio [%s]: %s (%s bytes)",
                fmt,
                path,
                len(audio_cache.get(fmt, b"")),
            )
    if not audio_cache:
        LOGGER.warning(
            "No audio files loaded; service will return errors until a file is provided."
        )

    server = MoonlightVoiceServer(
        (config.host, config.port),
        config,
        audio_cache,
        file_map,
        audio_dir,
        get_static_dir(),
    )
    LOGGER.info("Starting Moonlight Voice server on %s:%s", config.host, config.port)
    ingress_server = None
    ingress_thread = None
    if config.port != INGRESS_PORT:
        ingress_server = MoonlightVoiceIngressServer((config.host, INGRESS_PORT), server)
        ingress_thread = Thread(
            target=ingress_server.serve_forever,
            name="moonlight-voice-ingress",
            daemon=True,
        )
        ingress_thread.start()
        LOGGER.info("Starting stable Ingress listener on %s:%s", config.host, INGRESS_PORT)

    discovery_thread = Thread(
        target=publish_discovery_with_retry,
        args=(config.port,),
        name="moonlight-voice-discovery",
        daemon=True,
    )
    discovery_thread.start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("Server interrupted, shutting down.")
    finally:
        if ingress_server:
            ingress_server.shutdown()
            ingress_server.server_close()
        server.server_close()
