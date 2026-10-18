export const COSTS = ["l1i", "l1d", "l2", "ram_read", "ram_write"];
export const LEVELS = ["l1i", "l1d", "l2"];
export const COUNTERS = [
  "accesses",
  "misses",
  "compulsory",
  "conflict",
  "capacity",
];
export const COLUMNS = [
  "index",
  "pc",
  "address",
  "size",
  "operation",
  "context_id",
  "owner_id",
  ...COSTS,
  ...LEVELS.flatMap((l) => COUNTERS.map((k) => `${l}.${k}`)),
];
export function number(s) {
  if (typeof s !== "string" || !/^(0|[1-9][0-9]{0,39})$/.test(s))
    throw Error("Invalid unsigned integer");
  return BigInt(s);
}
const stringify = (o) =>
  Object.fromEntries(
    Object.entries(o).map(([k, v]) => [
      k,
      typeof v === "bigint" ? v.toString() : stringify(v),
    ]),
  );
const empty = () => ({
  instructions: 0n,
  memory_cycles: 0n,
  model_service_ns: 0n,
  accounted_model_ns: 0n,
  cost_cycles: { l1i: 0n, l1d: 0n, l2: 0n, ram_read: 0n, ram_write: 0n },
  cache: {
    l1i: {
      accesses: 0n,
      misses: 0n,
      compulsory: 0n,
      conflict: 0n,
      capacity: 0n,
    },
    l1d: {
      accesses: 0n,
      misses: 0n,
      compulsory: 0n,
      conflict: 0n,
      capacity: 0n,
    },
    l2: {
      accesses: 0n,
      misses: 0n,
      compulsory: 0n,
      conflict: 0n,
      capacity: 0n,
    },
  },
});
function add(a, b) {
  a.instructions += b.instructions;
  a.memory_cycles += b.memory_cycles;
  a.model_service_ns += b.model_service_ns;
  a.accounted_model_ns += b.accounted_model_ns;
  for (const k of COSTS) a.cost_cycles[k] += b.cost_cycles[k];
  for (const l of LEVELS)
    for (const k of COUNTERS) a.cache[l][k] += b.cache[l][k];
  return a;
}
function counts(r) {
  if (!Array.isArray(r) || r.length !== 27 || !["I", "R", "W"].includes(r[4]))
    throw Error("Invalid event row");
  const n = r.map((x, i) => (i === 4 ? x : number(x)));
  if (
    n[3] === 0n ||
    (n[4] === "I" && (n[1] !== n[2] || ![2n, 4n].includes(n[3])))
  )
    throw Error("Invalid access mapping");
  const out = empty();
  out.instructions = r[4] === "I" ? 1n : 0n;
  COSTS.forEach((k, i) => (out.cost_cycles[k] = n[7 + i]));
  out.memory_cycles = n.slice(7, 12).reduce((a, b) => a + b, 0n);
  out.model_service_ns = 2n * out.memory_cycles;
  out.accounted_model_ns = out.model_service_ns + out.instructions;
  LEVELS.forEach((l, i) => {
    COUNTERS.forEach((k, j) => (out.cache[l][k] = n[12 + i * 5 + j]));
    const c = out.cache[l];
    if (
      c.misses !== c.compulsory + c.conflict + c.capacity ||
      c.misses > c.accesses
    )
      throw Error("Cache conservation failure");
  });
  return out;
}
export const sumRows = (rows) =>
  stringify(rows.reduce((a, r) => add(a, counts(r)), empty()));
export const metricValue = (c, k) =>
  k.includes(".") ? c.cache[k.split(".")[0]]?.[k.split(".")[1]] : c[k];
const equal = (a, b) => {
  if (typeof a !== typeof b) return false;
  if (a === null || b === null || typeof a !== "object") return a === b;
  const keys = Object.keys(a);
  return (
    keys.length === Object.keys(b).length &&
    keys.every((k) => Object.hasOwn(b, k) && equal(a[k], b[k]))
  );
};
export async function digest(data) {
  return [...new Uint8Array(await crypto.subtle.digest("SHA-256", data))]
    .map((x) => x.toString(16).padStart(2, "0"))
    .join("");
}
export function validateManifest(m) {
  if (
    !m ||
    m.schema !== "event-window-run-v1" ||
    !equal(m.columns, COLUMNS) ||
    !Array.isArray(m.contexts) ||
    !m.contexts.length ||
    m.contexts.some((c) => typeof c !== "string" || !c) ||
    new Set(m.contexts).size !== m.contexts.length ||
    !Array.isArray(m.owners) ||
    !m.owners.length ||
    m.owners.some(
      (o) =>
        !o ||
        typeof o.function_id !== "string" ||
        !o.function_id ||
        typeof o.role !== "string" ||
        (o.function != null && typeof o.function !== "string"),
    ) ||
    new Set(m.owners.map((o) => o.function_id)).size !== m.owners.length ||
    !Array.isArray(m.chunks)
  )
    throw Error("Invalid manifest");
  let end = 0n;
  const sum = empty();
  m.chunks.forEach((c, i) => {
    const next = number(c.end);
    if (
      c.id !== String(i).padStart(6, "0") ||
      number(c.start) !== end ||
      next <= end ||
      next - end > 1024n ||
      number(c.rows) !== next - end ||
      number(c.uncompressed_bytes) > 2097152n ||
      number(c.compressed_bytes) > 2097152n
    )
      throw Error("Chunk range/size mismatch");
    for (const k of ["gzip_sha256", "json_sha256"])
      if (!/^[a-f0-9]{64}$/.test(c[k])) throw Error("Invalid digest");
    const parse = (dst, src) => {
      for (const k of Object.keys(dst))
        dst[k] =
          typeof dst[k] === "bigint" ? number(src[k]) : parse(dst[k], src[k]);
      return dst;
    };
    add(sum, parse(empty(), c.totals));
    end = next;
  });
  if (
    end === 0n ||
    end !== number(m.events) ||
    !equal(stringify(sum), m.totals)
  )
    throw Error("Incomplete manifest");
}
export async function decodeChunk(bytes, c, m) {
  if (
    BigInt(bytes.byteLength) !== number(c.compressed_bytes) ||
    (await digest(bytes)) !== c.gzip_sha256
  )
    throw Error("Compressed hash mismatch");
  const reader = new Blob([bytes])
    .stream()
    .pipeThrough(new DecompressionStream("gzip"))
    .getReader();
  let size = 0;
  const parts = [];
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.length;
      if (size > 2097152) throw Error("Decompression limit");
      parts.push(value);
    }
  } finally {
    await reader.cancel();
  }
  const raw = new Uint8Array(size);
  let p = 0;
  for (const a of parts) {
    raw.set(a, p);
    p += a.length;
  }
  if (
    BigInt(size) !== number(c.uncompressed_bytes) ||
    (await digest(raw)) !== c.json_sha256
  )
    throw Error("JSON hash mismatch");
  const data = JSON.parse(
    new TextDecoder("utf-8", { fatal: true }).decode(raw),
  );
  if (
    data.schema !== "event-window-chunk-v1" ||
    !equal(data.columns, COLUMNS) ||
    data.start !== c.start ||
    data.end !== c.end ||
    BigInt(data.rows.length) !== number(c.rows)
  )
    throw Error("Chunk schema mismatch");
  data.rows.forEach((r, i) => {
    if (
      number(r[0]) !== number(c.start) + BigInt(i) ||
      number(r[5]) >= BigInt(m.contexts.length) ||
      number(r[6]) >= BigInt(m.owners.length)
    )
      throw Error("Invalid event identity");
  });
  const verified = data.rows.map(counts);
  const total = verified.reduce((a, item) => add(a, item), empty());
  if (!equal(stringify(total), c.totals)) throw Error("Chunk totals mismatch");
  Object.defineProperty(data.rows, "counts", { value: verified });
  return data.rows;
}
const cell = (v) =>
  '"' +
  String(v ?? "")
    .replace(/^[=+@\-\t\r\n]/, "'$&")
    .replaceAll('"', '""') +
  '"';
export const csvLine = (items) => items.map(cell).join(",") + "\r\n";
export function functionsCsv(rows) {
  const keys = [
    "name",
    "role",
    "value",
    "run_denominator",
    "filtered_denominator",
    "instructions",
    "memory_cycles",
  ];
  return (
    csvLine(keys) + rows.map((r) => csvLine(keys.map((k) => r[k]))).join("")
  );
}
export async function queryEventWindow(m, loadChunk, q, emit = () => {}) {
  const begun = performance.now();
  let loadMs = 0,
    decodeMs = 0,
    aggregateMs = 0;
  validateManifest(m);
  const start = number(q.start),
    end = number(q.end),
    offset = number(q.event_offset ?? "0"),
    limit = q.event_limit ?? 200;
  if (
    start > end ||
    end > number(m.events) ||
    !Number.isInteger(limit) ||
    limit < 1 ||
    limit > 200 ||
    q.run_id !== m.identity.run_id
  )
    throw Error("Invalid interval query");
  const metric = q.metric ?? "memory_cycles";
  if (
    ![
      "instructions",
      "memory_cycles",
      "model_service_ns",
      "accounted_model_ns",
      ...LEVELS.flatMap((l) => COUNTERS.map((k) => `${l}.${k}`)),
    ].includes(metric)
  )
    throw Error("Unknown metric");
  const total = empty(),
    groups = new Map(),
    bins = [],
    page = [];
  let count = 0n,
    visited = 0,
    binIndex = 0;
  const search = q.function_query?.toLowerCase();
  const contextMatches = m.contexts.map((c) => !q.context || q.context === c);
  const ownerMatches = m.owners.map(
    (o) =>
      !search || (o.function ?? "unresolved").toLowerCase().includes(search),
  );
  const width = end - start,
    binCount = Number(width < 512n ? width : 512n);
  for (let i = 0; i < binCount; i++)
    bins.push({
      start: (start + (width * BigInt(i)) / BigInt(binCount)).toString(),
      end: (start + (width * BigInt(i + 1)) / BigInt(binCount)).toString(),
      value: 0n,
      rows: 0n,
    });
  const binEnds = bins.map((b) => number(b.end));
  if (q.export_events)
    emit({
      type: "csv",
      text: csvLine([...COLUMNS, "context", "function", "role"]),
    });
  const relevant = m.chunks.filter(
    (c) => number(c.end) > start && number(c.start) < end,
  );
  for (const c of relevant) {
    let phase = performance.now();
    const bytes = await loadChunk(c);
    loadMs += performance.now() - phase;
    phase = performance.now();
    const rows = await decodeChunk(bytes, c, m);
    decodeMs += performance.now() - phase;
    phase = performance.now();
    let csv = "";
    for (const [rowIndex, r] of rows.entries()) {
      const index = number(r[0]);
      if (index < start || index >= end) continue;
      const context = m.contexts[Number(r[5])],
        owner = m.owners[Number(r[6])],
        name = owner.function ?? "unresolved";
      if (!contextMatches[Number(r[5])] || !ownerMatches[Number(r[6])])
        continue;
      const values = rows.counts[rowIndex];
      add(total, values);
      const id = r[6];
      if (!groups.has(id))
        groups.set(id, { id, name, role: owner.role, counts: empty() });
      add(groups.get(id).counts, values);
      // Verified rows are ordered; walk exact integer edges rather than divide per row.
      while (index >= binEnds[binIndex]) binIndex++;
      bins[binIndex].value += metricValue(values, metric);
      bins[binIndex].rows++;
      if (count >= offset && page.length < limit)
        page.push({
          index: r[0],
          pc: r[1],
          address: r[2],
          size: r[3],
          operation: r[4],
          context,
          owner_id: r[6],
          name,
          ...stringify(values),
        });
      if (q.export_events) csv += csvLine([...r, context, name, owner.role]);
      count++;
    }
    aggregateMs += performance.now() - phase;
    if (csv) emit({ type: "csv", text: csv });
    emit({ type: "progress", done: ++visited, total: relevant.length });
  }
  const totals = stringify(total),
    den = metricValue(totals, metric),
    run = metricValue(m.totals, metric);
  const function_rows = [...groups.values()]
    .map((g) => ({
      id: g.id,
      name: g.name,
      role: g.role,
      ...stringify(g.counts),
      value: metricValue(g.counts, metric).toString(),
      run_denominator: run,
      filtered_denominator: den,
    }))
    .sort((a, b) =>
      number(a.value) > number(b.value)
        ? -1
        : number(a.value) < number(b.value)
          ? 1
          : a.name.localeCompare(b.name),
    );
  if (q.profile)
    emit({
      type: "profile",
      chunks: visited,
      load_ms: loadMs,
      decode_ms: decodeMs,
      aggregate_ms: aggregateMs,
      total_ms: performance.now() - begun,
    });
  return {
    request_id: q.request_id,
    run_id: q.run_id,
    start: q.start,
    end: q.end,
    metric,
    totals,
    run_totals: m.totals,
    function_rows,
    bins: bins.map((b) => ({
      ...b,
      value: b.value.toString(),
      rows: b.rows.toString(),
    })),
    event_count: count.toString(),
    event_page: page,
    next_event_offset:
      offset + BigInt(page.length) < count
        ? (offset + BigInt(page.length)).toString()
        : null,
    quality: "event_index_only",
  };
}

export async function decodeManifest(text, expectedHash) {
  const bytes = Uint8Array.from(atob(text), (c) => c.charCodeAt(0));
  const reader = new Blob([bytes])
    .stream()
    .pipeThrough(new DecompressionStream("gzip"))
    .getReader();
  const parts = [];
  let length = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.length;
      if (length > 4 * 1024 * 1024) throw Error("Manifest decompression limit");
      parts.push(value);
    }
  } finally {
    await reader.cancel();
  }
  const data = new Uint8Array(length);
  let i = 0;
  for (const part of parts) {
    data.set(part, i);
    i += part.length;
  }
  if ((await digest(data)) !== expectedHash)
    throw Error("Manifest digest mismatch");
  return JSON.parse(new TextDecoder().decode(data));
}
