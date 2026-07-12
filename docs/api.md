# API and security reference

Moonlight Voice serves local HTTP endpoints. The Home Assistant **Open Web UI** is available through authenticated Ingress. The direct port (`8031` by default) has no built-in authentication and must stay on a trusted local network.

## TTS response

`GET` or `POST /tts` returns an audio stream.

- `text` may be supplied as a query parameter or JSON field.
- `input` is accepted as a JSON field, including a list of strings or `{ "text": "..." }` items.
- `format` may be `mp3` or `wav` in the query or JSON body; the configured output format is used otherwise.
- A non-empty response code matches when the normalized request text is identical: surrounding whitespace is removed and comparison is case-insensitive.
- If no response code matches, the configured default clip is returned. If neither requested nor fallback audio is available, the service returns `500` JSON with an `error` field.

```bash
curl --request POST \
  --header 'Content-Type: application/json' \
  --data '{"input":"doorbell","format":"wav"}' \
  http://HOME_ASSISTANT_HOST:8031/tts \
  --output response.wav
```

## Management endpoints

### Endpoint model

Endpoint paths are fixed by the service and are resolved relative to the current page URL. This keeps browser requests below the Home Assistant Ingress prefix while also working on the trusted local direct port. The Advanced UI displays the effective URLs and can test only built-in read-only endpoints.

Moonlight Voice does not support runtime route aliases, arbitrary proxy targets, outbound URLs, or server-side request forwarding. There are therefore no endpoint settings to reset or persist; configuration changes remain separate from endpoint paths. This is intentional: failed browser input cannot change the service's routing or expose a new management surface.

The UI can suggest a direct-port host from the browser's current hostname, but cannot prove that this name is reachable on port `8031` from another device. The request-example host is therefore editable; use a trusted local hostname or IP address that is valid for your Home Assistant installation.

| Method and path | Purpose | Inputs and result |
| --- | --- | --- |
| `GET /health` | Service health | JSON status, start time, and uptime. |
| `GET /version` | Service version | JSON version. |
| `GET /config` | Active configuration | JSON configuration and available audio formats. |
| `GET /audio` | Default-audio inventory | JSON file and storage details. |
| `GET /audio/file?format=mp3|wav` | Stream default audio | Audio response or `404` JSON. |
| `POST /audio?format=mp3|wav&filename=name.ext` | Upload default audio | Raw MP3/WAV bytes; returns JSON upload result. |
| `DELETE /audio?format=mp3|wav` | Delete default audio | JSON deletion result. |
| `GET /responses` | List response codes | Supports `search`, `sort_by`, `sort_dir`, `page`, and `page_size`. |
| `GET /responses/file?code=doorbell&format=mp3|wav` | Stream a response clip | Audio response or `404` JSON. |
| `POST /responses?code=doorbell&filename=name.ext` | Upload a response clip | Raw MP3/WAV bytes; returns JSON upload result. |
| `PATCH /responses` | Rename a response code | JSON `{ "code": "old", "new_code": "new" }`. |
| `DELETE /responses?code=doorbell&format=mp3|wav` | Delete a response clip or code | Repeat `code` to delete multiple whole response codes at once. |
| `DELETE /storage` | Clear saved audio | Permanently removes the default audio and every response clip. |

`/audio` and `/responses` upload handlers accept MP3 and WAV based on the requested format, filename extension, or `Content-Type`. Uploads require a valid `Content-Length`, are rejected before reading when they exceed the configurable `max_upload_size_mb` limit (20 MiB by default), and must pass a lightweight MP3/WAV header probe before replacing active audio. Moonlight Voice attempts to create the alternate format with `ffmpeg`; if conversion is unavailable or fails, the original upload is retained and the JSON response reports the conversion error.

Invalid `Content-Length`, filenames, response codes, or audio content return a JSON `400` error; oversized bodies return `413`. Response codes are limited to 80 characters, filenames to 128 characters, the library to 500 codes, list pages to 100 entries, and the in-memory response cache to 32 MiB. Metadata updates use atomic replacement.

## Storage and retention

The service keeps the default clips, response clips, and `responses.json` metadata in `/data/moonlight-voice`, which persists across add-on restarts. Replacing a default clip removes stale default files; response clips remain until explicitly deleted.

Moonlight Voice makes no outbound network calls. It does not provide a public-internet authentication layer, so use Home Assistant Ingress for browser management and do not publish the direct port through a router or reverse proxy.
