import json
from pathlib import Path

from moonlight_voice.responses import ResponseLibrary, _detect_format


def test_detect_format_by_extension_and_content_type():
    assert _detect_format("sound.mp3", None) == "mp3"
    assert _detect_format("sound.wav", None) == "wav"
    assert _detect_format(None, "audio/mpeg") == "mp3"
    assert _detect_format(None, "audio/wave") == "wav"
    assert _detect_format("unknown.bin", "application/octet-stream") is None


def test_store_audio_auto_converts_and_persists_metadata(tmp_path: Path):
    base = tmp_path / "data"
    base.mkdir()

    def converter(data: bytes, source: str, target: str):
        return b"alt-bytes", None

    lib = ResponseLibrary(base, converter=converter)
    result = lib.store_audio("Doorbell", b"primary-bytes", filename="ding.mp3")

    assert result["code"] == "Doorbell"
    assert result["format"] == "mp3"
    response_dir = base / "responses" / "doorbell"
    assert (response_dir / "ding.mp3").exists()
    assert (response_dir / "ding.wav").exists()

    saved = lib.list(search=None, page=1, page_size=10)
    assert saved["stats"]["total_responses"] == 1
    assert "mp3" in saved["stats"]["available_formats"]
    assert "wav" in saved["stats"]["available_formats"]

    meta_path = base / "responses.json"
    assert meta_path.exists()
    payload = json.loads(meta_path.read_text())
    assert payload["responses"][0]["code"] == "Doorbell"


def test_rename_and_delete_response(tmp_path: Path):
    base = tmp_path / "data"
    base.mkdir()
    lib = ResponseLibrary(base, converter=lambda d, s, t: (None, None))
    lib.store_audio("Chime", b"bytes", filename="chime.wav")

    renamed = lib.rename("Chime", "Front Door")
    assert renamed["code"] == "Front Door"

    delete_result = lib.delete("Front Door")
    assert delete_result["deleted"] is True
    assert not lib.entries


def test_store_audio_removes_stale_alternate(tmp_path: Path):
    base = tmp_path / "data"
    base.mkdir()
    calls = {"count": 0}

    def converter(data: bytes, source: str, target: str):
        calls["count"] += 1
        if calls["count"] == 1:
            return b"alt-data", None
        return None, "conversion disabled"

    lib = ResponseLibrary(base, converter=converter)
    lib.store_audio("Doorbell", b"primary", filename="ding.mp3")
    alt_path = base / "responses" / "doorbell" / "ding.wav"
    assert alt_path.exists()

    lib.store_audio("Doorbell", b"replacement", filename="ding.mp3")
    # Second upload disables conversion, so old wav should be cleaned up.
    assert not alt_path.exists()
    # Only the mp3 should be cached.
    entry = next(iter(lib.entries.values()))
    assert "wav" not in lib.cache.get(entry.key, {})


def test_response_audio_falls_back_to_available_format(tmp_path: Path):
    base = tmp_path / "data"
    base.mkdir()
    lib = ResponseLibrary(base, converter=lambda d, s, t: (None, "conversion disabled"))
    lib.store_audio("Success", b"mp3-bytes", filename="success.mp3")

    audio, fmt = lib.audio_for_preferred_format("success", "wav")

    assert audio == b"mp3-bytes"
    assert fmt == "mp3"


def test_tts_cache_key_changes_with_response_library(tmp_path: Path):
    base = tmp_path / "data"
    base.mkdir()
    lib = ResponseLibrary(base, converter=lambda d, s, t: (None, "conversion disabled"))
    original_key = lib.tts_cache_key()

    lib.store_audio("Success", b"mp3-bytes", filename="success.mp3")

    assert lib.tts_cache_key() != original_key
