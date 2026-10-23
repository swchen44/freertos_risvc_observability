import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync } from 'node:fs';
import { MessageChannel } from 'node:worker_threads';
import { once } from 'node:events';

async function transport() {
  const url = new URL('../src/event-window-transport.js', import.meta.url);
  assert.ok(existsSync(url), 'CSV transport must transfer encoded bytes');
  return import(url);
}

test('CSV preserves UTF-8 bytes and transfers ownership with request identity', async () => {
  const { sendEventMessage } = await transport();
  const { port1, port2 } = new MessageChannel();
  const text = '"臺灣😀","a""b\nc","9007199254740993"\r\n';
  let sent;
  try {
    const received = once(port2, 'message');
    sendEventMessage({ type: 'csv', text }, 17, (message, transfer) => {
      sent = message.bytes;
      port1.postMessage(message, transfer);
    });
    assert.equal(sent.byteLength, 0, 'sender must not retain transferred buffer');
    const [message] = await received;
    assert.equal(message.request_id, 17);
    assert.equal(message.type, 'csv');
    assert.equal(message.text, undefined);
    assert.deepEqual(message.bytes, new TextEncoder().encode(text));
    assert.equal(await new Blob([message.bytes]).text(), text);
  } finally {
    port1.close(); port2.close();
  }
});

test('progress and empty CSV retain their protocol meaning', async () => {
  const { sendEventMessage } = await transport();
  let message;
  sendEventMessage({ type: 'progress', done: 3, total: 7 }, 18,
    (value) => { message = value; });
  assert.deepEqual(message, { type: 'progress', done: 3, total: 7, request_id: 18 });
  sendEventMessage({ type: 'csv', text: '' }, 19,
    (value) => { message = value; });
  assert.equal(message.bytes.byteLength, 0);
  assert.equal(message.request_id, 19);
});
