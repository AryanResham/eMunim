import { useEffect, useState } from 'react'
import { capabilities, uploadFile, runOcr, classifyDocument, extractFields, validateEntry, saveDocument, API_BASE } from '@/api/backend'
import type { Capabilities, DocType, ExtractedField, ExtractionRun, Pipeline, ReviewPolicy, ValidationResult } from '@/types/upload'
import type { OCRResult } from '@/types/ocr'
import { StepIndicator } from './StepIndicator'
import { OcrDebugViewer } from '@/components/OcrDebugViewer'

const DOCUMENT_TYPES: DocType[] = ['GST_INVOICE','PURCHASE_BILL','EXPENSE_RECEIPT','UTILITY_BILL','CREDIT_NOTE','DEBIT_NOTE']
const PIPELINE_LABELS: Record<Pipeline,string> = {ocr_layoutlm:'OCR + LayoutLM', hosted_vlm:'Hosted vision model',layoutlm_hosted_fallback:'LayoutLM + selective hosted fallback'}
const POLICIES: ReviewPolicy[] = ['validation_review','validation_confidence_review','extraction_only']

export function UploadWorkflow() {
  const [businessRole,setBusinessRole] = useState<'buyer'|'vendor'>('buyer')
  const [classificationAgreed,setClassificationAgreed] = useState(false)
  const [step,setStep] = useState<1|2|3|4>(1)
  const [pipeline,setPipeline] = useState<Pipeline>('ocr_layoutlm')
  const [policy,setPolicy] = useState<ReviewPolicy>('validation_review')
  const [file,setFile] = useState<File|null>(null)
  const [fileId,setFileId] = useState('')
  const [ocr,setOcr] = useState<OCRResult|null>(null)
  const [docType,setDocType] = useState<DocType>('GST_INVOICE')
  const [run,setRun] = useState<ExtractionRun|null>(null)
  const [fields,setFields] = useState<ExtractedField[]>([])
  const [validation,setValidation] = useState<ValidationResult|null>(null)
  const [busy,setBusy] = useState(false)
  const [error,setError] = useState('')
  const [notice,setNotice] = useState('')
  const [reason,setReason] = useState('')
  const [confirmed,setConfirmed] = useState(false)
  const [saved,setSaved] = useState('')
  const [caps,setCaps] = useState<Capabilities|null>(null)
  const [showOcr,setShowOcr] = useState(false)
  const [dimensions,setDimensions] = useState({width:0,height:0})
  useEffect(() => { capabilities().then(setCaps).catch(e=>setError(e.message)) }, [])
  async function perform(action:()=>Promise<void>) {
    setBusy(true); setError('')
    try { await action() } catch(e) { setError(e instanceof Error ? e.message : 'Request failed') } finally { setBusy(false) }
  }
  async function prepare() {
    if (!file) return
    await perform(async()=>{
      const uploaded = await uploadFile(file); setFileId(uploaded.file_id); setDimensions(uploaded)
      if (caps?.ocr_configured) {
        const result = await runOcr(uploaded.file_id); setOcr(result)
        try { const detected=await classifyDocument(uploaded.file_id,result.full_text); setDocType(detected.type); setNotice('Detected '+detected.label+' ('+detected.confidence+'%). Confirm or change below.') }
        catch { setNotice('Automatic classification unavailable. Select the document type manually.') }
      } else { setOcr(null); setNotice('Automatic classification requires OCR configuration. Select and confirm the document type manually.') }
      setClassificationAgreed(false); setStep(2)
    })
  }
  async function extract() {
    await perform(async()=>{
      const result = await extractFields(fileId,docType,ocr,pipeline,policy,businessRole)
      setRun(result); setFields(result.fields); setValidation(result.validation); setStep(3)
    })
  }
  const changed = !!run && fields.some(f=>f.value !== run.fields.find(r=>r.key===f.key)?.value)
  function edit(key:string,value:string) {
    setFields(current=>current.map(f=>f.key===key?{...f,value:value.trim()?value:null,confidence:null,source:'human'}:f))
    setValidation(null); setConfirmed(false)
  }
  const unavailable = !!caps && ((pipeline!=='hosted_vlm' && !caps.ocr_configured) || (pipeline!=='ocr_layoutlm' && !caps.hosted_configured))
  const noWeights = !!caps && pipeline!=='hosted_vlm' && !caps.layoutlm_weights_present[docType]
  return <div className="workflow">
    <StepIndicator currentStep={step}/>
    {error && <div role="alert" className="alert error">{error}</div>}
    {saved ? <section className="panel"><h2>Record saved</h2><p>Saved record {saved}. Your corrections and review history are stored.</p><button onClick={()=>{setSaved('');setStep(1);setFile(null);setRun(null);setOcr(null);setError('');setNotice('');setReason('');setConfirmed(false)}}>Process another document</button></section> :
    <section className="panel">
      {step===1 && <>
        <h2>Upload an accounting document</h2><p>Choose an extraction pipeline before processing. Upload a single JPEG or PNG.</p>
        <div className="pipeline-options">{(Object.keys(PIPELINE_LABELS) as Pipeline[]).map(p=><button key={p} className={pipeline===p?'selected':''} onClick={()=>setPipeline(p)} disabled={busy}>{PIPELINE_LABELS[p]}</button>)}</div>
        <label>Review configuration<select value={policy} onChange={e=>setPolicy(e.target.value as ReviewPolicy)} disabled={busy}>{POLICIES.map(p=><option key={p} value={p}>{p.replaceAll('_',' ')}</option>)}</select></label>
        <p className="muted">Extraction-only is an offline research comparator. Saving always requires review and server validation.</p>
        <label className="drop-area">Select or drop an invoice<input type="file" accept="image/jpeg,image/png" disabled={busy} onChange={e=>{setFile(e.target.files?.[0]??null);setError('')}}/></label>
        {file && <p>{file.name} · {(file.size/1024).toFixed(0)} KB</p>}
        {unavailable && <p className="alert">Configure {pipeline!=='hosted_vlm'&&!caps?.ocr_configured?'GOOGLE_CLOUD_VISION_API_KEY ':''}{pipeline!=='ocr_layoutlm'&&!caps?.hosted_configured?'GROQ_API_KEY and HOSTED_VLM_MODEL':''} in backend/.env, then restart.</p>}
        <button disabled={busy||!file||unavailable} onClick={prepare}>{busy?'Processing…':'Upload and continue'}</button>
      </>}
      {step===2 && <>
        <h2>Confirm document type</h2><p>{notice}</p>
        <label>Document type<select value={docType} onChange={e=>{setDocType(e.target.value as DocType);setClassificationAgreed(false)}} disabled={busy}>{DOCUMENT_TYPES.map(t=><option key={t}>{t}</option>)}</select></label>
        <label>Your business is the<select value={businessRole} onChange={e=>{setBusinessRole(e.target.value as 'buyer'|'vendor');setClassificationAgreed(false)}} disabled={busy}><option value="buyer">Buyer (purchase / received document)</option><option value="vendor">Vendor (sale / issued document)</option></select></label>
        <label className="inline"><input type="checkbox" checked={classificationAgreed} onChange={e=>setClassificationAgreed(e.target.checked)} disabled={busy}/>I confirm this document type and my business role.</label>
        {noWeights && <p className="alert">Trained per-type LayoutLM weights are missing for this type. Train them and restart the backend, or use the hosted pipeline.</p>}
        <img className="invoice-preview" src={API_BASE+'/files/'+fileId} alt="Normalized uploaded invoice"/>
        {ocr && file && <><button onClick={()=>setShowOcr(!showOcr)}>Toggle OCR inspection</button>{showOcr&&<OcrDebugViewer file={file} result={ocr} processedWidth={dimensions.width} processedHeight={dimensions.height}/>}</>}
        <div className="actions"><button disabled={busy} onClick={()=>setStep(1)}>Back</button><button disabled={busy||noWeights||!classificationAgreed} onClick={extract}>{busy?'Extracting…':'Extract fields'}</button></div>
      </>}
      {(step===3||step===4)&&run && <>
        <h2>{step===3?'Review extracted fields':'Validate and save'}</h2>
        <p>{PIPELINE_LABELS[pipeline]} · {run.metadata.elapsed_ms.toFixed(0)} ms · hosted attempts: {run.metadata.hosted.attempts}{run.metadata.hosted.cached?' (cached)':''}</p>
        {run.metadata.routing_reasons.length>0&&<details><summary>Hosted fallback reasons</summary><ul>{run.metadata.routing_reasons.map(r=><li key={r}>{r}</li>)}</ul></details>}
        {run.metadata.operational_reasons.length>0&&<div className="alert error">{run.metadata.operational_reasons.join(' ')}</div>}
        {run.metadata.conflicts.length>0&&<div className="alert">Extractor disagreements require correction or an explicit acceptance note: {run.metadata.conflicts.join(', ')}</div>}
        <div className="review-grid"><div><img className="invoice-preview" src={API_BASE+'/files/'+fileId} alt="Invoice source"/></div><div className="field-grid">
          {fields.map(f=><label key={f.key} className={validation?.flagged_fields?.includes(f.key)?'flagged':''}><span>{f.label} <small>{f.source} {f.confidence===null?'':f.confidence+'%'}</small></span>
            <input value={f.value??''} placeholder="Not extracted / absent" onChange={e=>edit(f.key,e.target.value)} disabled={busy}/></label>)}
        </div></div>
        {run.line_items.length>0&&<details><summary>Detected line items (verify independently)</summary><pre>{JSON.stringify(run.line_items,null,2)}</pre></details>}
        <button disabled={busy} onClick={()=>perform(async()=>{setValidation(await validateEntry(fields,docType,policy,run.run_id));setStep(4)})}>{busy?'Checking…':changed?'Validate corrected values':'Run validation'}</button>
        {validation && <div className="validation"><h3>{validation.review_required?'Review required':'No issues flagged — verify before saving'}</h3><p>Passing checks does not guarantee extraction accuracy.</p>
          {validation.rules.map(r=><div className={'rule '+(r.passed===false?'failed':r.passed===null?'unknown':'')} key={r.name}><strong>{r.passed===null?'Insufficient evidence':r.passed?'Pass':'Flag'} · {r.name}</strong><p>{r.message}</p></div>)}
          {validation.review_reasons?.map(r=><p key={r} className="muted">{r}</p>)}
        </div>}
        {step===4&&<>
          <label>Review note / reason for accepting unresolved issues<textarea value={reason} onChange={e=>setReason(e.target.value)} disabled={busy}/></label>
          <label className="inline"><input type="checkbox" checked={confirmed} onChange={e=>setConfirmed(e.target.checked)} disabled={busy}/>I reviewed the source and the final values.</label>
          <button disabled={busy||!validation||!confirmed} onClick={()=>perform(async()=>{const record=await saveDocument(run.run_id,fields,reason);setSaved(record.id)})}>{busy?'Saving…':'Save reviewed record'}</button>
        </>}
        <button disabled={busy} onClick={()=>{setStep(2);setConfirmed(false)}}>Back to document type</button>
      </>}
    </section>}
  </div>
}
