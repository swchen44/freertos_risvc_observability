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

test("cross-chunk sparse filters preserve all counters and exact uneven bins", async () => {
  const { m } = await fixture();
  const owners = [
    { function_id: "a", function: "Tcp_A", role: "app" },
    { function_id: "b", function: "other", role: "irq" },
    { function_id: "c", function: null, role: "unknown" },
  ];
  const rows = Array.from({ length: 1031 }, (_, i) => [
    String(i),
    "100",
    "100",
    "4",
    i % 3 === 0 ? "I" : i % 3 === 1 ? "R" : "W",
    String(i % 2),
    String(i % 3),
    ...m.COSTS.map((_, j) =>
      String(BigInt(i + j) + (j === 4 ? 9007199254740993n : 0n)),
    ),
    ...m.LEVELS.flatMap(() => ["10", "6", "1", "2", "3"]),
  ]);
  const payloads = new Map();
  const chunks = [];
  for (let start = 0; start < rows.length; start += 1024) {
    const subset = rows.slice(start, start + 1024),
      end = start + subset.length;
    const raw = Buffer.from(
      JSON.stringify({
        schema: "event-window-chunk-v1",
        columns: m.COLUMNS,
        start: String(start),
        end: String(end),
        rows: subset,
      }),
    );
    const gzip = gzipSync(raw),
      id = String(chunks.length).padStart(6, "0");
    chunks.push({
      id,
      start: String(start),
      end: String(end),
      rows: String(subset.length),
      compressed_bytes: String(gzip.length),
      uncompressed_bytes: String(raw.length),
      gzip_sha256: hash(gzip),
      json_sha256: hash(raw),
      totals: m.sumRows(subset),
    });
    payloads.set(id, gzip);
  }
  const manifest = {
    schema: "event-window-run-v1",
    columns: m.COLUMNS,
    events: String(rows.length),
    identity: { run_id: "toy" },
    owners,
    contexts: ["task:A", "irq:7"],
    chunks,
    totals: m.sumRows(rows),
  };
  const metrics = [
    "instructions",
    "memory_cycles",
    "model_service_ns",
    "accounted_model_ns",
    ...m.LEVELS.flatMap((l) => m.COUNTERS.map((k) => `${l}.${k}`)),
  ];
  for (const [context, function_query] of [
    ["", ""],
    ["irq:7", "TCP_"],
    ["", "UnReSoLvEd"],
    ["absent", ""],
  ]) {
    for (const metric of metrics) {
      const q = {
        run_id: "toy",
        start: "3",
        end: "1030",
        context,
        function_query,
        metric,
        profile: true,
      };
      const messages = [];
      const result = await m.queryEventWindow(
        manifest,
        async (c) => payloads.get(c.id),
        q,
        (x) => messages.push(x),
      );
      const selected = rows.filter(
        (r) =>
          Number(r[0]) >= 3 &&
          Number(r[0]) < 1030 &&
          (!context || manifest.contexts[Number(r[5])] === context) &&
          (owners[Number(r[6])].function ?? "unresolved")
            .toLowerCase()
            .includes(function_query.toLowerCase()),
      );
      const value = (r) => {
        const cycles = r.slice(7, 12).reduce((a, b) => a + BigInt(b), 0n);
        if (metric === "instructions") return r[4] === "I" ? 1n : 0n;
        if (metric === "memory_cycles") return cycles;
        if (metric === "model_service_ns") return 2n * cycles;
        if (metric === "accounted_model_ns")
          return 2n * cycles + (r[4] === "I" ? 1n : 0n);
        return BigInt(r[m.COLUMNS.indexOf(metric)]);
      };
      assert.equal(result.event_count, String(selected.length));
      for (const l of m.LEVELS)
        for (const k of m.COUNTERS)
          assert.equal(
            result.totals.cache[l][k],
            String(
              selected.reduce(
                (n, r) => n + BigInt(r[m.COLUMNS.indexOf(`${l}.${k}`)]),
                0n,
              ),
            ),
          );
      for (const k of m.COSTS)
        assert.equal(
          result.totals.cost_cycles[k],
          String(
            selected.reduce((n, r) => n + BigInt(r[m.COLUMNS.indexOf(k)]), 0n),
          ),
        );
      const total = selected.reduce((n, r) => n + value(r), 0n);
      assert.equal(String(m.metricValue(result.totals, metric)), String(total));
      assert.equal(
        result.function_rows.reduce((n, r) => n + BigInt(r.value), 0n),
        total,
      );
      for (const b of result.bins) {
        const inside = selected.filter(
          (r) =>
            BigInt(r[0]) >= BigInt(b.start) && BigInt(r[0]) < BigInt(b.end),
        );
        assert.equal(
          b.value,
          String(inside.reduce((n, r) => n + value(r), 0n)),
        );
        assert.equal(b.rows, String(inside.length));
      }
      assert.equal(messages.filter((x) => x.type === "profile").length, 1);
      assert.equal(messages.at(-1).chunks, 2);
    }
  }
});

test("canonical wire types and hash-valid cache conservation failures are rejected", async () => {
  const { m, manifest, gzip } = await fixture();
  const { gunzipSync } = await import("node:zlib");
  for (const [column, bad] of [
    [7, true],
    [7, "01"],
    [7, 1],
    [7, "-1"],
    [13, "1"],
    [4, "X"],
    [6, "9"],
  ]) {
    const data = JSON.parse(gunzipSync(gzip));
    data.rows[0][column] = bad;
    const raw = Buffer.from(JSON.stringify(data)),
      payload = gzipSync(raw);
    const descriptor = {
      ...manifest.chunks[0],
      compressed_bytes: String(payload.length),
      uncompressed_bytes: String(raw.length),
      gzip_sha256: hash(payload),
      json_sha256: hash(raw),
    };
    await assert.rejects(() => m.decodeChunk(payload, descriptor, manifest));
  }
});
