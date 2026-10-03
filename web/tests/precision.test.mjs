import test from "node:test";
import assert from "node:assert/strict";
import { relativeTickNumber } from "../src/timeline.js";
test("subtract before Number conversion", () => {
  assert.equal(relativeTickNumber("9007199254741002", "9007199254740992"), 10);
  assert.throws(() => relativeTickNumber("9007199254740992", "0"), RangeError);
  assert.throws(() => relativeTickNumber(null, "0"), TypeError);
});
