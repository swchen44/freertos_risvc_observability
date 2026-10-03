export class HTTPDataSource {
  constructor(fetcher = globalThis.fetch.bind(globalThis)) {
    this.fetcher = fetcher;
    this.revisions = new Map();
  }
  async request(url, options = {}, blob = false) {
    const r = await this.fetcher(url, options);
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      throw new Error(body.error?.message || `HTTP ${r.status}`);
    }
    return blob ? r.blob() : r.json();
  }
  post(url, body, blob = false) {
    return this.request(
      url,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      },
      blob,
    );
  }
  upload(file) {
    const form = new FormData();
    form.append("file", file);
    return this.request("/api/traces", { method: "POST", body: form });
  }
  metadata(id) {
    return this.request(`/api/traces/${encodeURIComponent(id)}`);
  }
  events(id, query) {
    return this.post(`/api/traces/${encodeURIComponent(id)}/events`, query);
  }
  view(id, query) {
    return this.post(`/api/traces/${encodeURIComponent(id)}/view`, query);
  }
  export(id, query) {
    return this.post(
      `/api/traces/${encodeURIComponent(id)}/export`,
      query,
      true,
    );
  }
  runs() {
    return this.request("/api/runs");
  }
  traces() {
    return this.request("/api/traces");
  }
  compare(query) {
    return this.post("/api/comparisons", query);
  }
  runPSF(id) {
    return this.request(`/api/runs/${encodeURIComponent(id)}/psf`, {}, true);
  }
  async latest(key, work) {
    const revision = (this.revisions.get(key) || 0) + 1;
    this.revisions.set(key, revision);
    try {
      const result = await work();
      return this.revisions.get(key) === revision ? result : null;
    } catch (error) {
      if (this.revisions.get(key) === revision) throw error;
      return null;
    }
  }
}
