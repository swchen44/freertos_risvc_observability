import './hotspot.css';
import * as echarts from 'echarts';
import {TabulatorFull as Tabulator} from 'tabulator-tables';
import {selectRun,selectFacts,summarizeFunctions,rankFunctions,pcRows,hotspotCsv,sumFacts,metricValue} from './hotspot-view.js';
const $=id=>document.getElementById(id),offline=Boolean($('hotspot-data').textContent.trim());
if(offline)$('deployment').textContent='離線 HTML · 無網路依賴';
const palette=['#326c89','#16826c','#bd7032','#785996','#8c5353'];
const safe=cell=>{const el=document.createElement('span');const v=cell.getValue();el.textContent=typeof v==='number'?(Number.isInteger(v)?v.toLocaleString():v.toFixed(3)):(v??'—');return el;};
const columns=[['name','函式'],['role','角色'],['value','選定指標'],['run_percent','占 run %'],['filtered_percent','占篩選 %'],['instructions','指令'],['memory_cycles','Memory cycles']].map(([field,title])=>({field,title,formatter:safe,sorter:['name','role'].includes(field)?'string':'number',minWidth:140}));
const table=new Tabulator('#functions-table',{data:[],columns,movableColumns:true,layout:'fitDataStretch',height:320});
const pcTable=new Tabulator('#pc-table',{data:[],columns:[['pc_hex','PC'],['instructions','Self instructions'],['memory_cycles','Memory cycles']].map(([field,title])=>({field,title,formatter:safe,minWidth:180})),layout:'fitDataStretch',height:230});
const ready=Promise.all([table,pcTable].map(t=>new Promise(resolve=>t.on('tableBuilt',resolve))));
const charts=Object.fromEntries(['rank','delta','cost','miss'].map(k=>[k,echarts.init($(k+'-chart'),null,{renderer:'svg'})]));
let bundle,run,filtered,metric,allRows,generation=0;
function options(id,items,value){const el=$(id);el.replaceChildren(...items.map(([key,label])=>new Option(label,key)));if(items.some(([key])=>String(key)===String(value)))el.value=value;}
function selections(){return {variant:$('variant').value,family:$('family').value,mode:Number($('mode').value),repeat:Number($('repeat').value)};}
function resetChoices(changed){
 let reports=bundle.reports.filter(r=>r.identity.variant===$('variant').value);
 const family=$('family').value;options('family',[...new Set(reports.map(r=>r.identity.family))].map(k=>[k,k==='b1'?'B1 · unknown context':'B2 · exact context']),family||'b1');
 reports=reports.filter(r=>r.identity.family===$('family').value);
 options('mode',[...new Set(reports.map(r=>r.identity.mode))].sort().map(m=>[m,m?'injection model':'control shadow']),$('mode').value||'1');
 reports=reports.filter(r=>String(r.identity.mode)===$('mode').value);
 options('repeat',[...new Set(reports.map(r=>r.identity.repeat))].sort().map(r=>[r,String(r)]),$('repeat').value||'1');
 run=selectRun(bundle,selections());
 options('context',[['all','全部 Context'],...Object.entries(run.context_labels).map(([k,v])=>[k,v.label])],changed?'all':$('context').value);
 options('role',[['all','全部角色'],...[...new Set(run.facts.map(f=>f.role))].sort().map(k=>[k,k])],changed?'all':$('role').value);
 if(changed){$('function-query').value='';$('source-evidence').textContent='已切換 run，請重新選擇函式。';$('pc-heading').textContent='點選函式，查看 PC 與來源';pcTable.clearData();}
}
function bars(chart,names,values,unit,colors){chart.setOption({animation:false,tooltip:{trigger:'axis',renderMode:'richText',valueFormatter:v=>`${v} ${unit}`},grid:{left:165,right:35,top:20,bottom:40},xAxis:{type:'value',name:unit},yAxis:{type:'category',inverse:true,data:names,axisLabel:{width:145,overflow:'truncate'}},series:[{type:'bar',data:values.map((value,i)=>({value,itemStyle:{color:colors?.[i]||palette[0]}}))}]},true);}
function compareRows(){
 const pair=bundle.pairs[run.identity.run_id];if(!pair)return {rows:[],note:'選擇 pbuf 候選查看 baseline 差異。'};
 const baseline=bundle.reports.find(r=>r.identity.run_id===pair.baseline_run);
 let ctx=$('context').value;
 if(ctx!=='all'){
   const key=run.context_labels[ctx]?.pair_key,matches=Object.entries(baseline.context_labels).filter(([,v])=>key&&v.pair_key===key);
   if(matches.length!==1)return {rows:[],note:'此 context 無唯一 baseline 對應；差異 unavailable。'};ctx=matches[0][0];
 }
 const bf=selectFacts(baseline,{context:ctx,role:$('role').value,query:$('function-query').value});
 const bm=new Map(summarizeFunctions(baseline,bf,metric).map(r=>[r.id,r]));const cm=new Map(allRows.map(r=>[r.id,r]));
 const deltas=[];let unknown=0;
 for(const p of pair.functions){
  if(p.status!=='matched'){unknown++;continue;}
  const a=bm.get(p.baseline[0]),b=cm.get(p.candidate[0]);
  if(!a||!b){unknown++;continue;}
  deltas.push({name:b.name,value:b.value-a.value});
 }
 deltas.sort((a,b)=>Math.abs(b.value)-Math.abs(a.value));
 return {rows:deltas.slice(0,Number($('top-n').value)),note:`candidate − baseline；正值增加。${unknown} 組 unmatched／ambiguous／篩選缺方不計算 delta。`};
}
async function render(){
 const start=performance.now();window.hotspotReady=false;$('csv').disabled=true;
 metric=$('metric').value==='misses'?$('cache-level').value+'.misses':$('metric').value;
 filtered=selectFacts(run,{context:$('context').value,role:$('role').value,query:$('function-query').value});
 allRows=summarizeFunctions(run,filtered,metric);
 const ranking=rankFunctions(allRows,{field:'value',direction:'desc',topN:Number($('top-n').value)});
 await table.replaceData(ranking.allSorted);table.setSort('value','desc');
 const totals=sumFacts(filtered);$('run-cost').textContent=metricValue(run.totals,metric).toLocaleString();$('filtered-cost').textContent=metricValue(totals,metric).toLocaleString();
 const unresolved=run.facts.filter(f=>f.role==='unresolved').reduce((n,f)=>n+f.memory_cycles,0);
 $('unresolved').textContent=run.totals.memory_cycles?(100*unresolved/run.totals.memory_cycles).toFixed(3)+'%':'—';$('quality').textContent=run.context_quality;
 $('hotspot-status').textContent=`${run.identity.run_id} · ${allRows.length} 個函式 · ${run.cost_semantics} · ${metric}`;
 $('rank-note').textContent=`顯示 ${ranking.visible.length} / ${allRows.length} 個函式；Other 保留其餘成本。比例分母不受 Top-N 影響。`;
 const ranked=[...ranking.visible];if(ranking.totalRows>ranked.length)ranked.push({name:'Other',value:ranking.other.value});
 bars(charts.rank,ranked.map(r=>r.name),ranked.map(r=>r.value),metric);
 const delta=compareRows();$('delta-note').textContent=delta.note;bars(charts.delta,delta.rows.map(r=>r.name),delta.rows.map(r=>r.value),metric,delta.rows.map(r=>r.value>0?'#bd7032':'#16826c'));
 bars(charts.cost,Object.keys(totals.cost_cycles),Object.values(totals.cost_cycles),'cycles',palette);
 const level=$('cache-level').value,miss=totals.cache[level]||{},keys=['compulsory','conflict','capacity'];bars(charts.miss,keys,keys.map(k=>miss[k]||0),level+' misses',palette);
 $('manifest').textContent=JSON.stringify({identity:run.identity,evidence:run.evidence,profile:run.profile,manifest_sha256:bundle.manifest_sha256},null,2);
 $('csv').disabled=false;window.hotspotReady=true;window.hotspotLastRenderMs=performance.now()-start;
}
table.on('rowClick',async(e,row)=>{const r=row.getData();$('pc-heading').textContent=r.name+' · PC self cost';await pcTable.replaceData(pcRows(run,filtered,r.id));$('source-evidence').textContent=JSON.stringify({owner:run.owners[r.id],elf_sha256:run.evidence.elf_sha256},null,2);});
pcTable.on('rowClick',(e,row)=>{$('source-evidence').textContent=JSON.stringify({pc:row.getData().pc_hex,frames:row.getData().source,elf_sha256:run.evidence.elf_sha256},null,2);});
$('csv').onclick=()=>{const rows=table.getRows('active').map(r=>r.getData());const metadata={...run.identity,context:$('context').value,role_filter:$('role').value,metric,metric_units:metric==='instructions'?'instructions':metric==='accounted_model_ns'?'ns':metric.endsWith('misses')?'misses':'cycles',context_quality:run.context_quality,profile_sha256:run.evidence.profile_sha256,manifest_sha256:bundle.manifest_sha256};const url=URL.createObjectURL(new Blob([hotspotCsv(rows,metadata)],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='hotspots.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
function failed(e){window.hotspotReady=false;$('csv').disabled=true;$('hotspot-status').textContent='載入失敗：'+e.message;table.clearData();pcTable.clearData();for(const c of Object.values(charts))c.clear();}
async function loadWorkload(){const token=++generation;window.hotspotReady=false;$('csv').disabled=true;try{const data=offline?JSON.parse($('hotspot-data').textContent):await fetch('/api/hotspots/'+$('workload').value).then(r=>{if(!r.ok)throw Error('來源驗證失敗');return r.json();});if(token!==generation)return;bundle=data;if(data.schema!=='hotspot-workload-v1')throw Error('不支援的 schema');resetChoices(true);await render();}catch(e){failed(e);}}
for(const id of ['variant','family','mode','repeat'])$(id).onchange=()=>{try{resetChoices(true);render().catch(failed);}catch(e){failed(e);}};
for(const id of ['context','role','metric','cache-level','top-n'])$(id).onchange=()=>render().catch(failed);
$('function-query').oninput=()=>render().catch(failed);$('workload').onchange=loadWorkload;
window.addEventListener('resize',()=>Object.values(charts).forEach(c=>c.resize()));
(async()=>{await ready;if(offline){const data=JSON.parse($('hotspot-data').textContent);options('workload',[[data.workload,data.workload]],data.workload);}else{const response=await fetch('/api/hotspots');if(!response.ok)throw Error('Catalog unavailable');const catalog=await response.json();options('workload',catalog.workloads.map(w=>[w.id,w.id]),'A02');}await loadWorkload();})().catch(failed);
