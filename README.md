# Moonlight Voice

Moonlight Voice is a local audio response service for Home Assistant. Instead of generating text-to-speech, it returns a preloaded MP3 or WAV file.

It has two local operating modes: an OpenAI-compatible TTS endpoint for direct HTTP clients, and the Moonlight Voice integration for Home Assistant's native TTS platform. It is useful for testing and demoing voice automations without cloud services, credentials, variable output, or network latency. Everything runs locally, making responses fast, predictable, and consistent.

## How response matching works

A `/tts` request whose `text` or `input` exactly matches a response code serves that response's clip. Matching trims surrounding whitespace and ignores case. All other requests receive the default clip in the requested format, if available.

Moonlight Voice supports its documented local endpoints and OpenAI-style request fields; it is not a drop-in implementation of the OpenAI API.

## Install in Home Assistant

Add [this repository](https://github.com/ssh-den/moonlight-voice) to the Home Assistant Add-on Store, install **Moonlight Voice**, start it, then use **Open Web UI**. The UI is served through authenticated Home Assistant Ingress.

For the complete first-run path, request examples, backup guidance, and direct-port security boundary, see [Quickstart](docs/quickstart.md). See the supported methods and payloads in the [API and security reference](docs/api.md).

## Choose a TTS mode

### OpenAI-compatible TTS endpoint

This is the default add-on mode: set `tts_mode` to `openai_compatible`. Configure an HTTP client that supports OpenAI-style TTS fields to send requests to `http://HOME_ASSISTANT_HOST:8031/tts`; use `input` (or `text`) for the requested response code and optionally `format` (`mp3` or `wav`). The matching saved clip is returned; an unmatched code returns the default clip.

Moonlight Voice supports these OpenAI-style request fields but is not a full OpenAI API implementation: it exposes `/tts`, not `/v1/audio/speech`. Use this mode when the calling application can be pointed at a custom TTS endpoint.

### Moonlight Voice integration

Set `tts_mode` to `home_assistant` and restart the add-on. The native integration registers a Home Assistant TTS entity, so it can be selected in an Assist pipeline or used with `tts.speak`. Every spoken message is sent to `/tts` as `message`, then matched against saved response codes.

#### Install the integration through HACS

1. In HACS, open **Integrations**, then open the menu and choose **Custom repositories**.
2. Add `https://github.com/ssh-den/moonlight-voice` with category **Integration**.
3. Find **Moonlight Voice** in HACS and select **Download**.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration**, choose **Moonlight Voice**, and enter the add-on URL reachable from Home Assistant. For the locally deployed add-on, use `http://local-moonlight-voice:8031`.

For a manual install, copy `custom_components/moonlight_voice` into `<Home Assistant config>/custom_components/moonlight_voice`, then restart Home Assistant. The integration automatically changes its Home Assistant TTS cache key after the response library changes. See [native TTS setup](docs/home-assistant-tts.md).

## Local development

The add-on runtime uses only the Python standard library plus `ffmpeg` supplied by its base image. Python and Node.js tooling below is development-only and is not copied into the add-on image.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements-dev.txt
npm ci
./scripts/check.sh
```

`check.sh` runs formatters, Python linters and type checkers, both Python test suites, ESLint, Prettier, and the JavaScript type check. Use the individual commands from [scripts/check.sh](scripts/check.sh) when investigating a failed check.

Regenerate the HACS and add-on icons from the Web UI's `moon-star.svg` with:

```bash
python3 scripts/generate_icons.py
```

Run the service locally with Python 3:

```bash
PYTHONPATH=moonlight-voice python3 -m moonlight_voice
```

The persistent directory is `/data/moonlight-voice`.

## Links

[Quickstart](docs/quickstart.md) · [API and security](docs/api.md) · [License](LICENSE)
