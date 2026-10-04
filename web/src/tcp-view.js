export function selectRows(rows, variant, kind, repeat) {
  return rows.filter(r => (variant==='all'||r.variant===variant) && (kind==='all'||r.kind===kind) && (repeat==='all'||r.repeat===Number(repeat)));
}
export function csvFor(rows, fields) {
 const cell=v=> typeof v==='number'?String(v):'"'+String(v??'').replaceAll('"','""')+'"';
 return [fields.join(','),...rows.map(r=>fields.map(f=>cell(r[f])).join(','))].join('\r\n');
}
