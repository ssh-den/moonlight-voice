# Native Home Assistant TTS

Moonlight Voice can appear in Home Assistant as a TTS provider. It does not synthesize speech: it sends the requested message to the add-on and plays the saved response clip whose code matches that message. If no code matches, the default clip is used.

## Set up

1. In the Moonlight Voice Web UI, set `tts_mode` to `home_assistant`.
2. Install `custom_components/moonlight_voice` from this repository into `<Home Assistant config>/custom_components/moonlight_voice`, or install the repository through HACS as an integration.
3. Restart Home Assistant after installing the custom integration.
4. The Supervisor discovers the running Moonlight Voice add-on and opens its configuration form under **Settings → Devices & services** with the add-on's private Docker IP and configured `port` already filled in. When the add-on restarts after a port change, it republishes the endpoint; an existing Moonlight Voice integration entry is updated and reloaded automatically.

   If discovery is not available (for example, Home Assistant Container or Core without the Supervisor), go to **Settings → Devices & services → Add integration** and choose **Moonlight Voice**. Enter an endpoint that Home Assistant can reach. For this repository deployed through the local `addons` share, the fallback is `http://local-moonlight-voice:8031`.

   Home Assistant generates an add-on hostname as `{repository}_{slug}` and Docker DNS uses the same name with underscores replaced by hyphens. Therefore, an add-on from a different repository needs that repository's generated identifier instead of `local`.

   The configured add-on `port` is for the private backend used by the native integration. Ingress keeps a separate internal listener on `8031`, so changing the backend port does not change the add-on Web UI URL. Internal port `8031` is also mapped to host port `8031` by default for direct local access; the mapping can be disabled or changed in the add-on's **Network** settings without affecting Supervisor discovery.
5. Select the created `tts.moonlight_voice_response_audio` entity in an Assist pipeline or call `tts.speak` with it. Moonlight Voice also appears as a service in the Home Assistant device registry.

For example, if the library contains a response code named `front door`, then a TTS request with exactly `front door` will play that clip. Matching ignores letter case and surrounding whitespace.

## Cache behavior

The custom integration polls a fingerprint of the default and response clips every five seconds. When the fingerprint changes, it is included in Home Assistant's TTS cache key, so a response code that was added or replaced does not reuse an earlier cached default clip.

## Remove old saved audio

Saved audio survives restarts and add-on updates. To delete data retained from an earlier installation, open the add-on UI, choose **Service**, and select **Clear all data**. This removes the default clips, all named response clips, and response metadata from the add-on data volume. It is irreversible and takes effect immediately.
