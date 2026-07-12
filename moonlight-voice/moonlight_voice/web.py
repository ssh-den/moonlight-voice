import re
from functools import lru_cache
from pathlib import Path
from typing import Tuple

CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".ico": "image/x-icon",
}

INDEX_COMPONENT_PATTERN = re.compile(rb"<!-- include: ([a-z0-9][a-z0-9-]*\.html) -->")


def get_static_dir() -> Path:
    """
    Return the packaged static directory for the web UI.
    """
    return Path(__file__).resolve().parent / "static"


def _resolve_static_path(static_dir: Path, relative_path: str) -> Path:
    """
    Resolve a path inside the static directory and guard against traversal.
    """
    safe_relative = relative_path.lstrip("/")
    candidate = (static_dir / safe_relative).resolve()
    candidate.relative_to(static_dir)
    return candidate


@lru_cache(maxsize=32)
def _read_file(path: Path) -> bytes:
    return path.read_bytes()


def load_static_asset(relative_path: str, static_dir: Path | None = None) -> Tuple[bytes, str]:
    """
    Load a static asset from disk, returning its bytes and content type.
    Raises FileNotFoundError when the file does not exist and ValueError on traversal attempts.
    """
    base = static_dir or get_static_dir()
    path = _resolve_static_path(base, relative_path)
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(path)
    content_type = CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream")
    return _read_file(path), content_type


def load_index_html(static_dir: Path | None = None) -> Tuple[bytes, str]:
    """
    Load the UI entrypoint and compose its named HTML components.

    Components are deliberately limited to files in ``static/components`` so the
    page remains readable without allowing arbitrary file inclusion.
    """
    base = static_dir or get_static_dir()
    index, content_type = load_static_asset("index.html", base)

    def include_component(match: re.Match[bytes]) -> bytes:
        component_name = match.group(1).decode("ascii")
        component_path = _resolve_static_path(base, f"components/{component_name}")
        return _read_file(component_path)

    return INDEX_COMPONENT_PATTERN.sub(include_component, index), content_type
