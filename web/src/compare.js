import * as echarts from "echarts";
import { relativeTickNumber, colors } from "./timeline.js";

export function requestRelative(requests) {
  return requests.map((r) => ({
    request_id: r.request_id,
    start: 0,
    response:
      r.response_ticks === null
        ? null
        : relativeTickNumber(r.response_ticks, "0"),
    execution:
      r.execution_ticks === null
        ? null
        : relativeTickNumber(r.execution_ticks, "0"),
    origin: r.start_ticks,
  }));
}
let chart, observer;
export function renderComparison(element, result) {
  observer?.disconnect();
  chart?.dispose();
  chart = null;
  element.replaceChildren();
  const status = document.createElement("p");
  status.className = "comparison-result";
  status.textContent = `${result.pair_id}：${result.verdict} · ${result.assertions?.length || 0} 個條件`;
  element.append(status);
  const series = [];
  for (const [index, run] of (result.runs || []).entries()) {
    const section = document.createElement("div"),
      title = document.createElement("strong");
    title.textContent = run.case.case_id;
    const detail = document.createElement("p");
    detail.textContent = `結果：${run.oracle.outcome}。${run.oracle.outcome === "normal" ? "正常案例" : "預期重現異常"}。時基：${run.manifest.time_model}`;
    section.append(title, detail);
    const relative = requestRelative(run.analysis.requests);
    if (relative.length) {
      const valid = relative.filter((r) => r.response !== null);
      const p = document.createElement("p");
      p.textContent = `Response ${Math.min(...valid.map((r) => r.response))} ～ ${Math.max(...valid.map((r) => r.response))} ticks；${valid.length} requests`;
      section.append(p);
      series.push({
        name: run.case.case_id,
        type: "bar",
        itemStyle: { color: colors[index] },
        data: relative.map((r) => r.response),
      });
    }
    const pre = document.createElement("pre");
    pre.textContent = JSON.stringify(run.case.parameters, null, 2);
    section.append(pre);
    element.append(section);
  }
  if (series.length) {
    const note = document.createElement("p");
    note.textContent =
      "每筆 request 各自從 0 對齊；長度為 response ticks，未相減兩次 capture 的絕對時間。";
    element.append(note);
    const canvas = document.createElement("div");
    canvas.className = "comparison-chart";
    canvas.style.height = "280px";
    element.append(canvas);
    chart = echarts.init(canvas, null, { renderer: "svg" });
    observer = new ResizeObserver(() => chart?.resize());
    observer.observe(canvas);
    chart.setOption({
      animation: false,
      tooltip: { trigger: "axis", renderMode: "richText" },
      legend: { bottom: 0 },
      grid: { left: 75, right: 20, top: 30, bottom: 65 },
      xAxis: {
        type: "category",
        name: "request",
        data: result.runs[0].analysis.requests.map((r) => String(r.request_id)),
      },
      yAxis: { type: "value", name: "response ticks" },
      series,
    });
  }
  const details = document.createElement("details"),
    summary = document.createElement("summary"),
    pre = document.createElement("pre");
  summary.textContent = "查看全部比較條件";
  pre.textContent = JSON.stringify(result.assertions, null, 2);
  details.append(summary, pre);
  element.append(details);
}
