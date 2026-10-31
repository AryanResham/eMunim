import { useEffect, useState } from 'react'
import { API_BASE, request } from '@/api/backend'

type PipelineMetrics = {documents:number;failures:number;micro_field_f1:number|null;macro_field_f1:number|null;complete_document_accuracy:number|null;hosted_attempts:number;review:{validation_review:{review_rate:number|null;accepted_error_rate:number|null}}}
type Report = {status:string;run_id?:string;cohort?:string;documents?:number;pipelines:Record<string,PipelineMetrics>;unavailable_metrics?:{metric:string;reason:string}[];limitations?:string[];files:string[];progress?:{phase?:string;status?:string;error?:string};pilot_progress?:{phase?:string;completed_documents?:number;total_documents?:number};checkpoint_tests?:Record<string,{documents:number;entity_f1:number;complete_document_accuracy:number}>}
const percent = (value:number|null|undefined) => value==null?'Unavailable':(value*100).toFixed(2)+'%'

export function Research() {
  const [data,setData]=useState<Report|null>(null)
  const [error,setError]=useState('')
  function refresh(){request<Report>('/research/latest').then(result=>{setData(result);setError('')}).catch(e=>setError(e.message))}
  useEffect(()=>{let active=true;const load=()=>request<Report>('/research/latest').then(result=>{if(active){setData(result);setError('')}}).catch(e=>{if(active)setError(e.message)});load();const interval=setInterval(load,15000);return()=>{active=false;clearInterval(interval)}},[])
  return <section className="panel"><h2>Research benchmarks</h2><p>Measured results from saved runs. Synthetic and public benchmarks do not establish accuracy on real Indian MSME documents.</p>
    <button onClick={refresh}>Refresh results</button>{error&&<p role="alert" className="alert error">{error}</p>}
    {!data?<p>Loading benchmark status…</p>:<>
      <div className="stats"><div><strong>{data.progress?.status??data.status}</strong><p>Run status</p></div><div><strong>{data.documents??'Unavailable'}</strong><p>Live comparison documents</p></div></div>
      {data.progress?.phase&&<p>Current phase: {data.progress.phase.replaceAll('_',' ')}</p>}
      {data.pilot_progress&&<p>{data.pilot_progress.phase}: {data.pilot_progress.completed_documents??0}/{data.pilot_progress.total_documents??data.documents??'—'} documents</p>}
      {data.progress?.error&&<p role="alert" className="alert error">{data.progress.error}</p>}
      {data.cohort&&<p>Cohort: {data.cohort.replaceAll('_',' ')}</p>}
      {Object.values(data.pipelines).some(m=>m.failures>0)&&<p className="alert error">Some pipeline runs failed or returned degraded results. Full-cohort scores include these cases and cannot establish a clean model-quality ranking.</p>}
      {data.limitations&&<details><summary>Benchmark limitations</summary><ul>{data.limitations.map(item=><li key={item}>{item}</li>)}</ul></details>}
      {Object.keys(data.pipelines).length>0&&<div className="table-scroll"><table><thead><tr><th>Pipeline</th><th>N</th><th>Micro field F1</th><th>Macro field F1</th><th>Complete documents</th><th>Review rate (B)</th><th>Accepted error rate</th><th>Failures</th><th>Hosted attempts</th></tr></thead><tbody>
        {Object.entries(data.pipelines).map(([name,m])=><tr key={name}><td>{name.replaceAll('_',' ')}</td><td>{m.documents}</td><td>{percent(m.micro_field_f1)}</td><td>{percent(m.macro_field_f1)}</td><td>{percent(m.complete_document_accuracy)}</td><td>{percent(m.review.validation_review.review_rate)}</td><td>{percent(m.review.validation_review.accepted_error_rate)}</td><td>{m.failures}</td><td>{m.hosted_attempts}</td></tr>)}
      </tbody></table></div>}
      {data.checkpoint_tests&&<><h3>Held-out checkpoint tests</h3><p>Synthetic checkpoint tests use generator-provided text and boxes. Their scores are separate from production-OCR results. FUNSD and SROIE evaluate different public tasks.</p><div className="table-scroll"><table><thead><tr><th>Task / document type</th><th>Documents</th><th>Entity F1</th><th>Complete documents</th></tr></thead><tbody>{Object.entries(data.checkpoint_tests).map(([name,m])=><tr key={name}><td>{name.replaceAll('_',' ')}</td><td>{m.documents}</td><td>{percent(m.entity_f1)}</td><td>{percent(m.complete_document_accuracy)}</td></tr>)}</tbody></table></div></>}
      {data.unavailable_metrics&&<><h3>Evidence still required</h3><ul>{data.unavailable_metrics.map(item=><li key={item.metric}><strong>{item.metric}:</strong> {item.reason}</li>)}</ul></>}
      {data.files.length>0&&<><h3>Download measured artifacts</h3><div className="actions">{data.files.map(file=><a className="button" key={file} href={API_BASE+'/research/files/'+encodeURIComponent(file)}>{file}</a>)}</div></>}
    </>}
  </section>
}
