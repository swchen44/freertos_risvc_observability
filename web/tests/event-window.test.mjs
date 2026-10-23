import test from "node:test";
import assert from "node:assert/strict";
import { existsSync } from "node:fs";
import { gzipSync } from "node:zlib";
import { createHash } from "node:crypto";
const hash = (b) => createHash("sha256").update(b).digest("hex");
async function fixture() {
  assert.ok(
    existsSync(new URL("../src/event-window-data.js", import.meta.url)),
    "event engine missing",
  );
  const m = await import("../src/event-window-data.js");
  const rows = [0, 1, 2].map((i) => [
    String(i),
    "100",
    "100",
    "4",
    "I",
    "0",
    "0",
    i === 1 ? "9007199254740993" : "1",
    ...Array(19).fill("0"),
  ]);
  const totals = m.sumRows(rows);
  const data = {
    schema: "event-window-chunk-v1",
    start: "0",
    end: "3",
    columns: m.COLUMNS,
    rows,
  };
  const raw = Buffer.from(JSON.stringify(data)),
    gzip = gzipSync(raw);
  const c = {
    id: "000000",
    start: "0",
    end: "3",
    rows: "3",
    compressed_bytes: String(gzip.length),
    uncompressed_bytes: String(raw.length),
    gzip_sha256: hash(gzip),
    json_sha256: hash(raw),
    totals,
  };
  const manifest = {
    schema: "event-window-run-v1",
    columns: m.COLUMNS,
    events: "3",
    contexts: ["task:A"],
    owners: [{ function_id: "f", function: "=SUM(1)", role: "lwip" }],
    chunks: [c],
    totals,
    identity: { run_id: "toy" },
  };
  return { m, manifest, gzip };
}
test("exact interval and integer beyond 2^53, empty selection", async () => {
  const { m, manifest, gzip } = await fixture();
  const q = {
    request_id: 1,
    run_id: "toy",
    start: "1",
    end: "2",
    metric: "memory_cycles",
    context: "",
    function_query: "",
    event_offset: "0",
    event_limit: 200,
  };
  const r = await m.queryEventWindow(
    manifest,
    async () => gzip,
    q,
    () => {},
  );
  assert.equal(r.totals.memory_cycles, "9007199254740993");
  assert.equal(r.event_page[0].index, "1");
  assert.equal(r.function_rows[0].run_denominator, "9007199254740995");
  assert.equal(
    r.bins.reduce((n, b) => n + BigInt(b.value), 0n),
    9007199254740993n,
  );
  const empty = await m.queryEventWindow(
    manifest,
    async () => gzip,
    { ...q, end: "1" },
    () => {},
  );
  assert.equal(empty.event_count, "0");
  assert.deepEqual(empty.function_rows, []);
  const csv = m.functionsCsv(r.function_rows);
  assert.ok(csv.includes("9007199254740993"));
  assert.ok(csv.includes("'=SUM(1)"));
});
test("corruption, bad query and missing chunks rejected", async () => {
  const { m, manifest, gzip } = await fixture();
  const q = {
    run_id: "toy",
    start: "0",
    end: "3",
    metric: "memory_cycles",
    event_limit: 200,
    event_offset: "0",
  };
  await assert.rejects(() =>
    m.queryEventWindow(
      manifest,
      async () => Buffer.concat([gzip, Buffer.from("x")]),
      q,
      () => {},
    ),
  );
  await assert.rejects(() =>
    m.queryEventWindow(
      { ...manifest, chunks: [] },
      async () => gzip,
      q,
      () => {},
    ),
  );
  await assert.rejects(() =>
    m.queryEventWindow(
      manifest,
      async () => gzip,
      { ...q, start: "-1" },
      () => {},
    ),
  );
  const r = await m.queryEventWindow(
    manifest,
    async () => gzip,
    { ...q, context: "unknown" },
    () => {},
  );
  assert.equal(r.event_count, "0");
});
test("CSV covers every selected row, independent of event pagination", async () => {
  const { m, manifest, gzip } = await fixture();
  let pieces = [];
  const r = await m.queryEventWindow(
    manifest,
    async () => gzip,
    {
      run_id: "toy",
      start: "0",
      end: "3",
      metric: "instructions",
      event_limit: 1,
      event_offset: "1",
      export_events: true,
    },
    (x) => {
      if (x.type === "csv") pieces.push(x.text);
    },
  );
  assert.equal(r.event_page.length, 1);
  assert.equal(r.next_event_offset, "2");
  assert.equal(pieces.join("").trim().split("\n").length, 4);
});
test("manifest dictionaries reject wrong types and duplicate identities", async () => {
  const { m, manifest } = await fixture();
  for (const patch of [
    { contexts: "unknown" },
    { contexts: [null] },
    { contexts: ["task:A", "task:A"] },
    { owners: [null] },
    { owners: [{}] },
    { owners: [...manifest.owners, ...manifest.owners] },
    { owners: [{ function_id: "f", role: 3 }] },
    { chunks: {} },
  ])
    assert.throws(
      () => m.validateManifest({ ...manifest, ...patch }),
      /manifest|dictionary/i,
    );
});
test("CSV guards spreadsheet control prefixes and preserves quotes", async () => {
  const { m } = await fixture();
  assert.equal(
    m.csvLine(["\t=1+1", "\r=1+1", 'a"b']),
    '"\'\t=1+1","\'\r=1+1","a""b"\r\n',
  );
});
test("canonical numeric wire and header-only empty CSV", async () => {
  const { m, manifest, gzip } = await fixture();
  for (const value of [
    true,
    1,
    "01",
    "-0",
    "1.0",
    "1e2",
    "",
    " 1",
    "١",
    "1\n",
    "1\r",
    "1\u2028",
    "0\n",
  ])
    assert.throws(() => m.number(value));
  const pieces = [];
  const r = await m.queryEventWindow(
    manifest,
    async () => gzip,
    {
      run_id: "toy",
      start: "1",
      end: "1",
      metric: "memory_cycles",
      event_offset: "0",
      event_limit: 200,
      export_events: true,
    },
    (x) => {
      if (x.type === "csv") pieces.push(x.text);
    },
  );
  assert.equal(r.event_count, "0");
  assert.equal(pieces.length, 1);
  assert.equal(
    pieces[0],
    m.csvLine([...m.COLUMNS, "context", "function", "role"]),
  );
});

test("CSV round-trips multiline Unicode, empty function set, and exact event integers", async () => {
  const { parse } = await import("csv-parse/sync");
  const { m, manifest, gzip } = await fixture();
  const value = 'alpha\n臺灣😀,"quoted"';
  assert.deepEqual(parse(m.csvLine([value])), [[value]]);
  assert.deepEqual(parse(m.functionsCsv([]), { columns: true }), []);
  assert.equal(parse(m.functionsCsv([])).length, 1);
  const pieces = [];
  await m.queryEventWindow(
    manifest,
    async () => gzip,
    {
      run_id: "toy",
      start: "0",
      end: "3",
      metric: "memory_cycles",
      event_offset: "0",
      event_limit: 1,
      export_events: true,
    },
    (x) => {
      if (x.type === "csv") pieces.push(x.text);
    },
  );
  const rows = parse(pieces.join(""), { columns: true });
  assert.equal(rows.length, 3);
  assert.equal(rows[1].l1i, "9007199254740993");
});

test("full-chunk and selected-row aggregation agree for exact counters", async () => {
  const { m, manifest, gzip } = await fixture();
  for (const [start, end] of [
    ["0", "3"],
    ["1", "2"],
  ]) {
    const query = {
      run_id: "toy",
      start,
      end,
      metric: "memory_cycles",
      event_offset: "0",
      event_limit: 200,
    };
    const full = await m.queryEventWindow(manifest, async () => gzip, query);
    const selected = await m.queryEventWindow(manifest, async () => gzip, {
      ...query,
      context: "task:A",
    });
    assert.deepEqual(full, selected);
  }
});
