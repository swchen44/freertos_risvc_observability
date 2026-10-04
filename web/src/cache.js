import './cache.css';
import * as echarts from 'echarts';
import {TabulatorFull as Tabulator} from 'tabulator-tables';
const $ = id => document.getElementById(id);
const node=$('cache-data');
const offline=Boolean(node.textContent.trim());
if(offline) $('mode').textContent='離線 HTML · 無網路依賴';
let filtered=[];
const columns=[['run','案例'],['kib','L1D KiB'],['reads','讀取'],['writes','寫入'],['misses','L1D miss'],['l2miss','L2 miss'],['used','使用比例 %'],['evicted','已逐出未用 bytes'],['resident','仍駐留未觀測 bytes']].map(([field,title])=>({field,title,sorter:field==='run'?'string':'number',minWidth:120}));
const table=new Tabulator('#table',{data:[],columns,layout:'fitDataStretch',height:280,movableColumns:true});
const tableReady=new Promise(resolve=>table.on('tableBuilt',resolve));
table.on('rowClick',(_,row)=>{$('evidence').textContent=JSON.stringify(row.getData().evidence,null,2)});
const miss=echarts.init($('miss'),null,{renderer:'svg'}), use=echarts.init($('use'),null,{renderer:'svg'});
const pct=n=>Math.round(n*10000)/100;
function chartOptions(rows,spatial){return {tooltip:{trigger:'axis'},legend:{bottom:0},grid:{left:65,right:20,top:20,bottom:85},xAxis:{type:'category',data:rows.map(r=>r.run.replace('cache_','')),axisLabel:{rotate:20}},yAxis:{type:'value',max:spatial?100:undefined,name:spatial?'%':'miss'},series:spatial?[{name:'已使用 bytes 比例',type:'bar',data:rows.map(r=>r.used),itemStyle:{color:'#16826c'}}]:[{name:'L1D miss',type:'bar',data:rows.map(r=>r.misses),itemStyle:{color:'#bd7032'}},{name:'L2 data miss',type:'bar',data:rows.map(r=>r.l2miss),itemStyle:{color:'#326c89'}}]};}
function start(data){
 if(data.schema!=='cache-dashboard-v1')throw Error('不支援的 cache schema');
 const render=()=>{
  filtered=data.rows.filter(r=>r.l1.geometry.size===Number($('size').value)&&($('variant').value==='all'||r.run.startsWith($('variant').value))&&($('repeat').value==='all'||r.run.endsWith('-'+$('repeat').value))).map(r=>({run:r.run,kib:r.l1.geometry.size/1024,reads:r.l1.reads,writes:r.l1.writes,misses:r.l1.misses,l2miss:r.l2.misses,used:pct(r.l1.spatial.observed_utilization),evicted:r.l1.spatial.evicted_unused_bytes,resident:r.l1.spatial.resident_unobserved_bytes,evidence:r}));
  table.setData(filtered);miss.setOption(chartOptions(filtered,false),true);use.setOption(chartOptions(filtered,true),true);
  $('status').textContent=`已驗證 ${data.rows.length} 筆結果 · 目前 ${filtered.length} 筆 · cold / 64-byte / 4-way / LRU`;
  $('evidence').textContent='點選一筆資料查看來源。';window.cacheReady=true;
 };
 ['size','variant','repeat'].forEach(id=>$(id).addEventListener('change',render));render();
}
$('csv').addEventListener('click',()=>{
 const rows=table.getData('active');const fields=columns.map(c=>c.field);
 const csv=[fields.join(','),...rows.map(r=>fields.map(f=>JSON.stringify(r[f])).join(','))].join('\r\n');
 const url=URL.createObjectURL(new Blob(['\ufeff'+csv],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='cache-comparison.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
window.addEventListener('resize',()=>{miss.resize();use.resize()});
Promise.resolve().then(async()=>offline?JSON.parse(node.textContent):await fetch('/api/cache').then(r=>{if(!r.ok)throw Error('cache API '+r.status);return r.json()})).then(async data=>{await tableReady;start(data)}).catch(e=>{$('status').textContent='載入失敗：'+e.message});
