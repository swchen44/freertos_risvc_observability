import { test, expect } from "@playwright/test";
import { readFile, writeFile, mkdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { parse } from "csv-parse/sync";
const root = fileURLToPath(new URL("../../../", import.meta.url));
const fixture = root + "/fixtures/desktop/trace.psf";
const queue =
  root + "/runs/20261003T074056Z-queue_baseline-26b984eed3/trace.psf";
let errors, external;
test.beforeEach(async ({ page }) => {
  errors = [];
  external = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (r) => {
    if (
      !r.url().startsWith("http://127.0.0.1:8766") &&
      !r.url().startsWith("blob:")
    )
      external.push(r.url());
  });
  await page.goto("/");
});
test.afterEach(() => {
  expect(errors).toEqual([]);
  expect(external).toEqual([]);
});
async function revision(page) {
  return Number(
    (await page.locator("body").getAttribute("data-render-revision")) || 0,
  );
}
async function changed(page, action, timeout = 10000) {
  const before = await revision(page);
  await action();
  await expect.poll(() => revision(page), { timeout }).toBeGreaterThan(before);
}
async function load(page, path = fixture, timeout = 10000) {
  await changed(
    page,
    () => page.locator("#psf-input").setInputFiles(path),
    timeout,
  );
}
async function metadata(page) {
  const id = await page.locator("#saved-traces").inputValue();
  return (await page.request.get("/api/traces/" + id)).json();
}
async function exportCSV(page, kind, info) {
  const pending = page.waitForEvent("download");
  await page.locator("#export-" + kind).click();
  const dl = await pending;
  const path = info.outputPath(kind + ".csv");
  await dl.saveAs(path);
  return parse(await readFile(path, "utf8"), { columns: true });
}
function event(id, seq, time, body) {
  const h = Buffer.alloc(8);
  h.writeUInt16LE(((body.length / 4) << 12) | id);
  h.writeUInt16LE(seq, 2);
  h.writeUInt32LE(time, 4);
  return Buffer.concat([h, body]);
}
function words(...values) {
  const b = Buffer.alloc(values.length * 4);
  values.forEach((v, i) => b.writeUInt32LE(v, i * 4));
  return b;
}
async function synthetic(events) {
  return Buffer.concat([
    (
      await readFile(root + "/artifacts/benchmarks/synthetic-1000.psf")
    ).subarray(0, 72),
    ...events,
  ]);
}

test("B01/02 real upload, SVG, keyboard filters and full sorted CSV", async ({
  page,
}, info) => {
  await load(page);
  await expect(page.locator("#timeline svg")).toBeVisible();
  await expect(page.locator("#timeline canvas")).toHaveCount(0);
  await expect(page.locator("#cpu-chart svg")).toBeVisible();
  await changed(page, () => page.locator("#search-filter").fill("Counter"));
  await changed(page, () =>
    page.locator(".tabulator-col[tabulator-field=ticks]").click(),
  );
  const meta = await metadata(page);
  const result = await (
    await page.request.post(`/api/traces/${meta.trace_id}/events`, {
      data: {
        filters: { search: "Counter" },
        sort: [{ field: "ticks", direction: "desc" }],
        limit: 2000,
      },
    })
  ).json();
  expect(result.total).toBeGreaterThan(20);
  const csv = await exportCSV(page, "events", info);
  expect(csv.map((r) => r.event_id)).toEqual(
    result.rows.map((r) => r.event_id),
  );
  expect(csv.length).toBe(result.total);
  await expect(page.locator(".tabulator-row")).toHaveCount(20);
  await changed(page, () => page.locator("#next").click());
  await expect(page.locator("#page-label")).toContainText("2 /");
  await page.locator("#reset").focus();
  await changed(page, () => page.keyboard.press("Enter"));
  await expect(page.locator("#row-count")).toContainText("309");
});

test("B03 task/object/channel/type filters and CPU denominator/metric CSV", async ({
  page,
}, info) => {
  await load(page, queue);
  const meta = await metadata(page);
  const base = await page.locator("#coverage-label").textContent();
  const task = meta.objects.find((o) => o.name === "consumer");
  await changed(page, () =>
    page.locator("#task-filter").selectOption(task.object_id),
  );
  expect(await page.locator("#coverage-label").textContent()).toBe(base);
  await changed(page, () => page.locator("#reset").click());
  await changed(page, () =>
    page
      .locator("#object-filter")
      .selectOption(meta.objects.find((o) => o.name === "messages").object_id),
  );
  await expect(page.locator("#row-count")).not.toContainText("符合 281 筆");
  await changed(page, () => page.locator("#reset").click());
  await changed(page, () =>
    page.locator("#channel-filter").selectOption("POC"),
  );
  await expect(page.locator("#row-count")).toContainText("符合");
  await changed(page, () => page.locator("#event-filter").selectOption("146"));
  const csv = await exportCSV(page, "events", info);
  expect(csv.length).toBeGreaterThan(0);
  expect(csv.every((r) => r.kind === "user_event")).toBeTruthy();
  const metrics = await exportCSV(page, "metrics", info);
  expect(metrics.length).toBeGreaterThan(0);
  await changed(page, async () => {
    await page.locator("#start-filter").fill("10000");
    await page.locator("#end-filter").fill("30000");
    await page.locator("#apply-window").click();
  });
  await expect(page.locator("#coverage-label")).toContainText("/ 20000 ticks");
  await expect(page.locator("#window-label")).toContainText("[10000, 30000)");
  const view = await (
    await page.request.post(`/api/traces/${meta.trace_id}/view`, {
      data: { filters: { start_ticks: "10000", end_ticks: "30000" } },
    })
  ).json();
  for (const [id, v] of Object.entries(view.metrics.task_share)) {
    const name = meta.objects.find((o) => o.object_id === id).name;
    await expect(page.locator("#share-values")).toContainText(
      `${name} ${(v.fraction * 100).toFixed(2)}%`,
    );
  }
});

test("B04/05 brush, wheel zoom, drag pan and reset change query window", async ({
  page,
}) => {
  await load(page, queue);
  const timeline = page.locator("#timeline");
  const box = await timeline.boundingBox();
  await page.locator("#brush").click();
  await changed(page, async () => {
    await page.mouse.move(box.x + 220, box.y + 90);
    await page.mouse.down();
    await page.mouse.move(box.x + 520, box.y + 90, { steps: 8 });
    await page.mouse.up();
  });
  expect(await page.locator("#start-filter").inputValue()).not.toBe("");
  await changed(page, () => page.locator("#reset-window").click());
  await page.mouse.move(box.x + 400, box.y + 110);
  await changed(page, () => page.mouse.wheel(0, -350));
  const zoom = await page.locator("#start-filter").inputValue();
  await changed(page, async () => {
    await page.mouse.move(box.x + 430, box.y + 145);
    await page.mouse.down();
    await page.mouse.move(box.x + 500, box.y + 145, { steps: 10 });
    await page.mouse.up();
  });
  expect(await page.locator("#start-filter").inputValue()).not.toBe(zoom);
  await changed(page, () => page.locator("#reset-window").click());
  await expect(page.locator("#start-filter")).toHaveValue("");
});

test("B06/07 hover, pin, column resize and reorder use real DOM", async ({
  page,
}) => {
  await load(page);
  const rows = page.locator(".tabulator-row");
  await rows.nth(0).hover();
  await expect(page.locator("#details")).toContainText("payload_hex");
  await rows.nth(0).click();
  const pinned = await page.locator("#details").textContent();
  await rows.nth(1).hover();
  expect(await page.locator("#details").textContent()).toBe(pinned);
  await page.locator("#unpin").click();
  await rows.nth(1).hover();
  await expect(page.locator("#details")).not.toHaveText(pinned);
  const col = page.locator(".tabulator-col[tabulator-field=ticks]");
  const before = await col.boundingBox();
  const handle = page.locator(
    ".tabulator-col[tabulator-field=ticks] + .tabulator-col-resize-handle",
  );
  const hb = await handle.boundingBox();
  await page.mouse.move(hb.x + hb.width / 2, hb.y + hb.height / 2);
  await page.mouse.down();
  await page.mouse.move(hb.x + 65, hb.y + hb.height / 2, { steps: 10 });
  await page.mouse.up();
  expect((await col.boundingBox()).width).toBeGreaterThan(before.width + 20);
  const headers = () =>
    page
      .locator(".tabulator-headers > .tabulator-col")
      .evaluateAll((es) => es.map((e) => e.getAttribute("tabulator-field")));
  const original = await headers();
  const a = await col.boundingBox(),
    b = await page
      .locator(".tabulator-col[tabulator-field=actor_name]")
      .boundingBox();
  await page.mouse.move(a.x + 30, a.y + 15);
  await page.mouse.down();
  await page.mouse.move(b.x + b.width - 10, b.y + 15, { steps: 20 });
  await page.mouse.up();
  expect(await headers()).not.toEqual(original);
});

test("B08 three verified comparisons and request-relative chart", async ({
  page,
}) => {
  await page
    .locator("#run-select option:nth-child(2)")
    .waitFor({ state: "attached" });
  for (const pair of ["logger", "priority", "locks"]) {
    await page.locator("#pair-select").selectOption(pair);
    await page.locator("#compare-run").click();
    await expect(page.locator("#comparison .comparison-result")).toContainText(
      pair + "：pass",
    );
    if (pair === "logger")
      await expect(page.locator(".comparison-chart svg")).toBeVisible();
  }
});

test("B09 unsupported, partial and empty trace show truthful quality", async ({
  page,
}) => {
  await page
    .locator("#psf-input")
    .setInputFiles({
      name: "bad.psf",
      mimeType: "application/octet-stream",
      buffer: Buffer.from("BAD!"),
    });
  await expect(page.locator("#status")).toHaveClass(/error/);
  await expect(page.locator("#trace-workspace")).toBeHidden();
  const data = await readFile(fixture);
  await load(page, {
    name: "partial.psf",
    mimeType: "application/octet-stream",
    buffer: data.subarray(0, -1),
  });
  await expect(page.locator("#status")).toContainText("partial");
  await load(page, {
    name: "empty.psf",
    mimeType: "application/octet-stream",
    buffer: await synthetic([]),
  });
  await expect(page.locator("#row-count")).toContainText("符合 0 筆");
  await expect(page.locator("#window-label")).toContainText("[0, 0)");
});

test("B10 raw HTML remains text, null timestamps and unknown frequency", async ({
  page,
}) => {
  const label = Buffer.alloc(40);
  label.write("<img src=x onerror=alert(1)>");
  const raw = await synthetic([
    event(3, 0, 1, Buffer.concat([words(4096), label])),
    event(0x37, 1, 100, words(4096)),
    event(0x37, 2, 0x80000100, words(4096)),
  ]);
  raw.writeUInt32LE(0, 40);
  let dialogs = 0;
  page.on("dialog", async (d) => {
    dialogs++;
    await d.dismiss();
  });
  await load(page, {
    name: "<b>untrusted.psf",
    mimeType: "application/octet-stream",
    buffer: raw,
  });
  await expect(page.locator("#task-filter")).toContainText(
    "<img src=x onerror=alert(1)>",
  );
  expect(await page.locator("img").count()).toBe(0);
  expect(dialogs).toBe(0);
  await expect(page.locator("#window-label")).toContainText("時間頻率未知");
  await expect(page.locator("#aggregation-label")).toContainText(
    "1 個事件時間未知",
  );
});

test("B11 delayed old filter response cannot overwrite newer selection", async ({
  page,
}) => {
  await load(page);
  let release;
  const gate = new Promise((r) => (release = r));
  let held;
  const started = new Promise((r) => (held = r));
  await page.route("**/api/traces/*/events", async (route) => {
    if (route.request().postDataJSON().filters.search === "Counter") {
      const response = await route.fetch();
      held();
      await gate;
      await route.fulfill({ response });
    } else await route.continue();
  });
  await page.locator("#search-filter").fill("Counter");
  await started;
  await changed(page, () =>
    page.locator("#search-filter").fill("no-match-at-all"),
  );
  await expect(page.locator("#row-count")).toContainText("符合 0 筆");
  release();
  await page.waitForResponse(
    (r) =>
      r.url().endsWith("/events") &&
      r.request().postDataJSON().filters.search === "Counter",
  );
  await expect(page.locator("#row-count")).toContainText("符合 0 筆");
});

test("B12/13/14 1k/10k/100k capacity, bounded SVG, measured render and filter", async ({
  page,
  browser,
}) => {
  const rows = [];
  await page.addInitScript(() => {
    window.measurements = [];
    window.addEventListener("psf-settled", (e) =>
      window.measurements.push(e.detail),
    );
  });
  await page.reload();
  for (const count of [1000, 10000, 100000]) {
    const started = Date.now();
    await load(
      page,
      root + `/artifacts/benchmarks/synthetic-${count}.psf`,
      30000,
    );
    const first = Date.now() - started;
    const meta = await metadata(page);
    expect(meta.event_count).toBe(count);
    if (count > 1000)
      await expect(page.locator("#aggregation-label")).toContainText("density");
    const svgMarks = await page.locator("#timeline svg *").count();
    expect(svgMarks).toBeLessThan(3000);
    await expect(page.locator(".tabulator-row")).toHaveCount(20);
    await changed(page, () =>
      page.locator("#task-filter").selectOption(meta.objects[0].object_id),
    );
    const measures = await page.evaluate(() => window.measurements.slice(-2));
    rows.push({
      count,
      first_upload_to_render_ms: first,
      render_ms: measures[0].duration_ms,
      filter_to_settled_ms: measures[1].duration_ms,
      svg_elements: svgMarks,
      table_rows: 20,
    });
  }
  await mkdir(root + "/artifacts/browser", { recursive: true });
  await writeFile(
    root + "/artifacts/browser/capacity.json",
    JSON.stringify(
      {
        browser: browser.version(),
        viewport: { width: 1600, height: 1000 },
        rows,
      },
      null,
      2,
    ) + "\n",
  );
});

test("B11 source race: delayed run download cannot replace a newer upload", async ({
  page,
}) => {
  await page
    .locator("#run-select option:nth-child(2)")
    .waitFor({ state: "attached" });
  let release, held;
  const gate = new Promise((r) => (release = r)),
    started = new Promise((r) => (held = r));
  await page.route("**/api/runs/*/psf", async (route) => {
    const response = await route.fetch();
    held();
    await gate;
    await route.fulfill({ response });
  });
  await page.locator("#run-select").selectOption({ index: 1 });
  await page.locator("#load-run").click();
  await started;
  await load(page, fixture);
  const before = await page.locator("#source-info").textContent();
  const finished = page.waitForResponse((r) => r.url().endsWith("/psf"));
  release();
  await finished;
  // Wait on all real requests becoming idle, not an arbitrary rendering delay.
  await page.waitForLoadState("networkidle");
  expect(await page.locator("#source-info").textContent()).toBe(before);
  await expect(page.locator("#source-info")).toContainText("309 events");
});
