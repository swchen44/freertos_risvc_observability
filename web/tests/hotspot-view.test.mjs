import test from "node:test";
import assert from "node:assert/strict";
import {
  selectFacts,
  summarizeFunctions,
  rankFunctions,
  hotspotCsv,
  pcRows,
} from "../src/hotspot-view.js";
const fact = (id, n, context = "task:A") => ({
  function_id: id,
  pc: id === "a" ? 100 : 104,
  context,
  role: "lwip",
  instructions: n,
  memory_cycles: n,
  accounted_model_ns: 3 * n,
  cost_cycles: { l1i: n },
  cache: {
    l1i: { accesses: n, misses: 0, compulsory: 0, conflict: 0, capacity: 0 },
  },
});
const report = {
  identity: { run_id: "r" },
  evidence: {},
  owners: {
    a: { function: "alpha" },
    b: { function: "beta" },
    c: { function: "gamma" },
  },
  totals: { memory_cycles: 100 },
  facts: [fact("a", 30), fact("b", 10), fact("c", 60, "irq:7")],
};
test("joint filter and top N preserve both denominators and full CSV", () => {
  const facts = selectFacts(report, {
    context: "task:A",
    role: "all",
    query: "",
  });
  const rows = summarizeFunctions(report, facts, "memory_cycles");
  const v = rankFunctions(rows, { field: "value", direction: "desc", topN: 1 });
  assert.equal(v.visible[0].run_percent, 30);
  assert.equal(v.visible[0].filtered_percent, 75);
  assert.equal(v.other.value, 10);
  assert.equal(v.allSorted.length, 2);
  assert.equal(
    hotspotCsv(v.allSorted, {}).split("\r\n").filter(Boolean).length,
    3,
  );
  assert.equal(pcRows(report, facts, "a").length, 1);
});
test("empty filter and CSV injection preserve negative numeric deltas", () => {
  assert.deepEqual(
    selectFacts(report, { context: "absent", role: "all", query: "" }),
    [],
  );
  const csv = hotspotCsv([{ name: "=SUM(A1)", delta: -4, value: 0 }], {
    run_id: "r",
  });
  assert.ok(csv.includes("'=SUM(A1)"));
  assert.ok(csv.includes("-4"));
  assert.deepEqual(
    rankFunctions([], { field: "value", direction: "desc", topN: 10 }).visible,
    [],
  );
});

test("per-row pairing exposes missing and ambiguous costs instead of zero deltas", async () => {
  const { annotateComparison } = await import("../src/hotspot-view.js");
  assert.equal(typeof annotateComparison, "function");
  const rows = annotateComparison(
    [
      { id: "c", value: 8 },
      { id: "missing", value: 7 },
      { id: "amb", value: 5 },
    ],
    [{ id: "b", value: 10 }],
    [
      { baseline: ["b"], candidate: ["c"], status: "matched" },
      { baseline: [], candidate: ["missing"], status: "unmatched" },
      { baseline: ["x", "y"], candidate: ["amb"], status: "ambiguous" },
    ],
  );
  assert.equal(rows[0].delta, -2);
  assert.equal(rows[0].delta_percent, -20);
  assert.equal(rows[1].pair_status, "unmatched");
  assert.equal(rows[1].delta, null);
  assert.equal(rows[2].pair_status, "ambiguous");
  assert.equal(
    annotateComparison(
      [{ id: "c", value: 8 }],
      [],
      [{ baseline: ["b"], candidate: ["c"], status: "matched" }],
    )[0].delta,
    null,
  );
});
