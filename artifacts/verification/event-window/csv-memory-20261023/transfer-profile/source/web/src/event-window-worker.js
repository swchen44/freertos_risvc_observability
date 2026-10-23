import { queryEventWindow } from "./event-window-data.js";
import { sendEventMessage } from "./event-window-transport.js";
let serial = 0,
  pending = new Map();
onmessage = async ({ data }) => {
  if (data.type === "chunk") {
    const wait = pending.get(data.id);
    if (wait) {
      pending.delete(data.id);
      data.error ? wait.reject(Error(data.error)) : wait.resolve(data.bytes);
    }
    return;
  }
  if (data.type !== "query") return;
  const { manifest, query } = data,
    request_id = query.request_id;
  const loadChunk = (descriptor) =>
    new Promise((resolve, reject) => {
      const id = ++serial;
      pending.set(id, { resolve, reject });
      postMessage({ type: "load", id, descriptor, request_id });
    });
  try {
    const result = await queryEventWindow(
      manifest,
      loadChunk,
      query,
      (message) =>
        sendEventMessage(message, request_id, (payload, transfer) =>
          postMessage(payload, transfer),
        ),
    );
    postMessage({ type: "result", request_id, result });
  } catch (error) {
    postMessage({ type: "error", request_id, error: String(error.message) });
  }
};
