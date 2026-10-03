import test from "node:test";
import assert from "node:assert/strict";
import { requestRelative } from "../src/compare.js";
test("comparison uses each request origin, preserves unknown duration", () => {
  const result = requestRelative([
    {
      request_id: 1,
      start_ticks: "9007199254740993",
      end_ticks: "9007199254741013",
      response_ticks: "20",
      execution_ticks: null,
    },
  ]);
  assert.deepEqual(result, [
    {
      request_id: 1,
      start: 0,
      response: 20,
      execution: null,
      origin: "9007199254740993",
    },
  ]);
});
