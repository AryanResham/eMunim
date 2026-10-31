import { useEffect, useState } from 'react'
import { API_BASE, listDocuments, summary } from '@/api/backend'
import type { SavedDocument } from '@/types/upload'

export function Records({dashboard=false}:{dashboard?:boolean}) {
  const [rows,setRows]=useState<SavedDocument[]>([])
  const [total,setTotal]=useState(0)
  const [page,setPage]=useState(0)
  const [search,setSearch]=useState('')
  const [error,setError]=useState('')
  const [selected,setSelected]=useState<SavedDocument|null>(null)
  const [stats,setStats]=useState<Awaited<ReturnType<typeof summary>>|null>(null)
  const [loading,setLoading]=useState(true)
  useEffect(()=>{
    let active=true
    Promise.all([listDocuments(new URLSearchParams({search,offset:String(page*25)}).toString()),summary()])
      .then(([data,counts])=>{if(active){setRows(data.items);setTotal(data.total);setStats(counts);setError('')}})
      .catch(e=>{if(active)setError(e.message)})
      .finally(()=>{if(active)setLoading(false)})
    return ()=>{active=false}
  },[search,page])
  return <section className="panel">
    <h2>{dashboard?'Document overview':'Saved records'}</h2>
    {error&&<p role="alert" className="alert error">{error}</p>}
    {stats&&dashboard&&<><div className="stats"><div><strong>{stats.count}</strong><p>Reviewed documents</p></div><div><strong>{stats.with_issues}</strong><p>Saved with unresolved issues</p></div></div>
      <p className="muted">{stats.note}</p><div className="stats">{Object.entries(stats.by_type).map(([type,g])=><div key={type}><strong>{type.replaceAll('_',' ')}</strong><p>{g.count} documents</p><p>Printed amounts: {g.printed_amount_total} ({g.amount_count} parsed)</p></div>)}</div></>}
    <div className="actions"><input aria-label="Search saved records" placeholder="Search field values…" value={search} onChange={e=>{setLoading(true);setSearch(e.target.value);setPage(0)}}/><a className="button" href={API_BASE+'/documents/export/csv?'+new URLSearchParams({search})}>Export CSV</a></div>
    {loading?<p>Loading records…</p>:rows.length===0?<p>No saved records yet.</p>:<div className="table-scroll"><table><thead><tr><th>Saved</th><th>Type</th><th>Pipeline</th><th>Status</th><th/></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{new Date(r.created_at).toLocaleString()}</td><td>{r.doc_type}</td><td>{r.pipeline}</td><td>{r.status.replaceAll('_',' ')}</td><td><button onClick={()=>setSelected(r)}>View</button></td></tr>)}</tbody></table></div>}
    <div className="actions"><button disabled={page===0} onClick={()=>{setLoading(true);setPage(p=>p-1)}}>Previous</button><span>{total} records · page {page+1}</span><button disabled={(page+1)*25>=total} onClick={()=>{setLoading(true);setPage(p=>p+1)}}>Next</button></div>
    {selected&&<div className="record-detail"><div className="actions"><h3>Reviewed record</h3><button onClick={()=>setSelected(null)}>Close</button></div><img className="invoice-preview" src={API_BASE+'/files/'+selected.file_id} alt="Saved invoice"/>
      <dl>{selected.fields.map(f=><div key={f.key}><dt>{f.label} · {f.source}</dt><dd>{f.value??'Absent'}</dd></div>)}</dl>
      <details><summary>Original values and audit history</summary><pre>{JSON.stringify({original:selected.original_fields,audit:selected.audit,validation:selected.validation,metadata:selected.metadata},null,2)}</pre></details></div>}
  </section>
}
