// Mirrors the published Python query contract. Keep ticks as BigInt until plotting.
const max = (a, b) => (a > b ? a : b),
  min = (a, b) => (a < b ? a : b);
const fold = (s, map) => [...s].map((c) => map[c] ?? c).join("");
const compareText = (a, b) => {
  const x = [...a],
    y = [...b];
  for (let i = 0; i < Math.min(x.length, y.length); i++) {
    const d = x[i].codePointAt(0) - y[i].codePointAt(0);
    if (d) return Math.sign(d);
  }
  return Math.sign(x.length - y.length);
};
export function validateFilters(f) {
  const keys = [
    "start_ticks",
    "end_ticks",
    "task_ids",
    "object_ids",
    "channels",
    "event_ids",
    "search",
  ];
  if (
    !f ||
    Array.isArray(f) ||
    typeof f !== "object" ||
    Object.keys(f).some((k) => !keys.includes(k))
  )
    throw Error("Invalid filters");
  for (const k of ["start_ticks", "end_ticks"])
    if (k in f && (typeof f[k] !== "string" || !/^\d{1,40}$/.test(f[k])))
      throw Error("Ticks must be unsigned decimal strings");
  if (
    "start_ticks" in f &&
    "end_ticks" in f &&
    BigInt(f.start_ticks) >= BigInt(f.end_ticks)
  )
    throw Error("Time window must have start < end");
  for (const k of ["task_ids", "object_ids", "channels", "event_ids"])
    if (
      k in f &&
      (!Array.isArray(f[k]) ||
        f[k].length > 512 ||
        f[k].some((v) =>
          k === "event_ids" ? !Number.isInteger(v) : typeof v !== "string",
        ))
    )
      throw Error("Invalid selection list");
  if (
    typeof (f.search ?? "") !== "string" ||
    [...(f.search ?? "")].length > 256
  )
    throw Error("Search exceeds 256 characters");
}
export function queryEvents(
  trace,
  filters = {},
  sort = [],
  offset = 0,
  limit = 200,
  casefold = {},
) {
  validateFilters(filters);
  if (
    !Number.isInteger(offset) ||
    offset < 0 ||
    (limit !== null && (!Number.isInteger(limit) || limit < 1 || limit > 2000))
  )
    throw Error("Invalid page bounds");
  if (
    !Array.isArray(sort) ||
    sort.length > 5 ||
    sort.some(
      (s) =>
        !s ||
        Object.keys(s).sort().join(",") !== "direction,field" ||
        !["ticks", "kind", "object_id", "sequence", "offset"].includes(
          s.field,
        ) ||
        !["asc", "desc"].includes(s.direction),
    )
  )
    throw Error("Invalid sort");
  const names = Object.fromEntries(
    (trace.objects ?? []).map((o) => [o.object_id, o.name ?? ""]),
  );
  const search = fold(filters.search ?? "", casefold),
    start =
      filters.start_ticks === undefined ? null : BigInt(filters.start_ticks),
    end = filters.end_ticks === undefined ? null : BigInt(filters.end_ticks);
  const rows = trace.events.filter((e) => {
    const ticks = e.ticks == null ? null : BigInt(e.ticks);
    if (
      (start !== null && (ticks === null || ticks < start)) ||
      (end !== null && (ticks === null || ticks >= end))
    )
      return false;
    for (const [k, v] of [
      ["task_ids", e.actor_id],
      ["object_ids", e.object_id],
      ["channels", e.fields.channel],
      ["event_ids", e.id],
    ])
      if (filters[k]?.length && !filters[k].includes(v)) return false;
    return (
      !search ||
      fold(
        [
          names[e.actor_id] ?? "",
          names[e.object_id] ?? "",
          e.fields.message ?? "",
        ].join(" "),
        casefold,
      ).includes(search)
    );
  });
  rows.sort((a, b) => {
    for (const s of [...sort, { field: "offset", direction: "asc" }]) {
      let x = a[s.field],
        y = b[s.field];
      if (x == null || y == null) {
        if (x !== y) return x == null ? 1 : -1;
        continue;
      }
      if (s.field === "ticks") {
        x = BigInt(x);
        y = BigInt(y);
      }
      if (x !== y) {
        const cmp = typeof x === "string" ? compareText(x, y) : x > y ? 1 : -1;
        return cmp * (s.direction === "asc" ? 1 : -1);
      }
    }
    return 0;
  });
  return {
    total: rows.length,
    rows: rows.slice(offset, limit === null ? undefined : offset + limit),
  };
}
export function metricsFor(intervals, start, end, frequency) {
  let known = 0n;
  const shares = new Map();
  for (const i of intervals) {
    if (i.end_ticks === null) continue;
    const duration = max(
      0n,
      min(end, BigInt(i.end_ticks)) - max(start, BigInt(i.start_ticks)),
    );
    if (i.state === "running" && i.object_id) {
      known += duration;
      shares.set(i.object_id, (shares.get(i.object_id) ?? 0n) + duration);
    }
  }
  const window = max(0n, end - start);
  return {
    start_ticks: String(start),
    end_ticks: String(end),
    window_ticks: String(window),
    window_seconds: frequency ? Number(window) / Number(frequency) : null,
    known_ticks: String(known),
    unknown_ticks: String(window - known),
    task_share: Object.fromEntries(
      [...shares].map(([k, v]) => [
        k,
        {
          running_ticks: String(v),
          fraction: window ? Number(v) / Number(window) : null,
        },
      ]),
    ),
  };
}
function displayLimit(items, total, startKey, endKey) {
  const times = items
    .flatMap((x) => [x[startKey], ...(endKey ? [x[endKey]] : [])])
    .filter((x) => x != null)
    .map(BigInt);
  return {
    shown: items.length,
    total,
    mode: items.length < total ? "first_n" : "all",
    truncated: items.length < total,
    start_ticks: times.length ? String(times.reduce(min)) : null,
    end_ticks: times.length ? String(times.reduce(max)) : null,
  };
}
export function queryView(trace, analysis, filters = {}, casefold = {}) {
  validateFilters(filters);
  const start = BigInt(filters.start_ticks ?? analysis.metrics.start_ticks),
    end = BigInt(filters.end_ticks ?? analysis.metrics.end_ticks);
  if (end < start) throw Error("Window is outside the trace");
  const frequency = BigInt(trace.clock.frequency_hz),
    selected = filters.task_ids ?? [],
    intervals = analysis.intervals;
  const metrics = metricsFor(intervals, start, end, frequency);
  let visible = [];
  for (const i of intervals) {
    if (
      i.end_ticks === null ||
      (selected.length && !selected.includes(i.object_id))
    )
      continue;
    const l = max(start, BigInt(i.start_ticks)),
      r = min(end, BigInt(i.end_ticks));
    if (r > l)
      visible.push({ ...i, start_ticks: String(l), end_ticks: String(r) });
  }
  const aggregation = {
    mode: "intervals",
    raw_intervals: visible.length,
    max_marks: 2000,
  };
  if (visible.length > 2000) {
    const lanes = new Set(visible.map((i) => i.object_id));
    if (lanes.size > 2000) {
      visible = [];
      aggregation.mode = "too_many_lanes";
    } else {
      const bins = BigInt(
          Math.max(1, Math.min(500, Math.floor(2000 / lanes.size))),
        ),
        step = max(1n, (end - start + bins - 1n) / bins),
        groups = new Map();
      for (const i of visible) {
        const slot = min(bins - 1n, (BigInt(i.start_ticks) - start) / step),
          key = JSON.stringify([i.object_id, String(slot)]);
        if (!groups.has(key))
          groups.set(key, {
            object_id: i.object_id,
            start_ticks: String(start + slot * step),
            end_ticks: String(min(end, start + (slot + 1n) * step)),
            state: "density",
            quality: ["aggregated_by_start"],
            count: 0,
          });
        groups.get(key).count++;
      }
      visible = [...groups.values()];
      aggregation.mode = "density_by_interval_start";
      aggregation.bin_ticks = String(step);
    }
  }
  const requests = analysis.requests.filter(
    (r) =>
      BigInt(r.start_ticks) < end &&
      (r.end_ticks === null || BigInt(r.end_ticks) > start) &&
      (!selected.length || selected.includes(r.worker_id)),
  );
  const trend = [];
  if (end > start) {
    const step = max(1n, (end - start + 39n) / 40n);
    for (let l = start; l < end; l += step)
      trend.push(metricsFor(intervals, l, min(l + step, end), frequency));
  }
  const values = requests
    .filter((r) => r.response_ticks !== null)
    .map((r) => BigInt(r.response_ticks));
  const stats = {
    samples: values.length,
    min_ticks: values.length ? String(values.reduce(min)) : null,
    mean_ticks: values.length
      ? Number(values.reduce((a, b) => a + b, 0n)) / values.length
      : null,
    max_ticks: values.length ? String(values.reduce(max)) : null,
  };
  const events = queryEvents(trace, filters, [], 0, null, casefold).rows,
    signals = events
      .filter((e) => "counter" in e.fields)
      .map((e) => ({
        ticks: e.ticks,
        value: e.fields.counter,
        event_id: e.event_id,
      }));
  return {
    intervals: visible,
    metrics,
    trend,
    requests: requests.slice(0, 2000),
    request_total: requests.length,
    request_stats: stats,
    signals: signals.slice(0, 2000),
    signal_total: signals.length,
    display_limits: {
      requests: displayLimit(
        requests.slice(0, 2000),
        requests.length,
        "start_ticks",
        "end_ticks",
      ),
      signals: displayLimit(signals.slice(0, 2000), signals.length, "ticks"),
    },
    quality: analysis.quality,
    aggregation,
    event_total: events.length,
    untimed_events: trace.events.filter((e) => e.ticks == null).length,
    filter_scope:
      "time: all views; task: lanes/requests; object/channel/type/search: events/signals; metrics denominator: full schedule",
  };
}
// Match Python json.dumps separators for list-valued quality cells.
function jsonCell(v) {
  return JSON.stringify(v).replace(
    /,(?=(?:[^"\\]|\\.|"(?:[^"\\]|\\.)*")*$)/g,
    ", ",
  );
}
export function exportCSV(
  trace,
  analysis,
  filters = {},
  sort = [],
  kind = "events",
  casefold = {},
) {
  const common = {
    source_sha256: trace.source.sha256,
    schema_version: trace.schema_version,
    time_unit: "recorder_ticks",
  };
  let fields, rows;
  if (kind === "events") {
    fields = [
      ...Object.keys(common),
      "event_id",
      "offset",
      "ticks",
      "kind",
      "actor_id",
      "object_id",
      "quality",
      "message",
      "spreadsheet_escaped",
    ];
    rows = queryEvents(trace, filters, sort, 0, null, casefold).rows.map(
      (e) => ({
        ...common,
        ...Object.fromEntries(
          ["event_id", "offset", "ticks", "kind", "actor_id", "object_id"].map(
            (k) => [k, e[k]],
          ),
        ),
        quality: jsonCell(e.quality),
        message: e.fields.message ?? "",
      }),
    );
  } else if (kind === "metrics") {
    const m = queryView(trace, analysis, filters, casefold).metrics;
    fields = [
      ...Object.keys(common),
      "start_ticks",
      "end_ticks",
      "window_ticks",
      "known_ticks",
      "unknown_ticks",
      "task_id",
      "running_ticks",
      "fraction",
      "spreadsheet_escaped",
    ];
    const shares = Object.entries(m.task_share);
    rows = (
      shares.length ? shares : [[null, { running_ticks: null, fraction: null }]]
    ).map(([k, v]) => ({
      ...common,
      ...Object.fromEntries(
        [
          "start_ticks",
          "end_ticks",
          "window_ticks",
          "known_ticks",
          "unknown_ticks",
        ].map((k) => [k, m[k]]),
      ),
      task_id: k,
      ...v,
    }));
  } else throw Error("Unsupported CSV kind");
  const quote = (v) => {
    const s = v == null ? "" : String(v);
    return /[",\r\n]/.test(s) ? '"' + s.replaceAll('"', '""') + '"' : s;
  };
  return (
    [
      fields.join(","),
      ...rows.map((row) => {
        let escaped = false;
        for (const [k, v] of Object.entries(row))
          if (typeof v === "string" && /^[=+\-@\t\r]/.test(v)) {
            row[k] = "'" + v;
            escaped = true;
          }
        row.spreadsheet_escaped = String(escaped);
        return fields.map((f) => quote(row[f])).join(",");
      }),
    ].join("\r\n") + "\r\n"
  );
}
