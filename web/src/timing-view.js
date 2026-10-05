import {csvFor} from './tcp-view.js';
export const fields=[['group','比較組'],['label','候選'],['baseline','同組基準'],['repeats','重跑次數'],['guest_ns','模型時間 ns'],['improvement_pct','時間改善 %'],['instructions','Guest 指令'],['cycles','記憶體 cycles'],['stack_cycles','Stack 區間 cycles'],['harness_cycles','其他區間 cycles'],['text','ELF text bytes'],...['l1i','l1d','l2'].flatMap(l=>[['accesses','查詢'],['misses','miss'],['miss_pct','miss %'],['compulsory','首次'],['conflict','衝突'],['capacity','容量']].map(([f,n])=>[`${l}_${f}`,`${l.toUpperCase()} ${n}`]))];
export const selectTiming=(rows,group,label)=>rows.filter(r=>r.group===group&&(label==='all'||r.label===label));
export const timingCsv=rows=>csvFor(rows,fields.map(([key])=>key));
