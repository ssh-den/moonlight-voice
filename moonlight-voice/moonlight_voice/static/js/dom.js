export function byId(id) {
  return /** @type {any} */ (document.getElementById(id));
}

const ICON_SHAPES = {
  edit: [
    ["path", { d: "M12 20h9" }],
    ["path", { d: "M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" }],
  ],
  "file-audio": [
    [
      "path",
      { d: "M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8Z" },
    ],
    ["path", { d: "M14 2v6h6" }],
    ["path", { d: "M9 17v-4l5-1v4" }],
    ["circle", { cx: "9", cy: "17", r: "1" }],
    ["circle", { cx: "14", cy: "16", r: "1" }],
  ],
  play: [["path", { d: "m5 3 14 9-14 9Z" }]],
  search: [
    ["circle", { cx: "10.75", cy: "10.75", r: "6.25" }],
    ["path", { d: "m16 16 5 5" }],
  ],
  trash: [
    ["path", { d: "M3 6h18" }],
    ["path", { d: "M8 6V4h8v2" }],
    ["path", { d: "m19 6-1 14H6L5 6" }],
    ["path", { d: "M10 11v6" }],
    ["path", { d: "M14 11v6" }],
  ],
  upload: [
    ["path", { d: "M12 16V4" }],
    ["path", { d: "m7 9 5-5 5 5" }],
    ["path", { d: "M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" }],
  ],
};

let moonStarGradientId = 0;

function addMoonStar(icon) {
  const gradientId = `moon-star-gradient-${(moonStarGradientId += 1)}`;
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
  const gradient = document.createElementNS(
    "http://www.w3.org/2000/svg",
    "linearGradient",
  );
  gradient.setAttribute("id", gradientId);
  gradient.setAttribute("x1", "0");
  gradient.setAttribute("y1", "0");
  gradient.setAttribute("x2", "24");
  gradient.setAttribute("y2", "24");
  [
    ["0%", "#ddd6fe"],
    ["100%", "#8b5cf6"],
  ].forEach(([offset, color]) => {
    const stop = document.createElementNS("http://www.w3.org/2000/svg", "stop");
    stop.setAttribute("offset", offset);
    stop.setAttribute("stop-color", color);
    gradient.append(stop);
  });
  defs.append(gradient);
  icon.append(defs);
  icon.setAttribute("stroke", "none");
  [
    "M14.3 3.1a8.8 8.8 0 1 0 6.6 13.7 7.7 7.7 0 0 1-6.6-13.7Z",
    "m18.4 4.2.8 2.1 2.1.8-2.1.8-.8 2.1-.8-2.1-2.1-.8 2.1-.8.8-2.1Z",
  ].forEach((pathData) => {
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", pathData);
    path.setAttribute("fill", `url(#${gradientId})`);
    icon.append(path);
  });
}

export function createIcon(name) {
  const icon = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  icon.setAttribute("class", `icon icon--${name}`);
  icon.setAttribute("viewBox", "0 0 24 24");
  icon.setAttribute("focusable", "false");
  icon.setAttribute("aria-hidden", "true");
  icon.setAttribute("fill", "none");
  icon.setAttribute("stroke", "currentColor");
  icon.setAttribute("stroke-width", "2");
  icon.setAttribute("stroke-linecap", "round");
  icon.setAttribute("stroke-linejoin", "round");
  if (name === "moon-star") {
    addMoonStar(icon);
    return icon;
  }
  (ICON_SHAPES[name] || []).forEach(([tag, attributes]) => {
    const shape = document.createElementNS("http://www.w3.org/2000/svg", tag);
    Object.entries(attributes).forEach(([attribute, value]) =>
      shape.setAttribute(attribute, value),
    );
    icon.append(shape);
  });
  return icon;
}

export function renderStaticIcons() {
  document.querySelectorAll("[data-icon]").forEach((placeholder) => {
    const iconPlaceholder = /** @type {HTMLElement} */ (placeholder);
    iconPlaceholder.replaceWith(createIcon(iconPlaceholder.dataset.icon));
  });
}

export function setText(element, value) {
  if (element) element.textContent = value ?? "—";
}

export function formatBytes(value) {
  const bytes = Number(value || 0);
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );
  return `${(bytes / 1024 ** index).toFixed(index ? 1 : 0)} ${units[index]}`;
}

export function formatDuration(value) {
  const seconds = Math.max(0, Math.floor(Number(value || 0)));
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const remainder = seconds % 60;
  return hours
    ? `${hours}h ${minutes}m`
    : minutes
      ? `${minutes}m ${remainder}s`
      : `${remainder}s`;
}

export function formatTimestamp(value) {
  const seconds = Number(value);
  return Number.isFinite(seconds)
    ? new Date(seconds * 1000).toLocaleString()
    : "—";
}

export function createNotice() {
  const region = byId("notice-region");
  const dismissAfterMs = 5000;
  return (message, type = "error") => {
    if (!region) return;
    const notice = document.createElement("div");
    notice.className = `notice notice--${type}`;
    notice.setAttribute("role", type === "error" ? "alert" : "status");
    const content = document.createElement("div");
    content.className = "notice__content";
    const text = document.createElement("p");
    text.className = "notice__message";
    text.textContent = message;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "notice__close";
    close.setAttribute("aria-label", "Dismiss notice");
    close.textContent = "×";
    const dismiss = () => notice.remove();
    close.addEventListener("click", dismiss);
    content.append(text);
    notice.append(content, close);
    region.replaceChildren(notice);
    window.setTimeout(dismiss, dismissAfterMs);
  };
}

export function createDialogs() {
  const confirmDialog = byId("confirm-dialog");
  const editDialog = byId("edit-response-dialog");

  function waitForClose(dialog) {
    return new Promise((resolve) =>
      dialog.addEventListener("close", () => resolve(dialog.returnValue), {
        once: true,
      }),
    );
  }

  return {
    async confirm(message, action = "Continue") {
      if (!confirmDialog) return false;
      byId("confirm-message").textContent = message;
      byId("confirm-accept").textContent = action;
      const closed = waitForClose(confirmDialog);
      confirmDialog.showModal();
      return (await closed) === "confirm";
    },
    async editResponse(code) {
      if (!editDialog) return null;
      const input = byId("edit-response-code");
      const fileInput = byId("edit-response-file");
      input.value = code;
      fileInput.value = "";
      fileInput.dispatchEvent(new Event("change"));
      const closed = waitForClose(editDialog);
      editDialog.showModal();
      input.focus();
      if ((await closed) !== "confirm") return null;
      return { code: input.value.trim(), file: fileInput.files?.[0] || null };
    },
  };
}

export function initFilePicker(input) {
  const picker = input?.closest("[data-file-picker]");
  const dropzone = picker?.querySelector(".file-picker__dropzone");
  const name = picker?.querySelector("[data-file-name]");
  if (!picker || !dropzone || !name) return;
  const sync = () => {
    name.textContent = input.files?.[0]?.name || "No file selected";
  };
  input.addEventListener("change", sync);
  ["dragenter", "dragover"].forEach((eventName) =>
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.add("file-picker__dropzone--dragover");
    }),
  );
  ["dragleave", "drop"].forEach((eventName) =>
    dropzone.addEventListener(eventName, (event) => {
      event.preventDefault();
      dropzone.classList.remove("file-picker__dropzone--dragover");
    }),
  );
  dropzone.addEventListener("drop", (event) => {
    const files = event.dataTransfer?.files;
    if (!files?.length) return;
    try {
      input.files = files;
      input.dispatchEvent(new Event("change", { bubbles: true }));
    } catch {
      name.textContent = "Choose this file using the picker";
    }
  });
}

export function playAudio(source) {
  const audio = new Audio(source);
  audio.play().catch(() => {});
  return audio;
}
