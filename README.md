# Moonlight Voice

Moonlight Voice is a local audio response service for Home Assistant. Instead of generating text-to-speech, it returns a preloaded MP3 or WAV file.

It can be used with Home Assistant Voice through the OpenAI-like integration. Support for custom endpoints is planned for the future. It's useful for testing and demoing voice automations without cloud services, credentials, variable output, or network latency. Everything runs locally, making responses fast, predictable, and consistent.

## How response matching works

A `/tts` request whose `text` or `input` exactly matches a response code serves that response's clip. Matching trims surrounding whitespace and ignores case. All other requests receive the default clip in the requested format, if available.

Moonlight Voice supports its documented local endpoints and OpenAI-style request fields; it is not a drop-in implementation of the OpenAI API.

## Install in Home Assistant

Add [this repository](https://github.com/ssh-den/moonlight-voice) to the Home Assistant Add-on Store, install **Moonlight Voice**, start it, then use **Open Web UI**. The UI is served through authenticated Home Assistant Ingress.

For the complete first-run path, request examples, backup guidance, and direct-port security boundary, see [Quickstart](docs/quickstart.md). See the supported methods and payloads in the [API and security reference](docs/api.md).

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

Run the service locally with Python 3:

```bash
PYTHONPATH=moonlight-voice python3 -m moonlight_voice
```

The persistent directory is `/data/moonlight-voice`.

## Links

[Quickstart](docs/quickstart.md) · [API and security](docs/api.md) · [License](LICENSE)
