import * as echarts from "echarts";
export const colors = [
  "#2774B8",
  "#1F8A83",
  "#CB8635",
  "#9669B8",
  "#BC6077",
  "#668441",
  "#58788E",
  "#9C7651",
];
export function relativeTickNumber(ticks, origin) {
  if (typeof ticks !== "string" || typeof origin !== "string")
    throw new TypeError("Ticks must be decimal strings");
  const value = BigInt(ticks) - BigInt(origin);
  if (
    value > BigInt(Number.MAX_SAFE_INTEGER) ||
    value < BigInt(Number.MIN_SAFE_INTEGER)
  )
    throw new RangeError("時間範圍太大，請縮小窗口");
  return Number(value);
}
export function mountTimeline(element, onWindowChange, onInspect = () => {}) {
  const chart = echarts.init(element, null, { renderer: "svg" });
  let current,
    origin = "0",
    updating = false;
  const observer = new ResizeObserver(() => chart.resize());
  observer.observe(element);
  function emit(left, right) {
    if (right > left)
      onWindowChange(
        (BigInt(origin) + BigInt(Math.floor(left))).toString(),
        (BigInt(origin) + BigInt(Math.ceil(right))).toString(),
      );
  }
  chart.on("datazoom", (event) => {
    if (updating || !current) return;
    const zoom = event.batch?.[0] || event;
    const width = relativeTickNumber(current.fullEnd, origin);
    emit((width * (zoom.start ?? 0)) / 100, (width * (zoom.end ?? 100)) / 100);
  });
  chart.on("brushEnd", (event) => {
    const range = event.areas?.[0]?.coordRange;
    if (range) emit(range[0], range[1]);
  });
  chart.on("click", (event) => {
    if (event.data?.interval) onInspect(event.data.interval);
  });
  return {
    render(view) {
      current = view;
      origin = view.fullStart || view.metrics.start_ticks;
      const end = view.fullEnd || view.metrics.end_ticks;
      const width = Math.max(1, relativeTickNumber(end, origin));
      const objects = new Map(
        (view.objects || []).map((o) => [o.object_id, o.name || o.object_id]),
      );
      const lanes = [...new Set(view.intervals.map((i) => i.object_id))];
      const text =
        getComputedStyle(element).getPropertyValue("--ink").trim() || "#203449";
      updating = true;
      chart.setOption(
        {
          animation: false,
          textStyle: {
            color: text,
            fontFamily: "Avenir Next, PingFang TC, sans-serif",
          },
          grid: { left: 120, right: 24, top: 28, bottom: 65 },
          tooltip: {
            trigger: "item",
            renderMode: "richText",
            formatter: (p) => {
              const i = p.data.interval;
              return `${objects.get(i.object_id) || "Unknown"}\n${i.start_ticks} → ${i.end_ticks} ticks\n${i.state}${i.count ? ` · ${i.count} intervals` : ""}`;
            },
          },
          xAxis: {
            type: "value",
            min: 0,
            max: width,
            name: "ticks",
            axisLabel: { color: text },
          },
          yAxis: {
            type: "category",
            data: lanes.map((id) => objects.get(id) || "Unknown"),
            axisLabel: { color: text, width: 105, overflow: "truncate" },
            splitLine: { show: true, lineStyle: { color: "#DCE3EB" } },
          },
          dataZoom: [
            {
              type: "slider",
              startValue: relativeTickNumber(view.metrics.start_ticks, origin),
              endValue: relativeTickNumber(view.metrics.end_ticks, origin),
              bottom: 8,
              height: 22,
            },
            {
              type: "inside",
              filterMode: "none",
              zoomOnMouseWheel: true,
              moveOnMouseMove: true,
            },
          ],
          brush: {
            xAxisIndex: 0,
            brushMode: "single",
            toolbox: ["lineX", "clear"],
          },
          toolbox: {
            right: 10,
            top: 0,
            feature: { brush: { type: ["lineX", "clear"] } },
          },
          series: [
            {
              type: "custom",
              renderItem: (params, api) => {
                const y = api.value(0),
                  start = api.coord([api.value(1), y]),
                  finish = api.coord([api.value(2), y]),
                  height = Math.min(22, api.size([0, 1])[1] * 0.6);
                const rect = echarts.graphic.clipRectByRect(
                  {
                    x: start[0],
                    y: start[1] - height / 2,
                    width: Math.max(1, finish[0] - start[0]),
                    height,
                  },
                  {
                    x: params.coordSys.x,
                    y: params.coordSys.y,
                    width: params.coordSys.width,
                    height: params.coordSys.height,
                  },
                );
                return rect
                  ? {
                      type: "rect",
                      shape: rect,
                      style: {
                        fill:
                          api.value(3) === 1
                            ? "#919DAA"
                            : colors[y % colors.length],
                        opacity: api.value(3) === 2 ? 0.55 : 1,
                      },
                    }
                  : null;
              },
              encode: { x: [1, 2], y: 0 },
              data: view.intervals.map((i) => ({
                value: [
                  lanes.indexOf(i.object_id),
                  relativeTickNumber(i.start_ticks, origin),
                  relativeTickNumber(i.end_ticks, origin),
                  i.state === "unknown" ? 1 : i.state === "density" ? 2 : 0,
                ],
                interval: i,
              })),
            },
          ],
        },
        true,
      );
      updating = false;
    },
    dispose() {
      observer.disconnect();
      chart.dispose();
    },
    brush() {
      chart.dispatchAction({
        type: "takeGlobalCursor",
        key: "brush",
        brushOption: { brushType: "lineX", brushMode: "single" },
      });
    },
    chart,
  };
}
export function mountMetrics(element, kind) {
  const chart = echarts.init(element, null, { renderer: "svg" });
  const observer = new ResizeObserver(() => chart.resize());
  observer.observe(element);
  return {
    render(view) {
      const names = new Map(
        (view.objects || []).map((o) => [o.object_id, o.name || o.object_id]),
      );
      const text =
        getComputedStyle(element).getPropertyValue("--ink").trim() || "#203449";
      let option;
      if (kind === "cpu") {
        const keys = Object.keys(view.metrics.task_share);
        option = {
          legend: { type: "scroll", bottom: 0, textStyle: { color: text } },
          xAxis: {
            type: "category",
            data: view.trend.map((m) => m.start_ticks),
            axisLabel: { color: text },
          },
          yAxis: {
            type: "value",
            max: 100,
            axisLabel: { formatter: "{value}%", color: text },
          },
          series: [
            ...keys.map((key, i) => ({
              name: names.get(key) || key,
              type: "bar",
              stack: "cpu",
              itemStyle: { color: colors[i % colors.length] },
              data: view.trend.map(
                (m) => (m.task_share[key]?.fraction || 0) * 100,
              ),
            })),
            {
              name: "Unknown",
              type: "bar",
              stack: "cpu",
              itemStyle: { color: "#919DAA" },
              data: view.trend.map(
                (m) => (Number(m.unknown_ticks) / Number(m.window_ticks)) * 100,
              ),
            },
          ],
        };
      } else if (view.requests.length) {
        option = {
          legend: { bottom: 0, textStyle: { color: text } },
          xAxis: {
            type: "category",
            data: view.requests.map((r) => String(r.request_id)),
            name: "request",
            axisLabel: { color: text },
          },
          yAxis: { type: "value", name: "ticks", axisLabel: { color: text } },
          series: [
            {
              name: "Response",
              type: "line",
              connectNulls: false,
              data: view.requests.map((r) =>
                r.response_ticks === null ? null : Number(r.response_ticks),
              ),
              itemStyle: { color: colors[0] },
            },
            {
              name: "Execution",
              type: "line",
              connectNulls: false,
              data: view.requests.map((r) =>
                r.execution_ticks === null ? null : Number(r.execution_ticks),
              ),
              itemStyle: { color: colors[1] },
            },
          ],
        };
      } else {
        option = {
          xAxis: {
            type: "category",
            data: view.signals.map((s) => s.ticks),
            axisLabel: { color: text },
          },
          yAxis: { type: "value", name: "Counter", axisLabel: { color: text } },
          series: [
            {
              name: "Counter",
              type: "line",
              data: view.signals.map((s) => s.value),
              itemStyle: { color: colors[1] },
            },
          ],
        };
      }
      chart.setOption(
        {
          animation: false,
          textStyle: {
            color: text,
            fontFamily: "Avenir Next, PingFang TC, sans-serif",
          },
          grid: { left: 60, right: 25, top: 30, bottom: 58 },
          tooltip: { trigger: "axis", renderMode: "richText" },
          ...option,
        },
        true,
      );
    },
    dispose() {
      observer.disconnect();
      chart.dispose();
    },
  };
}
