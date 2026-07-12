import { createApi } from "./api.js";
import { createDialogs, createNotice, renderStaticIcons } from "./dom.js";
import { setupAudioLibrary } from "./features/audio-library.js";
import { setupEndpointSettings } from "./features/endpoint-settings.js";
import { setupServiceOverview } from "./features/service-overview.js";
import { createState } from "./state.js";
import { startTabs } from "./tabs.js";

const state = createState();
const api = createApi();
const notify = createNotice();
const dialogs = createDialogs();

async function refreshService() {
  try {
    const [health, config, audio] = await Promise.all([
      api.getHealth(),
      api.getConfig(),
      api.getAudio(),
    ]);
    state.set("health", health);
    state.set("config", config);
    state.set("audio", audio);
  } catch (error) {
    notify(error.message);
  }
}

renderStaticIcons();
startTabs();
const library = setupAudioLibrary({
  api,
  state,
  dialogs,
  notify,
  refreshService,
});
setupServiceOverview({
  state,
  api,
  dialogs,
  notify,
  refresh: () => Promise.all([refreshService(), library.loadResponses()]),
});
setupEndpointSettings({ api, notify });

await refreshService();
await library.loadResponses();
window.setInterval(refreshService, 5000);
