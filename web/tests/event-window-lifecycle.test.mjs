import test from "node:test";
import assert from "node:assert/strict";
import vm from "node:vm";
import { readFileSync } from "node:fs";
const source = readFileSync(
  new URL("../src/event-window.js", import.meta.url),
  "utf8",
);
function extract(a, b) {
  return source.slice(source.indexOf(a), source.indexOf(b));
}
test("cancel invalidates manifest loader and cannot start an old query", async () => {
  let resolveLoad;
  const queried = [];
  const controls = { run: { value: "B" }, start: {}, end: {}, function: {} };
  const c = vm.createContext({
    selection: 0,
    request: 0,
    worker: null,
    url: null,
    parts: [],
    manifest: null,
    charts: { psf: { clear() {} } },
    psfTable: { clearData() {} },
    window: {},
    offline: null,
    $: (id) => controls[id],
    clear: async () => {},
    text: () => {},
    json: () => new Promise((r) => (resolveLoad = r)),
    validateManifest: () => {},
    options: () => {},
    plotPSF: () => {},
    query: () => queried.push(c.manifest.identity.run_id),
    URL: { revokeObjectURL() {} },
    console,
  });
  vm.runInContext(
    extract("function stop()", "function download(") +
      extract("async function loadRun()", "function chooseWorkload()"),
    c,
  );
  const loading = c.loadRun();
  await new Promise(setImmediate);
  c.stop();
  resolveLoad({
    identity: { run_id: "B" },
    contexts: ["unknown"],
    events: "1",
  });
  await loading;
  assert.deepEqual(queried, []);
});
test("cancelled render cannot write counters or charts after table await", async () => {
  let resolveTable;
  const writes = [];
  const r = {
    function_rows: [],
    event_page: [],
    next_event_offset: null,
    metric: "memory_cycles",
    totals: { memory_cycles: "1", cost_cycles: {} },
    run_totals: { memory_cycles: "1", cost_cycles: {} },
    event_count: "1",
    start: "0",
    end: "1",
    bins: [],
  };
  const c = vm.createContext({
    request: 1,
    result: r,
    nextOffset: null,
    table: {
      replaceData: () => new Promise((resolve) => (resolveTable = resolve)),
    },
    events: { replaceData: async () => {} },
    text: (...x) => writes.push(x),
    metricValue: (v, k) => v[k],
    charts: { event: { setOption: () => writes.push("chart") } },
    $: () => ({}),
    bar: () => {},
    Intl,
  });
  vm.runInContext(extract("async function render(", "function bar("), c);
  const rendering = c.render(r, 1);
  await new Promise(setImmediate);
  c.request = 2;
  c.result = null;
  resolveTable();
  await rendering;
  assert.deepEqual(writes, []);
});
