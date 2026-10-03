import { queryEvents, queryView, exportCSV } from "./offline-query.js";
export class OfflineDataSource {
  constructor(payload) {
    if (payload.version !== 1)
      throw Error("Unsupported offline report version");
    this.payload = payload;
    this.revisions = new Map();
  }
  get(id) {
    if (id !== this.payload.metadata.trace_id) throw Error("Unknown trace");
    return this.payload;
  }
  async metadata(id) {
    return this.get(id).metadata;
  }
  async traces() {
    return [this.payload.metadata];
  }
  async runs() {
    return [];
  }
  async events(id, q) {
    const p = this.get(id);
    return queryEvents(
      p.trace,
      q.filters,
      q.sort,
      q.offset,
      q.limit,
      p.casefold,
    );
  }
  async view(id, q) {
    const p = this.get(id);
    return queryView(p.trace, p.analysis, q.filters, p.casefold);
  }
  async export(id, q) {
    const p = this.get(id);
    return new Blob(
      [exportCSV(p.trace, p.analysis, q.filters, q.sort, q.kind, p.casefold)],
      { type: "text/csv;charset=utf-8" },
    );
  }
  async latest(key, work) {
    const n = (this.revisions.get(key) || 0) + 1;
    this.revisions.set(key, n);
    try {
      const result = await work();
      return this.revisions.get(key) === n ? result : null;
    } catch (e) {
      if (this.revisions.get(key) === n) throw e;
      return null;
    }
  }
}
