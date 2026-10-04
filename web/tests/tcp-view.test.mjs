import test from 'node:test';
import assert from 'node:assert/strict';
import {selectRows, csvFor} from '../src/tcp-view.js';
const rows=[{variant:'tcp_copy2',kind:'send',repeat:1,instructions:100,bytes:20}, {variant:'tcp_nocopy3',kind:'retransmit',repeat:2,instructions:50,bytes:20}];
test('TCP filters intersect without changing source data',()=>{
 assert.equal(selectRows(rows,'all','send','all').length,1);
 assert.equal(selectRows(rows,'tcp_copy2','retransmit','all').length,0);
 assert.equal(selectRows(rows,'all','all','2')[0].variant,'tcp_nocopy3');
 assert.equal(rows.length,2);
});
test('CSV uses supplied sorted subset and escaped cells',()=>{
 assert.equal(csvFor([{variant:'a,"b',instructions:50}],['variant','instructions']), 'variant,instructions\r\n"a,""b",50');
});
