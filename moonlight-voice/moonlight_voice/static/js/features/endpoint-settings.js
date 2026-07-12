import { byId } from "../dom.js";

export function setupEndpointSettings({ api, notify }) {
  const select = byId("endpoint-test-select");
  const result = byId("endpoint-test-result");
  const directHost = byId("direct-host");
  const requestExample = byId("request-example");
  document.querySelectorAll("[data-effective-url]").forEach((element) => {
    const urlElement = /** @type {HTMLElement} */ (element);
    urlElement.textContent = api.endpoint(urlElement.dataset.effectiveUrl);
  });
  function renderRequestExample() {
    const host = directHost.value.trim() || "HOME_ASSISTANT_HOST";
    requestExample.textContent = `curl --request POST --header 'Content-Type: application/json' --data '{"text":"doorbell","format":"mp3"}' http://${host}:8031/tts --output response.mp3`;
  }
  directHost.value = window.location.hostname || "HOME_ASSISTANT_HOST";
  directHost.addEventListener("input", renderRequestExample);
  renderRequestExample();
  byId("endpoint-test")?.addEventListener("click", async () => {
    const path = select?.value;
    const allowed = new Set([
      "health",
      "version",
      "config",
      "audio",
      "responses",
    ]);
    if (!allowed.has(path))
      return notify(
        "Only built-in read-only endpoints can be tested.",
        "warning",
      );
    result.textContent = "Loading…";
    try {
      result.textContent = JSON.stringify(
        await api.testReadonly(path),
        null,
        2,
      );
    } catch (error) {
      result.textContent = error.message;
      notify(error.message);
    }
  });
  byId("copy-request-example")?.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(byId("request-example").textContent);
      notify("Request example copied.", "success");
    } catch {
      notify(
        "Copy is unavailable in this browser. Select the example manually.",
        "warning",
      );
    }
  });
}
