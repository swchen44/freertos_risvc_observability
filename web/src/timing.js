import './timing.css';
import * as echarts from 'echarts';
import {TabulatorFull as Tabulator} from 'tabulator-tables';
import {fields,selectTiming,timingCsv} from './timing-view.js';
const $=id=>document.getElementById(id);
const offline=Boolean($('timing-data').textContent.trim());
if(offline)$('mode').textContent='離線 HTML · 無網路依賴';
const table=new Tabulator('#table',{data:[],columns:fields.map(([field,title])=>({field,title,minWidth:135,sorter:['group','label','baseline'].includes(field)?'string':'number',formatter:field.endsWith('_pct')?cell=>cell.getValue().toFixed(3):undefined})),movableColumns:true,layout:'fitDataStretch',height:260});
const ready=new Promise(resolve=>table.on('tableBuilt',resolve));
const charts=Object.fromEntries(['time','work','miss','cost'].map(id=>[id,echarts.init($(id),null,{renderer:'svg'})]));
const palette=['#326c89','#16826c','#bd7032','#785996','#8c5353'];
function option(rows,series,yAxis){return {animation:false,tooltip:{trigger:'axis'},legend:{bottom:0},grid:{left:70,right:65,top:45,bottom:90},xAxis:{type:'category',data:rows.map(r=>r.label),axisLabel:{interval:0,rotate:12}},yAxis,series};}
function series(rows,key,name,i,extra={}){return {name,type:'bar',data:rows.map(r=>r[key]),itemStyle:{color:palette[i]},...extra};}
function details(row,data){
 $('detail-title').textContent=`候選細節 · ${row.label}`;
 $('detail-summary').textContent=`同組基準：${row.baseline}\n完整模型時間：${row.guest_ms.toFixed(4)} ms；改善 ${row.improvement_pct.toFixed(3)}%\n重跑 ${row.repeats} 次；${row.ticks} ticks；ELF text ${row.text.toLocaleString()} bytes`+(row.request_phase_instructions?`\n兩次 request_rx 指令：${row.request_phase_instructions.join(' / ')}`:'')+(row.request_pbufs?`\npbuf chain：${row.request_pbufs[0].lengths.join(' + ')} bytes`:'');
 const t=document.createElement('table');const head=t.createTHead().insertRow();
 for(const name of ['函式','大小']){const th=document.createElement('th');th.textContent=name;head.append(th);}
 const body=t.createTBody();for(const [name,value] of Object.entries(row.function_sizes)){const tr=body.insertRow();tr.insertCell().textContent=name;tr.insertCell().textContent=value.size;}
 $('functions').replaceChildren(t);
 $('evidence').textContent=JSON.stringify({row,source_hashes:data.sources,profile:data.profile,environment:data.environment},null,2);
}
function failed(error){window.timingReady=false;$('csv').disabled=true;$('status').textContent='載入失敗：'+error.message;}
async function start(data){
 if(data.schema!=='timing-dashboard-v1')throw Error('不支援的資料格式');
 await ready;
 table.on('rowClick',(_,row)=>details(row.getData(),data));
 function candidates(){const options=[new Option('全部候選','all'),...data.rows.filter(r=>r.group===$('group').value).map(r=>new Option(r.label,r.label))];$('candidate').replaceChildren(...options);}
 async function render(){
  window.timingReady=false;
  const rows=selectTiming(data.rows,$('group').value,$('candidate').value),level=$('level').value;
  await table.setData(rows);
  charts.time.setOption(option(rows,[series(rows,'guest_ms','完整模型時間 ms',0,{label:{show:true,position:'top',formatter:p=>p.value.toFixed(4)+' ms'}})],{type:'value',name:'ms',min:0}),true);
  charts.work.setOption(option(rows,[series(rows,'instructions','Guest 指令',0),series(rows,'cycles','記憶體 cycles',1,{yAxisIndex:1})],[{type:'value',name:'指令',min:0},{type:'value',name:'cycles',min:0}]),true);
  const miss=option(rows,['compulsory','conflict','capacity'].map((k,i)=>series(rows,`${level}_${k}`,['首次','衝突','容量'][i],i,{stack:'3c'})),{type:'value',name:'miss 次數',min:0});
  miss.tooltip={trigger:'axis',formatter:params=>{const r=rows[params[0].dataIndex];return `${r.label}<br>${level.toUpperCase()}: ${r[level+'_misses']} / ${r[level+'_accesses']} = ${r[level+'_miss_pct'].toFixed(3)}%<br>`+params.map(p=>`${p.seriesName}: ${p.value}`).join('<br>')}};
  charts.miss.setOption(miss,true);$('miss-title').textContent=level.toUpperCase()+' miss 歸因';
  charts.cost.setOption(option(rows,['l1i','l1d','l2','ram_read','ram_write'].map((k,i)=>({name:k,type:'bar',stack:'cost',data:rows.map(r=>r.cost_cycles[k]),itemStyle:{color:palette[i]}})),{type:'value',name:'memory cycles',min:0}),true);
  if(rows.length)details(rows[0],data);else{$('functions').replaceChildren();$('detail-summary').textContent='沒有符合的資料';$('evidence').textContent='';}
  $('status').textContent=`${$('group').value} · ${rows.length} 筆候選 · 來源 SHA-256 已核對 · baseline 不受候選篩選影響`;
  $('csv').disabled=!rows.length;window.timingReady=true;
 }
 candidates();$('group').addEventListener('change',()=>{candidates();render().catch(failed)});
 for(const id of ['candidate','level'])$(id).addEventListener('change',()=>render().catch(failed));
 await render();
}
$('csv').addEventListener('click',()=>{const url=URL.createObjectURL(new Blob(['\ufeff'+timingCsv(table.getData('active'))],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='small-cache-comparison.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)});
window.addEventListener('resize',()=>Object.values(charts).forEach(c=>c.resize()));
Promise.resolve().then(()=>offline?JSON.parse($('timing-data').textContent):fetch('/api/timing').then(r=>{if(!r.ok)throw Error('API '+r.status);return r.json()})).then(start).catch(failed);
