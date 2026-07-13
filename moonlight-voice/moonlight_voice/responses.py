import json
import os
import re
import shutil
import threading
import time
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

MAX_RESPONSE_CODE_LENGTH = 80
MAX_FILENAME_LENGTH = 128
MAX_RESPONSE_COUNT = 500
MAX_CACHE_BYTES = 32 * 1024 * 1024


def _detect_format(filename: Optional[str], content_type: Optional[str]) -> Optional[str]:
    if filename:
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext in {"mp3", "wav"}:
            return ext
    if content_type:
        lowered = content_type.lower()
        if "mpeg" in lowered or "mp3" in lowered:
            return "mp3"
        if "wav" in lowered or "wave" in lowered:
            return "wav"
    return None


def _default_converter(
    _data: bytes, _source_format: str, _target_format: str
) -> Tuple[Optional[bytes], Optional[str]]:
    """Converter placeholder used when none is provided."""
    return None, "Conversion unavailable"


def _slugify(value: str, max_length: int = 64) -> str:
    """Create a filesystem-safe slug for storing response assets."""
    cleaned = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    cleaned = cleaned.strip("-")
    return (cleaned or "response")[:max_length]


def _normalize_code(code: str) -> str:
    candidate = (code or "").strip()
    if not candidate:
        raise ValueError("Response code is required")
    if len(candidate) > MAX_RESPONSE_CODE_LENGTH:
        raise ValueError(f"Response code must be at most {MAX_RESPONSE_CODE_LENGTH} characters")
    return candidate


def _key_for(code: str) -> str:
    return _normalize_code(code).lower()


@dataclass
class ResponseFile:
    format: str
    filename: str
    path: str
    size: int
    updated_at: float


@dataclass
class ResponseEntry:
    code: str
    key: str
    slug: str
    files: Dict[str, ResponseFile] = field(default_factory=dict)
    updated_at: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "code": self.code,
            "updated_at": self.updated_at,
            "formats": {fmt: file.__dict__ for fmt, file in self.files.items()},
        }


class ResponseLibrary:
    """Manage TTS response mappings backed by disk storage."""

    def __init__(
        self,
        base_dir: Path,
        converter: Optional[
            Callable[[bytes, str, str], Tuple[Optional[bytes], Optional[str]]]
        ] = None,
        validator: Optional[Callable[[bytes, str], None]] = None,
    ) -> None:
        self.base_dir = base_dir
        self.responses_dir = base_dir / "responses"
        self.metadata_path = base_dir / "responses.json"
        self.converter = converter or _default_converter
        self.validator = validator
        self.entries: Dict[str, ResponseEntry] = {}
        self.cache: Dict[str, Dict[str, bytes]] = {}
        self._lock = threading.Lock()
        self.responses_dir.mkdir(parents=True, exist_ok=True)
        self._load()

    # -- Persistence -------------------------------------------------
    def _load(self) -> None:
        if self.metadata_path.exists():
            try:
                data = json.loads(self.metadata_path.read_text(encoding="utf-8"))
                for item in data.get("responses", []):
                    code = _normalize_code(item.get("code", ""))
                    key = _key_for(code)
                    slug = item.get("slug") or _slugify(code)
                    files: Dict[str, ResponseFile] = {}
                    for fmt, meta in (item.get("formats") or {}).items():
                        path = Path(meta.get("path", ""))
                        if not path.exists() or not path.is_file():
                            continue
                        files[fmt] = ResponseFile(
                            format=fmt,
                            filename=meta.get("filename", path.name),
                            path=str(path),
                            size=meta.get("size", path.stat().st_size),
                            updated_at=meta.get("updated_at", path.stat().st_mtime),
                        )
                        self._cache_audio(key, fmt, path.read_bytes())
                    if files:
                        updated_at = item.get("updated_at") or max(
                            (file.updated_at for file in files.values()), default=0.0
                        )
                        self.entries[key] = ResponseEntry(
                            code=code,
                            key=key,
                            slug=slug,
                            files=files,
                            updated_at=updated_at,
                        )
            except Exception:
                # Fall back to scanning disk if metadata is corrupted
                self.entries = {}
                self.cache = {}
                self._scan_disk()
        else:
            self._scan_disk()

    def _scan_disk(self) -> None:
        if not self.responses_dir.exists():
            return
        for code_dir in self.responses_dir.iterdir():
            if not code_dir.is_dir():
                continue
            code = code_dir.name
            key = _key_for(code)
            files: Dict[str, ResponseFile] = {}
            for file in code_dir.iterdir():
                if file.suffix.lower() not in {".mp3", ".wav"}:
                    continue
                fmt = file.suffix.lstrip(".").lower()
                files[fmt] = ResponseFile(
                    format=fmt,
                    filename=file.name,
                    path=str(file),
                    size=file.stat().st_size,
                    updated_at=file.stat().st_mtime,
                )
                self._cache_audio(key, fmt, file.read_bytes())
            if files:
                updated_at = max((file.updated_at for file in files.values()), default=0.0)
                self.entries[key] = ResponseEntry(
                    code=code,
                    key=key,
                    slug=code_dir.name,
                    files=files,
                    updated_at=updated_at,
                )
        self._save()

    def _save(self) -> None:
        payload: dict[str, list[dict[str, object]]] = {"responses": []}
        for entry in sorted(self.entries.values(), key=lambda e: e.code.lower()):
            payload["responses"].append(
                {
                    "code": entry.code,
                    "slug": entry.slug,
                    "updated_at": entry.updated_at,
                    "formats": {fmt: file.__dict__ for fmt, file in entry.files.items()},
                }
            )
        temporary_path = self.metadata_path.with_suffix(".json.tmp")
        temporary_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(temporary_path, self.metadata_path)

    def _cache_audio(self, key: str, fmt: str, data: bytes) -> None:
        cached_bytes = sum(
            len(audio) for formats in self.cache.values() for audio in formats.values()
        )
        if len(data) <= MAX_CACHE_BYTES and cached_bytes + len(data) <= MAX_CACHE_BYTES:
            self.cache.setdefault(key, {})[fmt] = data

    # -- Public API --------------------------------------------------
    def list(
        self,
        search: Optional[str],
        page: int,
        page_size: int,
        sort_by: str = "code",
        sort_dir: str = "asc",
    ) -> Dict:
        needle = (search or "").strip().lower()
        all_entries: List[ResponseEntry] = list(self.entries.values())
        if needle:
            entries = [entry for entry in all_entries if needle in entry.code.lower()]
        else:
            entries = list(all_entries)
        reverse = sort_dir.lower() == "desc"
        if sort_by == "updated":
            entries.sort(key=lambda e: e.updated_at, reverse=reverse)
        else:
            entries.sort(key=lambda e: e.code.lower(), reverse=reverse)
        total = len(entries)
        start = max(page - 1, 0) * page_size
        end = start + page_size
        page_items = entries[start:end]
        formats: set[str] = set()
        total_size = 0
        for entry in all_entries:
            formats.update(entry.files.keys())
            for meta in entry.files.values():
                total_size += meta.size
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "items": [entry.to_dict() for entry in page_items],
            "stats": {
                "total_responses": len(all_entries),
                "available_formats": sorted(formats),
                "sort_by": "updated" if sort_by == "updated" else "code",
                "sort_dir": "desc" if reverse else "asc",
                "total_bytes": total_size,
            },
        }

    def find_match(self, text: str) -> Optional[ResponseEntry]:
        candidate = (text or "").strip().lower()
        if not candidate:
            return None
        return self.entries.get(candidate)

    def audio_for(self, code: str, fmt: str) -> Optional[bytes]:
        key = _key_for(code)
        cache = self.cache.get(key, {})
        audio = cache.get(fmt)
        if audio is not None:
            return audio
        entry = self.entries.get(key)
        if not entry:
            return None
        file = entry.files.get(fmt)
        if file and Path(file.path).exists():
            data = Path(file.path).read_bytes()
            self._cache_audio(key, fmt, data)
            return data
        return None

    def audio_for_preferred_format(
        self, code: str, preferred_format: str
    ) -> tuple[Optional[bytes], Optional[str]]:
        """Return a response clip, preferring but not requiring one format."""
        formats = (preferred_format, "wav" if preferred_format == "mp3" else "mp3")
        for fmt in formats:
            audio = self.audio_for(code, fmt)
            if audio is not None:
                return audio, fmt
        return None, None

    def tts_cache_key(self) -> str:
        """Return a stable fingerprint that changes with the response library."""
        digest = sha256()
        with self._lock:
            for entry in sorted(self.entries.values(), key=lambda item: item.key):
                digest.update(entry.key.encode("utf-8"))
                digest.update(str(entry.updated_at).encode("ascii"))
                for fmt, file in sorted(entry.files.items()):
                    digest.update(fmt.encode("ascii"))
                    digest.update(str(file.size).encode("ascii"))
                    digest.update(str(file.updated_at).encode("ascii"))
        return digest.hexdigest()

    def _remove_file(self, entry: ResponseEntry, fmt: str) -> None:
        file_meta = entry.files.pop(fmt, None)
        if file_meta:
            try:
                Path(file_meta.path).unlink()
            except FileNotFoundError:
                pass
            self.cache.get(entry.key, {}).pop(fmt, None)

    def store_audio(
        self,
        code: str,
        data: bytes,
        filename: Optional[str] = None,
        content_type: Optional[str] = None,
    ) -> Dict:
        fmt = _detect_format(filename, content_type)
        if fmt not in {"mp3", "wav"}:
            raise RuntimeError("Unable to detect audio format. Use .mp3 or .wav filename.")
        if self.validator:
            self.validator(data, fmt)
        code_value = _normalize_code(code)
        key = _key_for(code_value)
        slug = self.entries.get(
            key, ResponseEntry(code=code_value, key=key, slug=_slugify(code_value))
        ).slug
        if key not in self.entries and len(self.entries) >= MAX_RESPONSE_COUNT:
            raise RuntimeError(f"Response limit of {MAX_RESPONSE_COUNT} reached")
        target_dir = self.responses_dir / slug
        target_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename or f"{slug}.{fmt}").name
        if len(safe_name) > MAX_FILENAME_LENGTH:
            raise ValueError(f"Filename must be at most {MAX_FILENAME_LENGTH} characters")
        if not safe_name.endswith(f".{fmt}"):
            safe_name = f"{Path(safe_name).stem}.{fmt}"
        path = target_dir / safe_name
        with self._lock:
            entry = self.entries.get(key) or ResponseEntry(code=code_value, key=key, slug=slug)
            # Remove stale files before writing replacements so older assets are not served.
            self._remove_file(entry, fmt)
            alt_fmt = "wav" if fmt == "mp3" else "mp3"
            self._remove_file(entry, alt_fmt)

            temporary_path = path.with_suffix(path.suffix + ".tmp")
            temporary_path.write_bytes(data)
            temporary_path.replace(path)
            file_meta = ResponseFile(
                format=fmt,
                filename=safe_name,
                path=str(path),
                size=len(data),
                updated_at=time.time(),
            )
            entry.files[fmt] = file_meta
            self._cache_audio(key, fmt, data)

            # Attempt to auto-convert the alternate format
            converted_bytes, error = self.converter(data, fmt, alt_fmt)
            conversion = {
                "converted": False,
                "converted_format": alt_fmt,
                "converted_path": None,
                "conversion_error": error,
            }
            if converted_bytes:
                alt_name = f"{Path(safe_name).stem}.{alt_fmt}"
                alt_path = target_dir / alt_name
                temporary_alt_path = alt_path.with_suffix(alt_path.suffix + ".tmp")
                temporary_alt_path.write_bytes(converted_bytes)
                temporary_alt_path.replace(alt_path)
                entry.files[alt_fmt] = ResponseFile(
                    format=alt_fmt,
                    filename=alt_name,
                    path=str(alt_path),
                    size=len(converted_bytes),
                    updated_at=time.time(),
                )
                self._cache_audio(key, alt_fmt, converted_bytes)
                conversion.update(
                    {
                        "converted": True,
                        "converted_path": str(alt_path),
                        "conversion_error": None,
                    }
                )
            else:
                # Ensure stale alternates cannot be served when conversion fails.
                self._remove_file(entry, alt_fmt)

            self.entries[key] = entry
            entry.updated_at = max(
                (meta.updated_at for meta in entry.files.values()), default=time.time()
            )
            self._save()
            payload = {
                "code": entry.code,
                "format": fmt,
                "path": str(path),
                "filename": safe_name,
                **conversion,
            }
        return payload

    def rename(self, code: str, new_code: str) -> Dict:
        old_key = _key_for(code)
        new_value = _normalize_code(new_code)
        new_key = _key_for(new_value)
        if old_key not in self.entries:
            raise KeyError("Response not found")
        if new_key != old_key and new_key in self.entries:
            raise ValueError("A response with that code already exists")
        with self._lock:
            entry = self.entries.pop(old_key)
            old_dir = self.responses_dir / entry.slug
            new_slug = _slugify(new_value)
            new_dir = self.responses_dir / new_slug
            if old_dir.exists():
                new_dir.parent.mkdir(parents=True, exist_ok=True)
                old_dir.rename(new_dir)
            entry.code = new_value
            entry.key = new_key
            entry.slug = new_slug
            for _fmt, meta in entry.files.items():
                meta.path = str(new_dir / Path(meta.filename).name)
            self.entries[new_key] = entry
            self.cache[new_key] = self.cache.pop(old_key, {})
            self._save()
        return entry.to_dict()

    def delete(self, code: str, fmt: Optional[str] = None) -> Dict:
        key = _key_for(code)
        if key not in self.entries:
            return {"deleted": False}
        with self._lock:
            entry = self.entries[key]
            if fmt:
                fmt = fmt.lower()
                removed = False
                file_meta = entry.files.get(fmt)
                if file_meta:
                    removed = Path(file_meta.path).exists()
                    self._remove_file(entry, fmt)
                if not entry.files:
                    shutil.rmtree(self.responses_dir / entry.slug, ignore_errors=True)
                    self.entries.pop(key, None)
                    self.cache.pop(key, None)
                else:
                    entry.updated_at = max(
                        (meta.updated_at for meta in entry.files.values()),
                        default=entry.updated_at,
                    )
                self._save()
                return {"deleted": removed, "format": fmt, "code": entry.code}

            # delete entire entry
            shutil.rmtree(self.responses_dir / entry.slug, ignore_errors=True)
            self.entries.pop(key, None)
            self.cache.pop(key, None)
            self._save()
            return {"deleted": True, "code": entry.code}

    def delete_many(self, codes: List[str]) -> Dict:
        """Delete complete response entries for the supplied response codes."""
        requested = list(dict.fromkeys(code for code in codes if code))
        deleted_codes: List[str] = []
        with self._lock:
            for code in requested:
                key = _key_for(code)
                entry = self.entries.get(key)
                if not entry:
                    continue
                shutil.rmtree(self.responses_dir / entry.slug, ignore_errors=True)
                self.entries.pop(key, None)
                self.cache.pop(key, None)
                deleted_codes.append(entry.code)
            if deleted_codes:
                self._save()
        return {"deleted": len(deleted_codes), "codes": deleted_codes}

    def clear(self) -> Dict:
        """Remove every stored response clip and recreate the empty response library."""
        with self._lock:
            files = sum(len(entry.files) for entry in self.entries.values())
            entries = len(self.entries)
            shutil.rmtree(self.responses_dir, ignore_errors=True)
            self.responses_dir.mkdir(parents=True, exist_ok=True)
            self.entries.clear()
            self.cache.clear()
            self._save()
        return {"deleted": entries, "files": files}

    def storage_stats(self) -> Dict:
        total_size = 0
        total_files = 0
        for entry in self.entries.values():
            for meta in entry.files.values():
                total_size += meta.size
                total_files += 1
        return {
            "bytes": total_size,
            "files": total_files,
            "entries": len(self.entries),
            "dir": str(self.responses_dir),
        }
