// CPU/data-path diagnostic only: no browser/RSS acceptance claim.
import { readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import { createHash } from "node:crypto";
import { pathToFileURL } from "node:url";
const [folder, output, enginePath] = process.argv.slice(2);
const engine = enginePath
  ? pathToFileURL(path.resolve(enginePath))
  : new URL("../../web/src/event-window-data.js", import.meta.url);
const { queryEventWindow } = await import(engine);
if (!folder || !output)
  throw Error(
    "Usage: node tools/tcp/benchmark_event_window.mjs RUN_DIR NEW_OUTPUT",
  );
const manifest = JSON.parse(await readFile(path.join(folder, "manifest.json")));
const compressed = new Map();
for (const c of manifest.chunks)
  compressed.set(c.id, await readFile(path.join(folder, c.id + ".json.gz")));
const runs = [];
for (let i = 0; i < 3; i++) {
  const started = performance.now();
  let profile;
  const result = await queryEventWindow(
    manifest,
    async (c) => compressed.get(c.id),
    {
      request_id: 1,
      run_id: manifest.identity.run_id,
      start: "0",
      end: manifest.events,
      metric: "memory_cycles",
      event_limit: 200,
      profile: true,
    },
    (message) => {
      if (message.type === "profile") profile = message;
    },
  );
  runs.push({
    seconds: (performance.now() - started) / 1000,
    result_sha256: createHash("sha256")
      .update(JSON.stringify(result))
      .digest("hex"),
    profile,
    events: result.event_count,
    totals: result.totals,
  });
}
const receipt = {
  scope: "Node engine; compressed input in memory; not browser acceptance",
  node: process.version,
  engine_sha256: createHash("sha256")
    .update(await readFile(engine))
    .digest("hex"),
  chunks: manifest.chunks.length,
  runs,
};
await writeFile(output, JSON.stringify(receipt, null, 2) + "\n", {
  flag: "wx",
});
console.log(
  runs.map((r) => ({ seconds: r.seconds, result_sha256: r.result_sha256 })),
);
