const TAB_IDS = ["audio-library", "service", "advanced"];

function selectedFromHash() {
  const tab = window.location.hash.replace("#", "");
  return TAB_IDS.includes(tab) ? tab : "audio-library";
}

export function startTabs() {
  const tabs = [...document.querySelectorAll('[role="tab"]')].map(
    (element) => /** @type {HTMLElement} */ (element),
  );
  const panels = [...document.querySelectorAll('[role="tabpanel"]')].map(
    (element) => /** @type {HTMLElement} */ (element),
  );

  function select(tabName, focus = false) {
    const selected = TAB_IDS.includes(tabName) ? tabName : "audio-library";
    tabs.forEach((tab) => {
      const active = tab.dataset.tab === selected;
      tab.setAttribute("aria-selected", String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    });
    panels.forEach((panel) => {
      panel.hidden = panel.dataset.panel !== selected;
    });
    if (window.location.hash !== `#${selected}`)
      history.replaceState(null, "", `#${selected}`);
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => select(tab.dataset.tab));
    tab.addEventListener("keydown", (event) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key))
        return;
      event.preventDefault();
      const next =
        event.key === "Home"
          ? 0
          : event.key === "End"
            ? tabs.length - 1
            : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) %
              tabs.length;
      select(tabs[next].dataset.tab, true);
    });
  });
  window.addEventListener("hashchange", () => select(selectedFromHash()));
  select(selectedFromHash());
}
