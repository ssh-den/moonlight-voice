# Quickstart

## Install and open Moonlight Voice

1. In Home Assistant, open **Settings → Add-ons → Add-on Store**.
2. Add `https://github.com/ssh-den/moonlight-voice` as an add-on repository.
3. Install and start **Moonlight Voice**.
4. Select **Open Web UI** on the add-on page. This uses authenticated Home Assistant Ingress and is the recommended management path.

## Add audio

1. In the default **Audio library** tab, upload an MP3 or WAV file as the default response.
2. Add a response code, for example `doorbell`.
3. Upload an MP3 or WAV clip for that response code. You can search, sort, play, rename, or delete library items from the same tab.

When a `/tts` request sends `text` or `input` equal to `doorbell` (ignoring surrounding whitespace and letter case), Moonlight Voice returns the `doorbell` clip. A request without a matching code returns the default clip.

## Send a local test request

Direct HTTP access uses host port `8031` by default. You can disable or remap it in the add-on's **Network** settings if the port is already occupied; use the effective host port in the command below. Do not expose its management API to the public internet. The add-on's configurable `port` is a separate private backend port for the native Home Assistant integration and is discovered automatically through the Supervisor network.

```bash
curl --request POST \
  --header 'Content-Type: application/json' \
  --data '{"text":"doorbell","format":"mp3"}' \
  http://HOME_ASSISTANT_HOST:8031/tts \
  --output response.mp3
```

Replace `HOME_ASSISTANT_HOST` with the local hostname or IP. If you remapped port `8031`, use the selected host port instead. The response is an audio stream, so the example writes it to `response.mp3`.

## Back up audio

Audio, response-library files, and response metadata are stored in `/data/moonlight-voice` inside the add-on's persistent data volume. Back up that directory using your normal Home Assistant backup process before reinstalling or moving the add-on.

See [API and security](api.md) for every supported endpoint and upload behavior.

The **Service** tab is read-only status and configuration. **Advanced** shows the Ingress-relative management URLs, includes a safe read-only endpoint tester, and distinguishes the discovered private integration port from the internal Ingress listener on `8031`; it does not expose configurable routes or outbound proxying. Its request example starts with the hostname used to open the UI, and you can replace it with the local hostname or IP that reaches a mapped host port.
