import test from 'node:test';
import assert from 'node:assert/strict';
import {selectTiming, timingCsv, fields} from '../src/timing-view.js';

test('groups stay separate, candidate filter supports an empty result',()=>{
 const rows=[{group:'T3b',label:'baseline'},{group:'T3c-chain',label:'fragmented-pbuf'}];
 assert.deepEqual(selectTiming(rows,'T3b','all'),[rows[0]]);
 assert.deepEqual(selectTiming(rows,'T3b','fragmented-pbuf'),[]);
});
test('CSV preserves displayed order and the measured denominator',()=>{
 const rows=[{group:'T3c-chain',label:'fragmented-pbuf',guest_ns:2468700,baseline:'fragmented-baseline'}, {group:'T3c-chain',label:'fragmented-baseline',guest_ns:2489000}];
 const csv=timingCsv(rows);
 assert.equal(csv.split('\r\n').length,3);
 assert.match(csv.split('\r\n')[1],/fragmented-pbuf/);
 assert.match(csv,/2468700/);
 assert.ok(fields.some(([f])=>f==='l1i_accesses'));
});

test('workload filter preserves paired baseline and CSV request shape',()=>{
 const rows=[{group:'A08',label:'A08-baseline',baseline:'A08-baseline',request_shape:'1460',improvement_pct:0},{group:'A08',label:'A08-pbuf',baseline:'A08-baseline',request_shape:'1460',improvement_pct:8.3},{group:'A07',label:'A07-pbuf',baseline:'A07-baseline'}];
 const selected=selectTiming(rows,'A08','A08-pbuf');
 assert.equal(selected.length,1);
 assert.equal(selected[0].baseline,'A08-baseline');
 assert.equal(selected[0].improvement_pct,8.3);
 assert.match(timingCsv(selected),/1460/);
 assert.ok(fields.some(([f])=>f==='request_shape'));
});
