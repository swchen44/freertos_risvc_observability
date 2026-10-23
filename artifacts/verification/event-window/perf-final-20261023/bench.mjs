import { readFile } from 'node:fs/promises';
import { resolve } from 'node:path';
import { createHash } from 'node:crypto';
const {queryEventWindow}=await import(resolve(process.argv[2]));
const dir=resolve('artifacts/verification/event-window/formal/A08-baseline-b1-1-1');
const m=JSON.parse(await readFile(dir+'/manifest.json'));
const start=performance.now();
const r=await queryEventWindow(m,c=>readFile(dir+'/'+c.id+'.json.gz'),{run_id:m.identity.run_id,start:'0',end:m.events,metric:'memory_cycles',event_offset:'0',event_limit:200});
console.log(JSON.stringify({seconds:(performance.now()-start)/1000,events:r.event_count,cycles:r.totals.memory_cycles,result_sha256:createHash('sha256').update(JSON.stringify(r)).digest('hex')}));
