import { useEffect, useState } from 'react'
import { capabilities } from '@/api/backend'
import type { Capabilities } from '@/types/upload'
export function Settings() {
  const [data,setData]=useState<Capabilities|null>(null)
  const [error,setError]=useState('')
  useEffect(()=>{capabilities().then(setData).catch(e=>setError(e.message))},[])
  return <section className="panel"><h2>Service configuration</h2><p>Configure credentials in backend/.env and restart the backend. Keys are never sent to this browser.</p>
    {error&&<p className="alert error">{error}</p>}{data&&<><dl><dt>Google Vision OCR</dt><dd>{data.ocr_configured?'Configured':'Missing API key'}</dd><dt>Hosted vision</dt><dd>{data.hosted_configured?data.hosted_model:'Configure GROQ_API_KEY and HOSTED_VLM_MODEL'}</dd><dt>Database</dt><dd>{data.database} (connection checked when opening/saving records)</dd></dl>
    <p>Classifier: {data.model_status?.classifier ?? 'Status unavailable'}</p><h3>LayoutLM checkpoints</h3>{Object.entries(data.layoutlm_weights_present).map(([type,present])=><p key={type}>{type}: {data.model_status?.extractors[type] ?? (present?'Weights present':'Awaiting trained weights')}</p>)}
    <p className="alert">{data.threshold_status} Review: {data.review_threshold}% · Fallback: {data.fallback_threshold}%</p></>}</section>
}
