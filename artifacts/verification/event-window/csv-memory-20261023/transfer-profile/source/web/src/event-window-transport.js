const encoder = new TextEncoder();

export function sendEventMessage(message, request_id, send) {
  if (message.type === "csv") {
    const bytes = encoder.encode(message.text);
    send({ type: "csv", bytes, request_id }, [bytes.buffer]);
  } else {
    send({ ...message, request_id });
  }
}
