import test from "node:test";
import assert from "node:assert/strict";
import { HTTPDataSource } from "../src/data-source.js";
test("late requests cannot replace newer workspace", async () => {
  const api = new HTTPDataSource();
  let resolve;
  const first = api.latest(
    "workspace",
    () => new Promise((r) => (resolve = r)),
  );
  const second = await api.latest("workspace", async () => ({ id: "B" }));
  resolve({ id: "A" });
  assert.equal(await first, null);
  assert.equal(second.id, "B");
});
test("query contract and error handling", async () => {
  let url, options;
  const api = new HTTPDataSource(async (u, o) => {
    url = u;
    options = o;
    return { ok: true, json: async () => ({ total: 0, rows: [] }) };
  });
  await api.events("123", { filters: { search: "x" }, limit: 20 });
  assert.equal(url, "/api/traces/123/events");
  assert.equal(JSON.parse(options.body).limit, 20);
  const fail = new HTTPDataSource(async () => ({
    ok: false,
    json: async () => ({ error: { message: "unsupported PSF" } }),
  }));
  await assert.rejects(() => fail.metadata("x"), /unsupported PSF/);
});
