(() => {
  const records = [];
  window.csvDiagnostics = records;
  let chunks = 0, characters = 0;
  const mark = (stage, extra = {}) => records.push({
    stage, wall_ms: Date.now(), heap: performance.memory?.usedJSHeapSize ?? null,
    chunks, characters, ...extra
  });
  const NativeWorker = window.Worker;
  window.Worker = class extends NativeWorker {
    constructor(...args) {
      super(...args);
      this.addEventListener("message", ({data}) => {
        if(data.type === "csv") {
          chunks++; characters += data.text?.length ?? data.bytes?.byteLength ?? 0;
          if(chunks === 1 || chunks % 32 === 0) mark("csv-received");
        }
        if(data.type === "result") mark("worker-result");
      });
    }
  };
  const create = URL.createObjectURL.bind(URL);
  URL.createObjectURL = blob => {
    if(blob.type.startsWith("text/csv")) mark("csv-blob-url", {bytes: blob.size});
    return create(blob);
  };
  const click = HTMLAnchorElement.prototype.click;
  HTMLAnchorElement.prototype.click = function(...args) {
    if(this.download.endsWith(".csv")) mark("download-click");
    return click.apply(this,args);
  };
  mark("installed");
  return true;
})()
