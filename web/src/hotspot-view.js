export function selectRun(bundle, selection) {
  const rows=bundle.reports.filter(r=>Object.entries(selection).every(([k,v])=>r.identity[k]===v));
  if(rows.length!==1) throw Error('Run unavailable'); return rows[0];
}
export function selectFacts(report,{context='all',role='all',query=''}={}) {
  return report.facts.filter(f=>(context==='all'||f.context===context)&&(role==='all'||f.role===role)&&
    (report.owners[f.function_id]?.function||'unresolved').toLowerCase().includes(query.toLowerCase()));
}
export function metricValue(row,metric) {
  if(['instructions','memory_cycles','accounted_model_ns'].includes(metric)) return row[metric]??0;
  const [level,key]=metric.split('.');
  if(['l1i','l1d','l2'].includes(level)&&['accesses','misses','compulsory','conflict','capacity'].includes(key))return row.cache?.[level]?.[key]??0;
  throw Error('Unsupported metric');
}
export function sumFacts(facts) {
  const result={instructions:0,memory_cycles:0,accounted_model_ns:0,cost_cycles:{},cache:{}};
  for(const f of facts){
    for(const k of ['instructions','memory_cycles','accounted_model_ns'])result[k]+=f[k]||0;
    for(const [k,v] of Object.entries(f.cost_cycles||{}))result.cost_cycles[k]=(result.cost_cycles[k]||0)+v;
    for(const [level,counts] of Object.entries(f.cache||{})){
      result.cache[level]??={};for(const [k,v]of Object.entries(counts)) result.cache[level][k]=(result.cache[level][k]||0)+v;
    }
  }return result;
}
export function summarizeFunctions(report,facts,metric) {
  const groups=new Map();for(const f of facts){if(!groups.has(f.function_id))groups.set(f.function_id,[]);groups.get(f.function_id).push(f);}
  const runDen=metricValue(report.totals,metric),filterDen=metricValue(sumFacts(facts),metric);
  return [...groups].map(([id,fs])=>{
    const totals=sumFacts(fs),value=metricValue(totals,metric),owner=report.owners[id];
    return {id,name:owner?.function||'unresolved',role:fs[0].role,...totals,value,metric,
      run_denominator:runDen,filtered_denominator:filterDen,run_percent:runDen?100*value/runDen:null,
      filtered_percent:filterDen?100*value/filterDen:null};
  });
}
export function rankFunctions(rows,{field='value',direction='desc',topN=10}={}) {
  if(!Number.isInteger(topN)||topN<1)throw Error('Invalid top N');
  const allSorted=[...rows].sort((a,b)=>{
    if(a[field]==null)return b[field]==null?String(a.id).localeCompare(String(b.id)):1;
    if(b[field]==null)return -1;
    const d=typeof a[field]==='number'?a[field]-b[field]:String(a[field]).localeCompare(String(b[field]));
    return (direction==='desc'?-d:d)||String(a.id).localeCompare(String(b.id));
  });
  const rest=allSorted.slice(topN),other=sumFacts(rest);other.value=rest.reduce((n,r)=>n+r.value,0);
  return {allSorted,visible:allSorted.slice(0,topN),other,totalRows:rows.length};
}
export function pcRows(report,facts,functionId){
 const groups=new Map();for(const f of facts.filter(f=>f.function_id===functionId)){if(!groups.has(f.pc))groups.set(f.pc,[]);groups.get(f.pc).push(f);}
 return [...groups].map(([pc,fs])=>({pc,pc_hex:'0x'+pc.toString(16),...sumFacts(fs),source:report.source_lines?.[String(pc)]||[]}));
}
function flatten(obj,prefix='',out={}){
 for(const [k,v]of Object.entries(obj)){const key=prefix?prefix+'_'+k:k;if(v&&typeof v==='object'&&!Array.isArray(v))flatten(v,key,out);else out[key]=Array.isArray(v)?JSON.stringify(v):v;}return out;
}
export function hotspotCsv(rows,metadata){
 const flat=rows.map(r=>({...flatten(metadata),...flatten(r)}));
 const fields=[...new Set(flat.flatMap(Object.keys))];if(!fields.length)fields.push('run_id','name','value');
 const escape=v=>{let s=v==null?'':String(v);if(typeof v==='string'&&/^[\s]*[=+\-@]|^[\t\r\n]/.test(s))s="'"+s;return '"'+s.replaceAll('"','""')+'"';};
 return '\ufeff'+[fields.map(escape).join(','),...flat.map(r=>fields.map(f=>escape(r[f])).join(','))].join('\r\n')+'\r\n';
}
