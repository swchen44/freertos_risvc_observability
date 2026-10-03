import { TabulatorFull as Tabulator } from "tabulator-tables";
export function mountEventTable(element, onSelect, onSort) {
  const columns = [
    ["時間 ticks", "ticks", 135],
    ["事件", "kind", 180],
    ["Task", "actor_name", 145],
    ["物件", "object_name", 145],
    ["訊息", "message", 270],
    ["Offset", "offset", 100],
    ["Seq", "sequence", 85],
  ];
  const table = new Tabulator(element, {
    height: 320,
    layout: "fitDataStretch",
    movableColumns: true,
    resizableColumnFit: false,
    selectableRows: 1,
    placeholder: "目前沒有符合的事件",
    columnDefaults: {
      headerSort: false,
      resizable: true,
      formatter: "plaintext",
    },
    columns: columns.map(([title, field, width]) => ({
      title,
      field,
      width,
      headerClick: () => {
        if (
          ["ticks", "kind", "offset", "sequence", "object_name"].includes(field)
        )
          onSort(field === "object_name" ? "object_id" : field);
      },
    })),
  });
  const ready = new Promise((resolve) => table.on("tableBuilt", resolve));
  table.on("rowClick", (_, row) => onSelect(row.getData().event));
  table.on("rowMouseOver", (_, row) =>
    element.dispatchEvent(
      new CustomEvent("event-hover", { detail: row.getData().event }),
    ),
  );
  return {
    async render(page, objects = []) {
      await ready;
      const names = new Map(
        objects.map((o) => [o.object_id, o.name || o.object_id]),
      );
      await table.replaceData(
        page.rows.map((e) => ({
          ticks: e.ticks,
          kind: e.kind,
          actor_name: names.get(e.actor_id) || e.actor_id || "Unknown",
          object_name: names.get(e.object_id) || e.object_id || "—",
          message: e.fields.message || "",
          offset: e.offset,
          sequence: e.sequence,
          event: e,
        })),
      );
    },
    dispose() {
      table.destroy();
    },
    table,
  };
}
