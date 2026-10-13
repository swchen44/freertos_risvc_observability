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
test("PSF view preserves sequence, equal ticks, gaps and independent origin", () => {
  const psf = {
    clock: { origin_ticks: "4294967290" },
    quality: { sequence_gaps: [{ expected: 8, actual: 10 }] },
    events: [
      { sequence: 7, ticks: "0", kind: "task", timestamp_raw: "4294967290" },
      { sequence: 10, ticks: "0", kind: "irq", timestamp_raw: "4294967290" },
      { sequence: 11, ticks: null, kind: "unknown", timestamp_raw: null },
      { sequence: 12, ticks: "12", kind: "task", timestamp_raw: "6" },
    ],
  };
  let chart, table;
  const labels = {};
  const c = vm.createContext({
    manifest: {
      psf,
      identity: { run_id: "toy" },
      profile: {},
      evidence: {},
      parity: {},
    },
    charts: { psf: { setOption: (x) => (chart = x) } },
    psfTable: { replaceData: (x) => (table = x) },
    text: (k, v) => (labels[k] = v),
  });
  vm.runInContext(extract("function plotPSF()", "async function loadRun()"), c);
  c.plotPSF();
  assert.equal(table, psf.events);
  assert.deepEqual(
    Array.from(chart.series[0].data, (x) => x.event.sequence),
    [7, 10, 12],
  );
  assert.match(labels["psf-quality"], /4294967290.*sequence_gaps/);
  assert.match(labels["psf-quality"], /不與 event index 連動/);
});
