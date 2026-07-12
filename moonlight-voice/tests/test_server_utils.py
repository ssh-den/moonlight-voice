import json

from moonlight_voice import server
from moonlight_voice.config import ServiceConfig


def test_detect_format_helper():
    assert server._detect_format("clip.mp3", None) == "mp3"
    assert server._detect_format("clip.wav", "audio/wave") == "wav"
    assert server._detect_format(None, "audio/mpeg") == "mp3"
    assert server._detect_format(None, None) is None


def test_extract_tts_text_handles_openai_payloads():
    handler = object.__new__(server.MoonlightVoiceRequestHandler)
    query = ""
    body = json.dumps({"input": [{"text": "hello"}, {"text": "world"}]}).encode()
    result = handler._extract_tts_text(server.urlparse(f"/tts?{query}"), body)
    assert result == "hello world"

    body = json.dumps(["one", "two"]).encode()
    result = handler._extract_tts_text(server.urlparse("/tts"), body)
    assert result == "one two"


def test_set_audio_purges_stale_files(tmp_path, monkeypatch):
    config = ServiceConfig(output_file=str(tmp_path / "default.mp3"))
    audio_cache, file_map, audio_dir = server.load_audio_files(config)
    monkeypatch.setattr(server, "_transcode_audio", lambda data, s, t: (None, "disabled"))
    srv = server.MoonlightVoiceServer(("127.0.0.1", 0), config, audio_cache, file_map, audio_dir)
    try:
        srv.set_audio("mp3", b"ID3\x04\x00\x00\x00\x00\x00\x00", filename="first.mp3")
        stale = audio_dir / "default.wav"
        stale.write_bytes(b"stale")

        srv.set_audio("mp3", b"ID3\x04\x00\x00\x00\x00\x00\x00", filename="second.mp3")

        assert not stale.exists()
        assert "wav" not in srv.audio_cache
        assert srv.active_files.get("mp3") == str(audio_dir / "default.mp3")
    finally:
        srv.server_close()
