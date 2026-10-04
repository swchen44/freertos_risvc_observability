import './tcp.css';
import * as echarts from 'echarts';
import {TabulatorFull as Tabulator} from 'tabulator-tables';
import {selectRows,csvFor} from './tcp-view.js';
const $=id=>document.getElementById(id);
const offline=Boolean($('tcp-data').textContent.trim());
if(offline)$('mode').textContent='離線 HTML · 無網路依賴';
const names={tcp_copy2:'2 + copy',tcp_copy3:'3 + copy',tcp_nocopy3:'3 + zero-copy'};
const fields=[['variant','配置'],['repeat','重跑'],['kind','階段'],['bytes','payload bytes'],['instructions','QEMU 指令'],['reads','讀取操作'],['writes','寫入操作'],['l1i_misses','L1I miss'],['l1d_misses','L1D miss'],['l2_misses','L2 miss'],['text_bytes','ELF text bytes']];
const table=new Tabulator('#table',{data:[],columns:fields.map(([field,title])=>({field,title,minWidth:120,sorter:['variant','kind'].includes(field)?'string':'number'})),movableColumns:true,layout:'fitDataStretch',height:260});
const ready=new Promise(resolve=>table.on('tableBuilt',resolve));
const charts=Object.fromEntries(['work','miss','hot'].map(id=>[id,echarts.init($(id),null,{renderer:'svg'})]));
function details(row){
 $('evidence').textContent=JSON.stringify(row,null,2);
 $('hot-title').textContent=`函式熱點 · ${names[row.variant]} · ${row.kind}`;
 const entries=row.hotspots.slice(0,7).reverse();
 charts.hot.setOption({tooltip:{trigger:'axis'},grid:{left:160,right:25,top:15,bottom:30},xAxis:{type:'value',name:'指令'},yAxis:{type:'category',data:entries.map(x=>x.function)},series:[{type:'bar',data:entries.map(x=>x.instructions),itemStyle:{color:'#326c89'}}]},true);
}
table.on('rowClick',(_,row)=>details(row.getData()));
function options(rows,cache){
 return {tooltip:{trigger:'axis'},legend:{bottom:0},grid:{left:65,right:20,top:20,bottom:100},xAxis:{type:'category',data:rows.map(r=>`${names[r.variant]} / ${r.repeat}\n${r.kind}`),axisLabel:{rotate:15}},yAxis:{type:'value',name:cache?'line miss':'instructions'},series:(cache?[['L1I','l1i_misses','#326c89'],['L1D','l1d_misses','#16826c'],['L2','l2_misses','#bd7032']]:[['QEMU 指令','instructions','#16826c']]).map(([name,key,color])=>({name,type:'bar',data:rows.map(r=>r[key]),itemStyle:{color}}))};
}
async function start(data){
 if(data.schema!=='tcp-dashboard-v1')throw Error('不支援的資料格式');
 await ready;
 async function render(){
  window.tcpReady=false;
  const rows=selectRows(data.rows,$('variant').value,$('kind').value,$('repeat').value);
  await table.setData(rows);
  charts.work.setOption(options(rows,false),true);charts.miss.setOption(options(rows,true),true);
  $('status').textContent=`已驗證 9 個 TCP sessions / 45 個 TX 區段 · 目前 ${rows.length} 筆結果`;
  if(rows.length)details(rows[0]);
  window.tcpReady=true;
 }
 ['variant','kind','repeat'].forEach(id=>$(id).addEventListener('change',()=>render().catch(failed)));
 await render();
}
function failed(e){$('status').textContent='載入失敗：'+e.message;window.tcpReady=false;}
$('csv').addEventListener('click',()=>{
 const text=csvFor(table.getData('active'),fields.map(([field])=>field));
 const url=URL.createObjectURL(new Blob(['\ufeff'+text],{type:'text/csv;charset=utf-8'}));
 const a=document.createElement('a');a.href=url;a.download='tcp-comparison.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
});
window.addEventListener('resize',()=>Object.values(charts).forEach(c=>c.resize()));
Promise.resolve().then(()=>offline?JSON.parse($('tcp-data').textContent):fetch('/api/tcp').then(r=>{if(!r.ok)throw Error('API '+r.status);return r.json()})).then(start).catch(failed);
