import * as echarts from "echarts";
import { TabulatorFull as Tabulator } from "tabulator-tables";
import "tabulator-tables/dist/css/tabulator.min.css";
import "./event-window.css";
import workerSource from "../dist/assets/event-window-worker.txt";
import {
  functionsCsv,
  number,
  metricValue,
  validateManifest,
  decodeManifest,
  digest,
} from "./event-window-data.js";
const $ = (id) => document.getElementById(id),
  text = (id, v) => ($(id).textContent = v);
const offline = $("event-window-data").textContent.trim()
  ? JSON.parse($("event-window-data").textContent)
  : null;
$("event-window-data").textContent = "";
text("mode", offline ? "離線 HTML · 無網路依賴" : "本機 Web");
const safe = (c) => {
  const e = document.createElement("span");
  e.textContent = String(c.getValue() ?? "—");
  return e;
};
const numeric = (a, b) =>
  number(String(a)) > number(String(b))
    ? 1
    : number(String(a)) < number(String(b))
      ? -1
      : 0;
const table = new Tabulator("#function-table", {
  data: [],
  height: 340,
  layout: "fitDataStretch",
  movableColumns: true,
  columns: [
    ["name", "函式"],
    ["role", "角色"],
    ["value", "選定指標"],
    ["run_denominator", "完整 run 分母"],
    ["filtered_denominator", "篩選分母"],
    ["instructions", "指令"],
    ["memory_cycles", "Memory cycles"],
  ].map(([field, title]) => ({
    field,
    title,
    minWidth: 145,
    formatter: safe,
    sorter: ["name", "role"].includes(field) ? "string" : numeric,
  })),
});
const events = new Tabulator("#event-table", {
  data: [],
  height: 270,
  layout: "fitDataStretch",
  movableColumns: true,
  columns: [
    ["index", "Event index"],
    ["operation", "I/R/W"],
    ["pc", "PC（十進位）"],
    ["name", "函式"],
    ["context", "Context"],
    ["memory_cycles", "Memory cycles"],
  ].map(([field, title]) => ({
    field,
    title,
    minWidth: 130,
    formatter: safe,
    sorter: ["index", "pc", "memory_cycles"].includes(field)
      ? numeric
      : "string",
  })),
});
const psfTable = new Tabulator("#psf-table", {
  data: [],
  height: 230,
  layout: "fitDataStretch",
  columns: [
    ["sequence", "Sequence"],
    ["kind", "事件"],
    ["ticks", "相對 ticks"],
    ["timestamp_raw", "Raw timestamp"],
  ].map(([field, title]) => ({ field, title, formatter: safe, minWidth: 160 })),
});
const charts = Object.fromEntries(
  ["event", "rank", "cost", "psf"].map((k) => [
    k,
    echarts.init($(k + "-chart"), null, { renderer: "svg" }),
  ]),
);
window.addEventListener("resize", () =>
  Object.values(charts).forEach((c) => c.resize()),
);
const tablesReady = Promise.all(
  [table, events, psfTable].map(
    (t) => new Promise((r) => t.on("tableBuilt", r)),
  ),
);
const compressedCache = new Map();
let compressedBytes = 0;
let catalog,
  manifest,
  result,
  worker,
  url,
  request = 0,
  selection = 0,
  currentQuery,
  parts = [],
  nextOffset = null;
window.eventWindowReady = false;
window.eventWindowResult = null;
window.eventWindowTiming = null;
const options = (id, rows) => {
  $(id).replaceChildren(
    ...rows.map(([value, label]) => {
      const o = document.createElement("option");
      o.value = value;
      o.textContent = label;
      return o;
    }),
  );
};
const json = async (path) => {
  const r = await fetch(path);
  if (!r.ok) throw Error(`HTTP ${r.status}`);
  return r.json();
};
function stop() {
  request++;
  selection++;
  if (worker) worker.terminate();
  worker = null;
  if (url) URL.revokeObjectURL(url);
  url = null;
  parts = [];
  window.eventWindowReady = false;
  window.eventWindowTiming = null;
}
function download(blob, name) {
  const u = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = u;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(u), 1000);
}
async function clear() {
  result = null;
  window.eventWindowResult = null;
  nextOffset = null;
  const clearing = Promise.all([table.clearData(), events.clearData()]);
  text("source", "篩選已變更，請重新選取事件。");
  for (const k of ["event", "rank", "cost"]) charts[k].clear();
  for (const id of ["run-cost", "selected-cost", "event-count"]) text(id, "—");
  await clearing;
}
function plotPSF() {
  const p = manifest.psf;
  const usable = p.events.filter((e) => e.ticks != null);
  text(
    "psf-quality",
    `獨立 PSF ticks · origin ${p.clock.origin_ticks} · ${JSON.stringify(p.quality)} · 不與 event index 連動`,
  );
  charts.psf.setOption({
    tooltip: {
      trigger: "item",
      renderMode: "richText",
      formatter: (p) => JSON.stringify(p.data.event),
    },
    grid: { left: 60, right: 25, bottom: 45 },
    xAxis: { type: "value", name: "PSF ticks" },
    yAxis: { type: "category", data: [...new Set(usable.map((e) => e.kind))] },
    series: [
      {
        type: "scatter",
        symbolSize: 7,
        data: usable.map((e) => ({
          value: [Number(e.ticks), e.kind],
          event: e,
        })),
        itemStyle: { color: "#078575" },
      },
    ],
  });
  psfTable.replaceData(p.events);
  text(
    "evidence",
    JSON.stringify(
      {
        identity: manifest.identity,
        profile: manifest.profile,
        evidence: manifest.evidence,
        parity: manifest.parity,
      },
      null,
      2,
    ),
  );
}
async function loadRun() {
  stop();
  const token = selection;
  manifest = null;
  charts.psf.clear();
  psfTable.clearData();
  text("psf-quality", "正在載入 Run；尚無可用時間視圖。");
  text("evidence", "");
  await clear();
  text("status", "驗證 manifest…");
  try {
    const id = $("run").value,
      m = offline
        ? await decodeManifest(
            offline.runs[id].manifest_gzip,
            catalog.runs.find((r) => r.run_id === id).sha256,
          )
        : await json("/api/event-windows/" + id);
    if (token !== selection) return;
    validateManifest(m);
    manifest = m;
    options("context", [
      ["", "全部 Context"],
      ...m.contexts.map((c) => [c, c]),
    ]);
    $("start").value = "0";
    $("end").value = m.events;
    $("function").value = "";
    plotPSF();
    query();
  } catch (e) {
    if (token === selection) text("status", e.message);
  }
}
function chooseWorkload() {
  options(
    "run",
    catalog.runs
      .filter((r) => r.workload === $("workload").value)
      .map((r) => [r.run_id, r.run_id]),
  );
  loadRun();
}
async function query(offset = "0", exportEvents = false) {
  const begun = performance.now();
  let workerTiming;
  if (!manifest) {
    text("status", "請先完成 Run 載入；按分析區間可重新載入。");
    return;
  }
  stop();
  const token = request;
  await clear();
  if (token !== request) return;
  currentQuery = {
    request_id: token,
    run_id: manifest.identity.run_id,
    start: $("start").value,
    end: $("end").value,
    context: $("context").value,
    function_query: $("function").value,
    metric: $("metric").value,
    event_offset: offset,
    event_limit: 200,
    export_events: exportEvents,
    profile: true,
  };
  text("status", "逐塊核對與加總…");
  $("progress").value = 0;
  url = URL.createObjectURL(
    new Blob([workerSource], { type: "text/javascript" }),
  );
  worker = new Worker(url);
  const active = worker;
  active.onmessage = async ({ data }) => {
    if (data.request_id !== request) return;
    if (data.type === "load") {
      try {
        let bytes;
        const cached = compressedCache.get(data.descriptor.gzip_sha256);
        if (cached) {
          bytes = cached.slice();
        } else if (offline) {
          const s = offline.chunk_pool[data.descriptor.gzip_sha256];
          bytes = Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
        } else {
          const response = await fetch(
            `/api/event-windows/${currentQuery.run_id}/chunks/${data.descriptor.id}`,
          );
          if (!response.ok) throw Error(`HTTP ${response.status}`);
          bytes = new Uint8Array(await response.arrayBuffer());
        }
        if (!cached && !offline && token === request) {
          if ((await digest(bytes)) !== data.descriptor.gzip_sha256)
            throw Error("Chunk hash mismatch");
          while (
            compressedBytes + bytes.length > 8 * 1024 * 1024 &&
            compressedCache.size
          ) {
            const key = compressedCache.keys().next().value;
            compressedBytes -= compressedCache.get(key).length;
            compressedCache.delete(key);
          }
          compressedCache.set(data.descriptor.gzip_sha256, bytes.slice());
          compressedBytes += bytes.length;
        }
        if (token === request)
          active.postMessage({ type: "chunk", id: data.id, bytes }, [
            bytes.buffer,
          ]);
      } catch (e) {
        if (token === request)
          active.postMessage({ type: "chunk", id: data.id, error: e.message });
      }
      return;
    }
    if (data.type === "profile") workerTiming = data;
    if (data.type === "progress") {
      text("status", `驗證區塊 ${data.done} / ${data.total}`);
      $("progress").value = data.done / data.total;
    }
    if (data.type === "csv")
      parts.push(new Blob([data.text], { type: "text/csv;charset=utf-8" }));
    if (data.type === "error") {
      text("status", "分析失敗：" + data.error);
      active.terminate();
      if (url) URL.revokeObjectURL(url);
      parts = [];
      return;
    }
    if (data.type === "result") {
      result = data.result;
      window.eventWindowResult = result;
      const renderStart = performance.now();
      await render(data.result, token);
      if (token !== request) return;
      window.eventWindowTiming = {
        request_id: token,
        worker: workerTiming,
        render_ms: performance.now() - renderStart,
        query_ms: performance.now() - begun,
        navigation_elapsed_ms: performance.now(),
      };
      if (exportEvents)
        download(
          new Blob(parts, { type: "text/csv;charset=utf-8" }),
          `${currentQuery.run_id}-events.csv`,
        );
      parts = [];
      text(
        "status",
        `${result.run_id} · [${result.start}, ${result.end}) · ${result.event_count} 筆事件`,
      );
      window.eventWindowReady = true;
      active.terminate();
      if (url) URL.revokeObjectURL(url);
      worker = null;
      url = null;
    }
  };
  active.onerror = (e) => {
    if (token === request) {
      text("status", "Worker 錯誤：" + e.message);
      stop();
    }
  };
  active.postMessage({ type: "query", manifest, query: currentQuery });
}
async function render(r, token) {
  if (token !== request) return;
  nextOffset = r.next_event_offset;
  await table.replaceData(r.function_rows);
  if (token !== request) return;
  await events.replaceData(r.event_page);
  if (token !== request) return;
  text("run-cost", metricValue(r.run_totals, r.metric));
  text("selected-cost", metricValue(r.totals, r.metric));
  text("event-count", r.event_count);
  $("next-page").disabled = nextOffset === null;
  const tip = {
    trigger: "item",
    renderMode: "richText",
    formatter: (p) => p.data.label,
  };
  charts.event.setOption(
    {
      animation: false,
      tooltip: tip,
      grid: { left: 75, right: 25, bottom: 75 },
      xAxis: {
        type: "value",
        min: Number(r.start),
        max: Number(r.end),
        name: "event index",
      },
      yAxis: {
        type: "value",
        name: r.metric,
        axisLabel: {
          formatter: (v) =>
            Intl.NumberFormat("en", { notation: "compact" }).format(v),
        },
      },
      dataZoom: [
        {
          type: "slider",
          xAxisIndex: 0,
          filterMode: "none",
          start: 0,
          end: 100,
        },
        { type: "inside", xAxisIndex: 0, filterMode: "none" },
      ],
      series: [
        {
          type: "bar",
          data: r.bins.map((b) => ({
            value: [(Number(b.start) + Number(b.end)) / 2, Number(b.value)],
            label: `[${b.start}, ${b.end})\n${b.value} ${r.metric}\n${b.rows} selected rows`,
          })),
          itemStyle: { color: "#336e86" },
        },
      ],
    },
    { notMerge: true, silent: true },
  );
  const rank = r.function_rows
    .slice(0, 20)
    .map((g) => ({ name: g.name, value: g.value }));
  if (r.function_rows.length > 20)
    rank.push({
      name: "Other",
      value: r.function_rows
        .slice(20)
        .reduce((n, g) => n + number(g.value), 0n)
        .toString(),
    });
  bar(charts.rank, rank, r.metric);
  bar(
    charts.cost,
    Object.entries(r.totals.cost_cycles).map(([name, value]) => ({
      name,
      value,
    })),
    "cycles",
  );
}
function bar(chart, rows, unit) {
  chart.setOption(
    {
      animation: false,
      tooltip: {
        trigger: "item",
        renderMode: "richText",
        formatter: (p) => `${p.name}\n${p.data.exact} ${unit}`,
      },
      grid: { left: 140, right: 30, top: 25, bottom: 35 },
      xAxis: {
        type: "value",
        axisLabel: {
          formatter: (v) =>
            Intl.NumberFormat("en", { notation: "compact" }).format(v),
        },
      },
      yAxis: {
        type: "category",
        inverse: true,
        data: rows.map((r) => r.name),
        axisLabel: { width: 120, overflow: "truncate" },
      },
      series: [
        {
          type: "bar",
          data: rows.map((r) => ({ value: Number(r.value), exact: r.value })),
          itemStyle: { color: "#078575" },
        },
      ],
    },
    { notMerge: true },
  );
}
charts.event.on("datazoom", (ev) => {
  if (!result) return;
  const z = ev.batch?.[0] ?? ev;
  const s = Number(result.start),
    width = Number(result.end) - s;
  const a = Math.floor(s + (width * (z.start ?? 0)) / 100),
    b = Math.ceil(s + (width * (z.end ?? 100)) / 100);
  $("start").value = String(a);
  $("end").value = String(b);
  query();
});
events.on("rowClick", (_, row) => {
  const e = row.getData(),
    hex = "0x" + BigInt(e.pc).toString(16);
  text(
    "source",
    JSON.stringify(
      {
        event: e.index,
        pc: hex,
        elf: manifest.evidence.elf_sha256,
        source:
          manifest.source_lines[e.pc] ??
          manifest.source_lines[hex] ??
          "unresolved",
      },
      null,
      2,
    ),
  );
});
$("apply").onclick = () => (manifest ? query() : loadRun());
$("cancel").onclick = () => {
  stop();
  clear();
  text("status", "已取消；可重新分析。");
};
$("reset").onclick = () => {
  if (!manifest) {
    loadRun();
    return;
  }
  $("start").value = "0";
  $("end").value = manifest.events;
  query();
};
$("workload").onchange = chooseWorkload;
$("run").onchange = loadRun;
for (const id of ["context", "metric"]) $(id).onchange = () => query();
$("function").onchange = () => query();
$("next-page").onclick = () => {
  if (nextOffset) query(nextOffset);
};
$("functions-csv").onclick = () => {
  if (result)
    download(
      new Blob([functionsCsv(table.getData("active"))], {
        type: "text/csv;charset=utf-8",
      }),
      result.run_id + "-functions.csv",
    );
};
$("events-csv").onclick = () => query("0", true);
window.addEventListener("pagehide", stop);
(async () => {
  await tablesReady;
  if (!window.Worker || !window.DecompressionStream)
    throw Error("瀏覽器需支援 Worker 與 DecompressionStream");
  catalog = offline ? offline.catalog : await json("/api/event-windows");
  options(
    "workload",
    [...new Set(catalog.runs.map((r) => r.workload))].map((w) => [w, w]),
  );
  chooseWorkload();
})().catch((e) => text("status", "載入失敗：" + e.message));
