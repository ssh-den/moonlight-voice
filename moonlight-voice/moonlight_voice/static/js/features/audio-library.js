import {
  byId,
  createIcon,
  formatBytes,
  formatTimestamp,
  initFilePicker,
  playAudio,
} from "../dom.js";

export function setupAudioLibrary({
  api,
  state,
  dialogs,
  notify,
  refreshService,
}) {
  const ui = {
    defaultForm: byId("default-upload-form"),
    defaultFile: byId("default-file"),
    defaultUpload: byId("default-upload"),
    defaultUploadLabel: document.querySelector("[data-default-upload-label]"),
    defaultPlay: byId("default-play"),
    defaultDelete: byId("default-delete"),
    responseForm: byId("response-upload-form"),
    responseCode: byId("response-code"),
    responseFile: byId("response-file"),
    responseUpload: byId("response-upload"),
    responseUploadLabel: document.querySelector("[data-response-upload-label]"),
    search: byId("responses-search"),
    table: byId("responses-table-body"),
    tableHead: byId("responses-table-head"),
    selectAll: byId("responses-select-all"),
    bulkDelete: byId("responses-delete-selected"),
    selectionStatus: byId("responses-selection-status"),
    prev: byId("responses-prev"),
    next: byId("responses-next"),
    page: byId("responses-page-info"),
    pageSize: byId("responses-page-size"),
  };
  const model = {
    page: 1,
    pageSize: Number(ui.pageSize?.value || 10),
    search: "",
    sortBy: "code",
    sortDir: "asc",
    total: 0,
    preview: null,
    busy: false,
    codes: new Set(),
    pageCodes: [],
    selected: new Set(),
  };

  function setBusy(busy) {
    model.busy = busy;
    ui.table?.setAttribute("aria-busy", String(busy));
    ui.defaultUpload.disabled = busy;
    ui.responseUpload.disabled = busy;
    renderDefaultControls();
    renderSelectionStatus();
  }
  function renderDefaultControls() {
    const hasAudio = Object.keys(state.get("audio")?.files || {}).length > 0;
    ui.defaultUploadLabel.textContent = hasAudio
      ? "Replace default"
      : "Upload default";
    ui.defaultPlay.disabled = model.busy || !hasAudio;
    ui.defaultDelete.disabled = model.busy || !hasAudio;
  }
  function updateResponseUploadLabel() {
    ui.responseUploadLabel.textContent = model.codes.has(
      ui.responseCode.value.trim(),
    )
      ? "Replace response"
      : "Upload response";
  }
  function play(source) {
    model.preview?.pause();
    model.preview = playAudio(source);
  }
  function renderSortIndicators() {
    ui.tableHead
      ?.querySelectorAll("[data-sort-indicator]")
      .forEach((indicator) => {
        indicator.textContent =
          indicator.dataset.sortIndicator === model.sortBy
            ? model.sortDir === "asc"
              ? "↑"
              : "↓"
            : "↕";
      });
  }
  function button(label, action, code, iconName) {
    const element = document.createElement("button");
    element.type = "button";
    element.className = "button button--secondary button--small";
    element.append(createIcon(iconName), document.createTextNode(label));
    element.dataset.action = action;
    element.dataset.code = code;
    return element;
  }
  function renderSelectionStatus() {
    const selectedCount = model.selected.size;
    if (ui.selectionStatus)
      ui.selectionStatus.textContent = selectedCount
        ? `${selectedCount} selected`
        : "Select responses to delete.";
    if (ui.bulkDelete) ui.bulkDelete.disabled = model.busy || !selectedCount;
    if (!ui.selectAll) return;
    const selectedOnPage = model.pageCodes.filter((code) =>
      model.selected.has(code),
    ).length;
    ui.selectAll.checked =
      Boolean(model.pageCodes.length) &&
      selectedOnPage === model.pageCodes.length;
    ui.selectAll.indeterminate =
      selectedOnPage > 0 && selectedOnPage < model.pageCodes.length;
    ui.selectAll.disabled = model.busy || !model.pageCodes.length;
  }
  function render(data) {
    ui.table.replaceChildren();
    const items = data?.items || [];
    if (!items.length) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = 6;
      cell.className = "muted";
      cell.textContent = "No response clips found.";
      row.append(cell);
      ui.table.append(row);
    }
    items.forEach((item) => {
      const row = document.createElement("tr");
      const selection = document.createElement("td");
      selection.className = "table-select";
      const checkbox = document.createElement("input");
      checkbox.type = "checkbox";
      checkbox.checked = model.selected.has(item.code);
      checkbox.dataset.selectResponse = item.code;
      checkbox.setAttribute("aria-label", `Select ${item.code}`);
      selection.append(checkbox);
      const code = document.createElement("td");
      code.textContent = item.code;
      const updated = document.createElement("td");
      updated.textContent = formatTimestamp(item.updated_at);
      const formats = document.createElement("td");
      const formatList = document.createElement("div");
      formatList.className = "format-list";
      Object.keys(item.formats || {}).forEach((format) => {
        const group = document.createElement("span");
        group.className = "format-list__item";
        group.textContent = format.toUpperCase();
        formatList.append(group);
      });
      if (!formatList.children.length)
        formatList.textContent = "No audio uploaded";
      formats.append(formatList);
      const size = document.createElement("td");
      size.textContent = formatBytes(
        Object.values(item.formats || {}).reduce(
          (total, details) => total + Number(details.size || 0),
          0,
        ),
      );
      const actions = document.createElement("td");
      const actionRow = document.createElement("div");
      actionRow.className = "action-row";
      actionRow.append(button("Edit", "edit", item.code, "edit"));
      actions.append(actionRow);
      row.append(selection, code, updated, formats, size, actions);
      ui.table.append(row);
    });
    model.total = Number(data?.total || 0);
    model.codes = new Set(items.map((item) => item.code));
    model.pageCodes = items.map((item) => item.code);
    const pages = Math.max(1, Math.ceil(model.total / model.pageSize));
    ui.page.textContent = `Page ${model.page} of ${pages} · ${model.total} total`;
    ui.prev.disabled = model.page <= 1;
    ui.next.disabled = model.page >= pages;
    renderSortIndicators();
    updateResponseUploadLabel();
    renderSelectionStatus();
  }
  async function loadResponses() {
    const params = new URLSearchParams({
      page: String(model.page),
      page_size: String(model.pageSize),
      sort_by: model.sortBy,
      sort_dir: model.sortDir,
    });
    if (model.search) params.set("search", model.search);
    setBusy(true);
    try {
      const data = await api.getResponses(params);
      state.set("responses", data);
      render(data);
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function uploadDefault(event) {
    event.preventDefault();
    const file = ui.defaultFile.files?.[0];
    if (!file) return notify("Choose an MP3 or WAV file first.", "warning");
    setBusy(true);
    try {
      await api.uploadDefault(file);
      ui.defaultForm.reset();
      await refreshService();
      notify("Default audio updated.", "success");
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function deleteDefault() {
    if (
      !(await dialogs.confirm(
        "Delete all default audio formats? This cannot be undone.",
        "Delete default",
      ))
    )
      return;
    setBusy(true);
    try {
      await api.deleteDefault();
      await refreshService();
      notify("Default audio deleted.", "success");
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function uploadResponse(event) {
    event.preventDefault();
    const code = ui.responseCode.value.trim();
    const file = ui.responseFile.files?.[0];
    if (!code || !file)
      return notify(
        "Enter a response code and choose an MP3 or WAV file.",
        "warning",
      );
    setBusy(true);
    try {
      await api.uploadResponse(code, file);
      ui.responseForm.reset();
      model.page = 1;
      await Promise.all([loadResponses(), refreshService()]);
      notify("Response clip uploaded.", "success");
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function deleteSelected() {
    const codes = [...model.selected];
    if (!codes.length) return;
    if (
      !(await dialogs.confirm(
        `Delete ${codes.length} selected response${codes.length === 1 ? "" : "s"}? This cannot be undone.`,
        "Delete selected",
      ))
    )
      return;
    setBusy(true);
    try {
      const result = await api.deleteResponses(codes);
      model.selected.clear();
      model.page = 1;
      await Promise.all([loadResponses(), refreshService()]);
      const deleted = Number(result.deleted);
      notify(
        `${deleted} response${deleted === 1 ? "" : "s"} deleted.`,
        "success",
      );
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }
  async function act(event) {
    const target = /** @type {HTMLButtonElement | null} */ (
      /** @type {HTMLElement} */ (event.target).closest("button[data-action]")
    );
    if (!target) return;
    const { action, code } = target.dataset;
    if (action !== "edit") return;
    const changes = await dialogs.editResponse(code);
    if (!changes || !changes.code) return;
    if (changes.code === code && !changes.file)
      return notify(
        "Change the code or choose a replacement audio file.",
        "warning",
      );
    setBusy(true);
    try {
      if (changes.code !== code) await api.renameResponse(code, changes.code);
      if (changes.file) await api.uploadResponse(changes.code, changes.file);
      await Promise.all([loadResponses(), refreshService()]);
      notify("Response updated.", "success");
    } catch (error) {
      notify(error.message);
    } finally {
      setBusy(false);
    }
  }
  ui.defaultForm?.addEventListener("submit", uploadDefault);
  ui.defaultPlay?.addEventListener("click", () =>
    play(
      api.endpoint(
        `audio/file?format=${encodeURIComponent(state.get("config")?.output_format || "mp3")}`,
      ),
    ),
  );
  ui.defaultDelete?.addEventListener("click", deleteDefault);
  ui.responseForm?.addEventListener("submit", uploadResponse);
  ui.table?.addEventListener("click", act);
  ui.table?.addEventListener("change", (event) => {
    const checkbox = /** @type {HTMLInputElement | null} */ (
      /** @type {HTMLElement} */ (event.target).closest(
        "[data-select-response]",
      )
    );
    if (!checkbox) return;
    if (checkbox.checked) model.selected.add(checkbox.dataset.selectResponse);
    else model.selected.delete(checkbox.dataset.selectResponse);
    renderSelectionStatus();
  });
  ui.selectAll?.addEventListener("change", (event) => {
    const checkbox = /** @type {HTMLInputElement} */ (event.target);
    model.pageCodes.forEach((code) => {
      if (checkbox.checked) model.selected.add(code);
      else model.selected.delete(code);
    });
    render(state.get("responses"));
  });
  ui.bulkDelete?.addEventListener("click", deleteSelected);
  ui.search?.addEventListener("input", (event) => {
    model.search = /** @type {HTMLInputElement} */ (event.target).value.trim();
    model.page = 1;
    model.selected.clear();
    loadResponses();
  });
  ui.responseCode?.addEventListener("input", updateResponseUploadLabel);
  ui.prev?.addEventListener("click", () => {
    model.page -= 1;
    loadResponses();
  });
  ui.next?.addEventListener("click", () => {
    model.page += 1;
    loadResponses();
  });
  ui.pageSize?.addEventListener("change", (event) => {
    model.pageSize =
      Number(/** @type {HTMLSelectElement} */ (event.target).value) || 10;
    model.page = 1;
    loadResponses();
  });
  ui.tableHead?.addEventListener("click", (event) => {
    const header = /** @type {HTMLElement | null} */ (
      /** @type {HTMLElement} */ (event.target).closest("[data-sort]")
    );
    if (!header) return;
    const sortBy = header.dataset.sort;
    model.sortDir =
      model.sortBy === sortBy && model.sortDir === "asc" ? "desc" : "asc";
    model.sortBy = sortBy;
    model.page = 1;
    loadResponses();
  });
  initFilePicker(ui.defaultFile);
  initFilePicker(ui.responseFile);
  initFilePicker(byId("edit-response-file"));
  state.subscribe((event) => {
    if (event.detail.key === "audio") renderDefaultControls();
  });
  renderDefaultControls();
  return { loadResponses };
}
