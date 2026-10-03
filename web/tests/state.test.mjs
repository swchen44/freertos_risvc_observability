import test from "node:test";
import assert from "node:assert/strict";
import { createStore } from "../src/state.js";
test("isolated state, patch and reset", () => {
  const initial = { filters: { task_ids: [] }, selection: null };
  const a = createStore(initial);
  let seen = 0;
  a.subscribe(() => seen++);
  const external = a.getState();
  external.filters.task_ids.push("BAD");
  assert.deepEqual(a.getState(), initial);
  a.setState({ filters: { task_ids: ["A"] } });
  assert.equal(seen, 1);
  assert.deepEqual(initial.filters.task_ids, []);
  a.reset();
  assert.deepEqual(a.getState(), initial);
});
