/*
 * Tiny wrapper around fetch() used by every page to talk to the Flask API.
 *  - sends/receives JSON
 *  - includes the session cookie (credentials: "include")
 *  - turns error responses into an ApiError with the server's message
 */
class ApiError extends Error {
  constructor(message, status, fields) {
    super(message);
    this.status = status;
    this.fields = fields || {};
  }
}

const API = (() => {
  const base = ((window.APP_CONFIG && window.APP_CONFIG.API_BASE_URL) || "").replace(/\/+$/, "");

  async function request(method, path, body, { raw = false } = {}) {
    const options = { method, credentials: "include", headers: { Accept: "application/json" } };
    if (body !== undefined) {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }

    let response;
    try {
      response = await fetch(base + path, options);
    } catch (networkError) {
      throw new ApiError("Cannot reach the server. Check your internet connection and try again.", 0);
    }

    if (raw && response.ok) return response;

    let data = null;
    try { data = await response.json(); } catch (_) { /* empty or non-JSON body */ }

    if (!response.ok) {
      const fallback = response.status === 503
        ? "The server is waking up or the database is unavailable. Please retry in a few seconds."
        : `Request failed (HTTP ${response.status}).`;
      throw new ApiError((data && data.error) || fallback, response.status, data && data.fields);
    }
    return data;
  }

  /** Build "?a=1&b=2" from an object, skipping empty values. */
  function query(params) {
    const qs = new URLSearchParams();
    Object.entries(params || {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== "") qs.append(k, v);
    });
    const s = qs.toString();
    return s ? `?${s}` : "";
  }

  return {
    get: (path) => request("GET", path),
    post: (path, body = {}) => request("POST", path, body),
    download: (path) => request("GET", path, undefined, { raw: true }),
    query,
  };
})();
