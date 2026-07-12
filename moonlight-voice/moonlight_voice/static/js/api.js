export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function createApi() {
  const endpoint = (path) => new URL(path, document.baseURI).toString();

  async function request(path, options = {}) {
    let response;
    try {
      response = await fetch(endpoint(path), options);
    } catch {
      throw new ApiError("Unable to reach the Moonlight Voice service.");
    }
    const data = await response.json().catch(() => null);
    if (!response.ok)
      throw new ApiError(
        data?.error || `Request failed (${response.status}).`,
        response.status,
      );
    return data;
  }

  function upload(path, file) {
    return request(path, {
      method: "POST",
      body: file,
      headers: { "Content-Type": file.type || "application/octet-stream" },
    });
  }

  return {
    endpoint,
    getHealth: () => request("health"),
    getConfig: () => request("config"),
    getAudio: () => request("audio"),
    getResponses: (params) => request(`responses?${params.toString()}`),
    uploadDefault: (file) =>
      upload(`audio?filename=${encodeURIComponent(file.name)}`, file),
    deleteDefault: () => request("audio", { method: "DELETE" }),
    uploadResponse: (code, file) =>
      upload(
        `responses?code=${encodeURIComponent(code)}&filename=${encodeURIComponent(file.name)}`,
        file,
      ),
    renameResponse: (code, newCode) =>
      request("responses", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code, new_code: newCode }),
      }),
    deleteResponse: (code, format) => {
      const params = new URLSearchParams({ code });
      if (format) params.set("format", format);
      return request(`responses?${params.toString()}`, { method: "DELETE" });
    },
    deleteResponses: (codes) => {
      const params = new URLSearchParams();
      codes.forEach((code) => params.append("code", code));
      return request(`responses?${params.toString()}`, { method: "DELETE" });
    },
    clearAllData: () => request("storage", { method: "DELETE" }),
    testReadonly: (path) => request(path),
  };
}
