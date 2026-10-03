import "./styles.css";
import { HTTPDataSource } from "./data-source.js";
import { createStore } from "./state.js";
import { mountTimeline, mountMetrics, taskColor } from "./timeline.js";
import { mountEventTable } from "./event-table.js";
import { showDetails } from "./details.js";
import { renderComparison } from "./compare.js";
const $ = (id) => document.getElementById(id);
const api = new HTTPDataSource();
const state = createStore({
  traceId: null,
  filters: {},
  sort: [{ field: "ticks", direction: "asc" }],
  selection: null,
  viewport: null,
  comparison: null,
  offset: 0,
});
let metadata = null,
  fullView = null,
  lastView = null,
  lastPage = null,
  runs = [],
  timeline,
  cpu,
  timing,
  table,
  pinned = false,
  signature = "",
  renderCount = 0;
function status(text, type = "") {
  $("status").textContent = text;
  $("status").className = `status ${type}`;
}
function options(element, values, empty) {
  element.replaceChildren();
  if (empty) {
    const o = new Option(empty, "");
    element.add(o);
  }
  values.forEach(([value, label]) => element.add(new Option(label, value)));
}
function buildFilters() {
  const objects = metadata.objects;
  options(
    $("task-filter"),
    objects
      .filter((o) => o.kind === "task")
      .map((o) => [o.object_id, o.name || o.object_id]),
  );
  options(
    $("object-filter"),
    objects.map((o) => [o.object_id, `${o.name || o.object_id} · ${o.kind}`]),
    "全部物件",
  );
  options(
    $("channel-filter"),
    (
      metadata.channels ||
      objects.filter((o) => o.kind === "channel").map((o) => o.name)
    ).map((n) => [n, n]),
    "全部 channel",
  );
  options(
    $("event-filter"),
    (metadata.event_types || []).map((e) => [
      String(e.id),
      `${e.kind} (0x${e.id.toString(16)})`,
    ]),
    "全部事件",
  );
}
function initViews() {
  if (timeline) return;
  timeline = mountTimeline($("timeline"), setWindow, (interval) => {
    pinned = true;
    showDetails($("details"), interval, "執行區間");
  });
  cpu = mountMetrics($("cpu-chart"), "cpu");
  timing = mountMetrics($("timing-chart"), "timing");
  table = mountEventTable(
    $("event-table"),
    (event) => {
      pinned = true;
      state.setState({ selection: event.event_id });
      showDetails($("details"), event);
    },
    (field) => {
      const s = state.getState();
      const direction =
        s.sort[0]?.field === field && s.sort[0].direction === "asc"
          ? "desc"
          : "asc";
      state.setState({ sort: [{ field, direction }], offset: 0 });
    },
  );
  $("event-table").addEventListener("event-hover", (event) => {
    if (!pinned) showDetails($("details"), event.detail);
  });
}
function draw(view) {
  const decorated = {
    ...view,
    objects: metadata.objects,
    fullStart: fullView.metrics.start_ticks,
    fullEnd: fullView.metrics.end_ticks,
  };
  timeline.render(decorated);
  cpu.render(decorated);
  timing.render(decorated);
}
async function refresh() {
  const s = state.getState();
  if (!s.traceId) return;
  const key = JSON.stringify([s.traceId, s.filters, s.sort, s.offset]);
  if (key === signature) return;
  signature = key;
  status("正在更新時間窗口與事件…");
  const started = performance.now();
  try {
    const result = await api.latest("workspace", async () => {
      const [page, view] = await Promise.all([
        api.events(s.traceId, {
          filters: s.filters,
          sort: s.sort,
          offset: s.offset,
          limit: 20,
        }),
        api.view(s.traceId, { filters: s.filters }),
      ]);
      return { page, view };
    });
    if (!result) return;
    lastView = result.view;
    lastPage = result.page;
    if (!fullView) fullView = result.view;
    $("trace-workspace").hidden = false;
    $("empty-state").hidden = true;
    initViews();
    draw(lastView);
    await table.render(lastPage, metadata.objects);
    const now = state.getState();
    if (
      JSON.stringify([now.traceId, now.filters, now.sort, now.offset]) !== key
    )
      return;
    const m = lastView.metrics;
    $("window-label").textContent =
      `[${m.start_ticks}, ${m.end_ticks}) ticks · ${m.window_seconds === null ? "時間頻率未知" : (m.window_seconds * 1000).toFixed(3) + " ms"}`;
    $("start-filter").value = s.filters.start_ticks || "";
    $("end-filter").value = s.filters.end_ticks || "";
    $("coverage-label").textContent =
      `Known ${m.known_ticks} / ${m.window_ticks} ticks；Unknown ${m.unknown_ticks}`;
    $("aggregation-label").textContent =
      `${lastView.aggregation.mode === "intervals" ? "逐段執行區間" : `聚合：${lastView.aggregation.mode}`} · ${lastView.aggregation.raw_intervals} intervals · ${lastView.untimed_events} 個事件時間未知`;
    const names = new Map(
      metadata.objects.map((o) => [o.object_id, o.name || o.object_id]),
    );
    $("share-values").replaceChildren();
    Object.entries(m.task_share).forEach(([id, v]) => {
      const el = document.createElement("span");
      el.textContent = `${names.get(id) || id} ${v.fraction === null ? "未知" : (v.fraction * 100).toFixed(2) + "%"}`;
      el.style.borderColor = taskColor(id);
      $("share-values").append(el);
    });
    $("timing-title").textContent = lastView.request_total
      ? "Response／execution"
      : "User-event signal";
    $("request-label").textContent = lastView.request_total
      ? `${lastView.request_stats.samples} 個完整 requests；response min／mean／max ${lastView.request_stats.min_ticks}／${lastView.request_stats.mean_ticks?.toFixed(1)}／${lastView.request_stats.max_ticks} ticks`
      : `${lastView.signal_total} 個 Counter samples`;
    $("timing-note").textContent = lastView.request_total
      ? "Response 是開始到完成；execution 僅累加已知 worker 執行區間。"
      : lastView.signal_total
        ? "顯示已解碼的 Counter 數值。"
        : "此 trace 未提供支援的 request／Counter 訊號。";
    $("row-count").textContent =
      `符合 ${lastPage.total} 筆；本頁 ${lastPage.rows.length} 筆。CSV 匯出全部 ${lastPage.total} 筆。`;
    $("page-label").textContent =
      `${Math.floor(s.offset / 20) + 1} / ${Math.max(1, Math.ceil(lastPage.total / 20))}`;
    $("previous").disabled = s.offset === 0;
    $("next").disabled = s.offset + 20 >= lastPage.total;
    $("sort-label").textContent =
      `排序：${s.sort[0].field} ${s.sort[0].direction === "asc" ? "↑" : "↓"}；點欄名切換`;
    const issues = metadata.quality.issues.length;
    status(
      issues
        ? `資料品質：${metadata.quality.status}，${issues} 項問題；查看品質與來源了解限制。`
        : `已更新。窗口與分母一致；capture 完整性：${metadata.quality.capture_complete === true ? "已驗證" : "此上傳檔案未經獨立 oracle 確認"}。`,
      issues ? "warning" : "",
    );
    await new Promise(requestAnimationFrame);
    document.body.dataset.renderRevision = String(++renderCount);
    window.dispatchEvent(
      new CustomEvent("psf-settled", {
        detail: {
          duration_ms: performance.now() - started,
          event_total: lastPage.total,
        },
      }),
    );
  } catch (error) {
    status(error.message, "error");
    signature = "";
  }
}
state.subscribe(refresh);
async function activate(meta) {
  metadata = meta;
  fullView = null;
  lastView = null;
  pinned = false;
  signature = "";
  $("source-name").textContent = meta.source.name;
  $("source-info").textContent =
    `${meta.platform.name} · PSF ${meta.platform.format_version} · ${meta.event_count} events · ${meta.clock.frequency_hz} Hz · ${meta.clock.time_model}`;
  buildFilters();
  $("search-filter").value = "";
  showDetails(
    $("details"),
    {
      source: meta.source,
      platform: meta.platform,
      clock: meta.clock,
      quality: meta.quality,
    },
    "來源與品質",
  );
  state.setState({
    traceId: meta.trace_id,
    filters: {},
    sort: [{ field: "ticks", direction: "asc" }],
    offset: 0,
    selection: null,
  });
  await savedTraces();
}
async function loadSource(work) {
  status("正在解析 PSF…");
  clearTimeout(searchTimer);
  api.latest("workspace", async () => null);
  state.setState({ traceId: null });
  try {
    const meta = await api.latest("load", work);
    if (meta) await activate(meta);
  } catch (error) {
    $("trace-workspace").hidden = true;
    $("empty-state").hidden = false;
    status(error.message, "error");
  }
}
async function loadFile(file) {
  if (file) await loadSource(() => api.upload(file));
}
$("psf-input").addEventListener("change", (event) =>
  loadFile(event.target.files[0]),
);
function applySelections() {
  const f = { ...state.getState().filters };
  f.task_ids = [...$("task-filter").selectedOptions].map((o) => o.value);
  for (const [key, id] of [
    ["object_ids", "object-filter"],
    ["channels", "channel-filter"],
  ])
    f[key] = $(id).value ? [$(id).value] : [];
  f.event_ids = $("event-filter").value
    ? [Number($("event-filter").value)]
    : [];
  f.search = $("search-filter").value;
  state.setState({ filters: f, offset: 0 });
}
for (const id of [
  "task-filter",
  "object-filter",
  "channel-filter",
  "event-filter",
])
  $(id).addEventListener("change", applySelections);
let searchTimer;
$("search-filter").addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(applySelections, 120);
});
function setWindow(start, end) {
  state.setState({
    filters: {
      ...state.getState().filters,
      start_ticks: start,
      end_ticks: end,
    },
    offset: 0,
  });
}
$("apply-window").onclick = () => {
  const f = { ...state.getState().filters };
  for (const [key, id] of [
    ["start_ticks", "start-filter"],
    ["end_ticks", "end-filter"],
  ]) {
    if ($(id).value) f[key] = $(id).value;
    else delete f[key];
  }
  state.setState({ filters: f, offset: 0 });
};
$("reset-window").onclick = () => {
  const f = { ...state.getState().filters };
  delete f.start_ticks;
  delete f.end_ticks;
  state.setState({ filters: f, offset: 0 });
};
$("brush").onclick = () => timeline?.brush();
$("reset").onclick = () => {
  if (!metadata) return;
  clearTimeout(searchTimer);
  buildFilters();
  $("search-filter").value = "";
  state.setState({
    filters: {},
    offset: 0,
    sort: [{ field: "ticks", direction: "asc" }],
  });
};
$("previous").onclick = () =>
  state.setState({ offset: Math.max(0, state.getState().offset - 20) });
$("next").onclick = () =>
  state.setState({ offset: state.getState().offset + 20 });
$("show-quality").onclick = () => {
  if (metadata) {
    pinned = true;
    showDetails($("details"), metadata, "來源、時基與品質");
  }
};
$("unpin").onclick = () => {
  pinned = false;
};
async function download(kind) {
  const s = state.getState();
  if (!s.traceId) return;
  try {
    const blob = await api.export(s.traceId, {
      filters: s.filters,
      sort: s.sort,
      kind,
    });
    const url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    a.download = `psf-${kind}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    status(error.message, "error");
  }
}
$("export-events").onclick = () => download("events");
$("export-metrics").onclick = () => download("metrics");
async function savedTraces() {
  const traces = await api.traces();
  options(
    $("saved-traces"),
    traces.map((t) => [t.trace_id, t.source.name]),
    "已儲存 trace",
  );
  if (metadata) $("saved-traces").value = metadata.trace_id;
}
$("saved-traces").onchange = async () => {
  const id = $("saved-traces").value;
  if (id) await loadSource(() => api.metadata(id));
};
$("load-run").onclick = async () => {
  const id = $("run-select").value;
  if (!id) return;
  await loadSource(async () => {
    const blob = await api.runPSF(id);
    const run = runs.find((r) => r.run_id === id);
    return api.upload(new File([blob], `${run.case_id}.psf`));
  });
};
$("compare-run").onclick = async () => {
  const pair = $("pair-select").value,
    names = {
      logger: ["logger_bad", "logger_fixed"],
      priority: ["inversion", "inheritance"],
      locks: ["deadlock_abba", "ordered_locks"],
    }[pair];
  const selected = names.map((c) => runs.find((r) => r.case_id === c));
  if (selected.some((v) => !v)) {
    status("缺少已驗證的對照案例", "error");
    return;
  }
  try {
    status("正在核對案例比較…");
    const result = await api.latest("comparison", () =>
      api.compare({ pair_id: pair, run_ids: selected.map((r) => r.run_id) }),
    );
    if (!result) return;
    $("comparison-panel").hidden = false;
    renderComparison($("comparison"), result);
    status(`案例比較：${result.verdict}。異常案例的通過表示預期重現異常。`);
  } catch (error) {
    status(error.message, "error");
  }
};
$("close-comparison").onclick = () => ($("comparison-panel").hidden = true);
$("theme-toggle").onclick = () => {
  const dark = document.body.dataset.theme !== "dark";
  document.body.dataset.theme = dark ? "dark" : "light";
  $("theme-toggle").textContent = dark ? "淺色模式" : "深色模式";
  if (lastView) draw(lastView);
};
Promise.all([api.runs(), savedTraces()])
  .then(([value]) => {
    runs = value;
    options(
      $("run-select"),
      runs.map((r) => [r.run_id, `${r.case_id} · ${r.run_id.slice(-6)}`]),
      "已驗證案例",
    );
  })
  .catch((error) => status(error.message, "error"));
