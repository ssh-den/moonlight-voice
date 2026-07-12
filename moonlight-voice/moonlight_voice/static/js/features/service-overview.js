import {
  formatBytes,
  formatDuration,
  formatTimestamp,
  setText,
} from "../dom.js";

export function setupServiceOverview({ state, api, dialogs, notify, refresh }) {
  const fields = Object.fromEntries(
    [...document.querySelectorAll("[data-field]")].map((element) => {
      const field = /** @type {HTMLElement} */ (element);
      return [field.dataset.field, field];
    }),
  );
  const clearStorage = /** @type {HTMLButtonElement | null} */ (
    document.getElementById("clear-storage")
  );

  function render() {
    const health = state.get("health");
    const config = state.get("config");
    const audio = state.get("audio");
    const responses = state.get("responses");
    if (!health && !config && !audio) return;
    const healthy = health?.status === "ok";
    const status = fields.status;
    if (status) {
      status.replaceChildren();
      const dot = document.createElement("span");
      dot.className = `status-dot ${healthy ? "status-dot--ok" : "status-dot--error"}`;
      status.append(
        dot,
        document.createTextNode(healthy ? "Healthy" : "Unavailable"),
      );
    }
    setText(fields.version, config?.version || state.get("version") || "—");
    setText(fields.uptime, formatDuration(health?.uptime_seconds));
    setText(fields["started-at"], formatTimestamp(health?.started_at));
    setText(fields["output-format"], config?.output_format || "—");
    setText(fields["output-file"], config?.output_file || "—");
    setText(
      fields["cache-headers"],
      config?.cache_headers ? "Enabled" : "Disabled",
    );
    setText(fields["response-count"], responses?.stats?.total_responses ?? "—");
    setText(fields["storage-used"], formatBytes(audio?.storage?.total_bytes));
    setText(
      fields["default-storage"],
      formatBytes(audio?.storage?.default_bytes),
    );
    setText(
      fields["responses-storage"],
      formatBytes(audio?.storage?.responses_bytes),
    );
    const files = Object.keys(audio?.files || {});
    setText(
      fields["default-audio"],
      files.length ? files.join(", ") : "Missing",
    );
  }

  clearStorage?.addEventListener("click", async () => {
    if (
      !(await dialogs.confirm(
        "This permanently deletes the default audio and every response clip from disk.",
        "Clear all data",
      ))
    )
      return;
    clearStorage.disabled = true;
    try {
      await api.clearAllData();
      await refresh();
      notify("All saved audio data was cleared.", "success");
    } catch (error) {
      notify(error.message);
    } finally {
      clearStorage.disabled = false;
    }
  });

  return state.subscribe(render);
}
