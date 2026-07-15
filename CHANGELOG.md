# Changelog

## 1.4.2

- Preserved the Supervisor token in the s6 service environment so automatic integration discovery is actually published.
- Retried discovery publication in the background until Supervisor accepts it, without delaying the HTTP service startup.
- Made Home Assistant TTS the default mode for new installations while preserving explicit saved settings.

## 1.4.1

- Restored the default host mapping for port `8031` so direct local URLs work after installation.
- Restored the Supervisor discovery service allow-list required for the add-on to publish its private endpoint.
- Kept discovered flows visible until the user confirms connectivity and Home Assistant TTS mode, while preserving a stable Supervisor unique ID.
- Registered the Moonlight Voice TTS provider as a Home Assistant service device.

## 1.4.0

- Prefilled the manual integration URL from Home Assistant's internal hostname on the add-on port.
- Clarified the Web UI's Ingress URLs and direct add-on URL so port `8123` is not confused with port `8031`.

## 1.3.0

- Added Home Assistant Supervisor discovery for the Moonlight Voice add-on, prefilling the integration's URL field with the discovered internal address.

## 1.2.0

- Added the Moonlight Voice icon to the integration's local `brand/` directory so it is displayed by current Home Assistant and HACS installations.
- Updated the icon-generation script to keep the local integration brand asset in sync with the other generated icons.

## 1.1.0

- Added a selectable TTS mode and persistent Web UI settings for OpenAI-compatible clients or Home Assistant's native TTS platform.
- Added the Moonlight Voice custom integration with HACS metadata, configuration flow, native `tts.speak` support, and setup documentation.
- Added automatic Home Assistant TTS cache invalidation when default or named response clips change.
- Added `message` payload support for the native integration while preserving OpenAI-compatible `input` and `text` requests.
- Improved audio delivery by falling back to an available MP3 or WAV response format when the requested format is missing.
- Improved the Web UI with TTS settings, default-file details, response preview and deletion actions, and refreshed Moon Star icons.
- Added redacted debug request logging, generated add-on/integration icons, and a release workflow that validates version and changelog consistency.

## 1.0.0 — Initial release

- Local, deterministic MP3/WAV responses for Home Assistant voice automations.
- Home Assistant Ingress UI for managing a default clip and named response clips.
- Documented local API, persistent audio storage, upload validation, and direct-port security boundary.
