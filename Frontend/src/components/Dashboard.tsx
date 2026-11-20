import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { dashboard } from '@/api/backend'
import type { DashboardData, DashboardMonth } from '@/types/dashboard'

const inr = new Intl.NumberFormat('en-IN', {style: 'currency', currency: 'INR', maximumFractionDigits: 0})
const money = (n: number) => inr.format(n)
const short = (n: number) => n >= 1e7 ? `₹${(n / 1e7).toFixed(1)}Cr` : n >= 1e5 ? `₹${(n / 1e5).toFixed(1)}L` : n >= 1e3 ? `₹${Math.round(n / 1e3)}k` : `₹${Math.round(n)}`
const monthLabel = (m: string) => new Date(m + '-01T00:00:00').toLocaleDateString('en-IN', {month: 'short', year: '2-digit'})
const TYPE_LABEL: Record<string, string> = {GST_INVOICE: 'GST invoice', PURCHASE_BILL: 'Purchase bill', EXPENSE_RECEIPT: 'Expense receipt',
  UTILITY_BILL: 'Utility bill', CREDIT_NOTE: 'Credit note', DEBIT_NOTE: 'Debit note'}
const PIPELINE_LABEL: Record<string, string> = {ocr_layoutlm: 'LayoutLM only', hosted_vlm: 'VLM only', layoutlm_hosted_fallback: 'Hybrid (VLM fallback)',
  layoutlm_llm_vlm: 'LayoutLM + LLM + VLM', demo_seed: 'Demo seed', human: 'Manual'}
const label = (map: Record<string, string>, key: string) => map[key] ?? key.replaceAll('_', ' ')
const fieldName = (key: string) => key.replaceAll('_', ' ').replace(/^\w/, c => c.toUpperCase()).replace(/\bgstin\b/i, 'GSTIN')
  .replace(/\b(no|cgst|sgst|igst|po)\b/gi, w => ({no: 'number', cgst: 'CGST', sgst: 'SGST', igst: 'IGST', po: 'PO'})[w.toLowerCase()] ?? w)

type Series = {key: keyof DashboardMonth; label: string; color: string}
const FLOW: Series[] = [{key: 'in', label: 'Billed in', color: 'var(--in)'}, {key: 'out', label: 'Billed out', color: 'var(--out)'}]
const GST: Series[] = [{key: 'cgst', label: 'CGST', color: 'var(--cgst)'}, {key: 'sgst', label: 'SGST', color: 'var(--sgst)'},
  {key: 'igst', label: 'IGST', color: 'var(--igst)'}]

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null)
  const [width, setWidth] = useState(0)
  useLayoutEffect(() => {
    if (!ref.current) return
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width))
    observer.observe(ref.current)
    return () => observer.disconnect()
  }, [])
  return [ref, width] as const
}

// Four equal steps of a round size (1, 2 or 5 x 10^n), so every tick is a round number.
function niceMax(v: number) {
  if (v <= 0) return 4
  const raw = v / 4
  const p = 10 ** Math.floor(Math.log10(raw))
  const f = raw / p
  return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * p * 4
}

// One unit for the whole axis, chosen from its maximum: ₹0.5L beside ₹1.0L, never ₹50k beside ₹1.0L.
function axisFormat(max: number) {
  const [div, unit] = max >= 1e7 ? [1e7, 'Cr'] : max >= 1e5 ? [1e5, 'L'] : max >= 1e3 ? [1e3, 'k'] : [1, '']
  return (n: number) => n === 0 ? '₹0' : `₹${Number((n / div).toFixed(2)).toString()}${unit}`
}

// Bar grows from the baseline: square at the bottom, 4px rounded data-end on top.
function topRounded(x: number, y: number, w: number, h: number, r = 4) {
  if (h <= 0 || w <= 0) return ''
  const rr = Math.min(r, w / 2, h)
  return `M${x},${y + h}V${y + rr}Q${x},${y} ${x + rr},${y}H${x + w - rr}Q${x + w},${y} ${x + w},${y + rr}V${y + h}Z`
}

function Legend({series}: {series: Series[]}) {
  return <div className="dash-legend">{series.map(s => <span key={s.key}><i style={{background: s.color}}/>{s.label}</span>)}</div>
}

function ColumnChart({rows, series, stacked = false, title}: {rows: DashboardMonth[]; series: Series[]; stacked?: boolean; title: string}) {
  const [ref, width] = useWidth<HTMLDivElement>()
  const [hover, setHover] = useState<number | null>(null)
  const height = 230, left = 52, bottom = 26, top = 10
  const plot = height - top - bottom
  const value = (row: DashboardMonth, s: Series) => Number(row[s.key]) || 0
  const max = niceMax(Math.max(0, ...rows.map(r => stacked ? series.reduce((t, s) => t + value(r, s), 0) : Math.max(...series.map(s => value(r, s))))))
  const tick = axisFormat(max)
  const band = rows.length ? (width - left) / rows.length : 0
  const y = (v: number) => top + plot - (v / max) * plot
  const barW = stacked ? Math.min(24, band * 0.55) : Math.min(24, (band * 0.7 - 2 * (series.length - 1)) / series.length)
  const step = Math.max(1, Math.ceil(rows.length / Math.max(1, Math.floor((width - left) / 54))))
  return <div className="dash-chart" ref={ref}>
    <Legend series={series}/>
    {width > 0 && <svg width={width} height={height} role="img" aria-label={title}>
      {[0, 0.25, 0.5, 0.75, 1].map(t => <g key={t}>
        <line x1={left} x2={width} y1={y(max * t)} y2={y(max * t)} className={t === 0 ? 'dash-base' : 'dash-gridline'}/>
        <text x={left - 8} y={y(max * t) + 4} textAnchor="end" className="dash-axis">{tick(max * t)}</text>
      </g>)}
      {rows.map((row, i) => {
        const x0 = left + i * band + band / 2
        let stackTop = top + plot
        return <g key={row.month} opacity={hover === null || hover === i ? 1 : 0.45}>
          {series.map((s, j) => {
            const v = value(row, s)
            if (stacked) {
              const h = (v / max) * plot
              const last = series.slice(j + 1).every(next => value(row, next) === 0)
              // Lower segments leave a 2px surface gap on top; only the topmost gets the rounded end.
              const segment = <path key={s.key} fill={s.color} d={last ? topRounded(x0 - barW / 2, stackTop - h, barW, h)
                : h > 2 ? `M${x0 - barW / 2},${stackTop}V${stackTop - h + 2}H${x0 + barW / 2}V${stackTop}Z` : ''}/>
              stackTop -= h
              return segment
            }
            const x = x0 - (series.length * barW + 2 * (series.length - 1)) / 2 + j * (barW + 2)
            return <path key={s.key} fill={s.color} d={topRounded(x, y(v), barW, top + plot - y(v))}/>
          })}
          {i % step === 0 && <text x={x0} y={height - 8} textAnchor="middle" className="dash-axis">{monthLabel(row.month)}</text>}
          <rect x={left + i * band} y={top} width={band} height={plot} fill="transparent" tabIndex={0}
            aria-label={`${monthLabel(row.month)}: ${series.map(s => `${s.label} ${money(value(row, s))}`).join(', ')}`}
            onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}/>
        </g>
      })}
    </svg>}
    {hover !== null && rows[hover] && <div className="dash-tip" style={{left: Math.min(width - 170, Math.max(0, left + hover * band + band / 2 - 85))}}>
      <strong>{monthLabel(rows[hover].month)}</strong>
      {series.map(s => <div key={s.key}><i style={{background: s.color}}/>{s.label}<b>{money(value(rows[hover], s))}</b></div>)}
      <small>{rows[hover].documents} documents</small>
    </div>}
    <details><summary>Show as table</summary><div className="table-scroll"><table><thead><tr><th>Month</th>{series.map(s => <th key={s.key}>{s.label}</th>)}</tr></thead>
      <tbody>{rows.map(r => <tr key={r.month}><td>{monthLabel(r.month)}</td>{series.map(s => <td key={s.key}>{money(value(r, s))}</td>)}</tr>)}</tbody></table></div></details>
  </div>
}

function BarList({rows, format, empty}: {rows: {label: string; value: number; detail?: string}[]; format: (n: number) => string; empty: string}) {
  const max = Math.max(0, ...rows.map(r => r.value))
  if (!rows.length) return <p className="muted">{empty}</p>
  return <div className="dash-bars">{rows.map(r => <div key={r.label} className="dash-bar-row" title={r.detail ? `${r.label}: ${r.detail}` : r.label}>
    <span>{r.label}</span>
    <div><i style={{width: max ? `${(r.value / max) * 100}%` : 0}}/></div>
    <b>{format(r.value)}</b>
  </div>)}</div>
}

function Card({title, children, wide = false}: {title: string; children: ReactNode; wide?: boolean}) {
  return <section className={'dash-card' + (wide ? ' wide' : '')}><h3>{title}</h3>{children}</section>
}

export function Dashboard() {
  const [data, setData] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')
  useEffect(() => {
    dashboard().then(setData).catch(e => setError(e instanceof Error ? e.message : 'Could not load the dashboard'))
  }, [])
  if (error) return <section className="panel"><p role="alert" className="alert error">{error}</p></section>
  if (!data) return <section className="panel"><p>Loading dashboard…</p></section>
  const t = data.totals
  if (!t.documents) return <section className="panel"><h2>Dashboard</h2>
    <p>No saved records yet. Process and save a document, or preload demo data with <code>python scripts/seed_demo.py --data &lt;generator folder&gt;</code>.</p></section>
  const party = (rows: DashboardData['top_vendors']) => rows.map(r => ({label: r.name, value: r.amount, detail: `${r.count} documents`}))
  return <section className="panel dash">
    <h2>Dashboard</h2>
    <p className="muted">{data.note}</p>
    <div className="dash-tiles">
      <div><span><i style={{background: 'var(--in)'}}/>Billed in</span><strong>{money(t.billed_in)}</strong><small>documents your business issued</small></div>
      <div><span><i style={{background: 'var(--out)'}}/>Billed out</span><strong>{money(t.billed_out)}</strong><small>bills, receipts and invoices received</small></div>
      <div><span>Adjustments</span><strong>{money(t.adjustments)}</strong><small>credit and debit notes, shown separately</small></div>
      <div><span>Documents</span><strong>{t.documents}</strong><small>{t.needs_review} saved with open issues · {t.corrected_documents} corrected by a reviewer</small></div>
    </div>
    <div className="dash-grid">
      <Card title="Billed in vs out, by month" wide><ColumnChart rows={data.months} series={FLOW} title="Billed in and out by month"/></Card>
      <Card title="Documents by type"><BarList rows={data.by_type.map(r => ({label: label(TYPE_LABEL, r.type), value: r.count, detail: money(r.amount)}))} format={n => String(n)} empty="No documents."/></Card>
      <Card title="GST printed on invoices, by month"><ColumnChart rows={data.months} series={GST} stacked title="CGST, SGST and IGST by month"/></Card>
      <Card title="Top vendors (billed out)"><BarList rows={party(data.top_vendors)} format={short} empty="No vendors yet."/></Card>
      <Card title="Top customers (billed in)"><BarList rows={party(data.top_customers)} format={short} empty="No customers yet: no documents saved as issued by your business."/></Card>
      <Card title="Fields reviewers corrected most"><BarList rows={data.quality.corrected_fields.map(f => ({label: fieldName(f.key), value: f.count}))} format={n => String(n)} empty="No corrections recorded."/></Card>
      <Card title="Corrections per document, by pipeline"><BarList rows={data.quality.pipelines.map(p => ({label: label(PIPELINE_LABEL, p.name), value: p.corrections_per_document, detail: `${p.count} documents, ${p.corrections} corrections`}))} format={n => n.toFixed(2)} empty="No pipelines recorded."/></Card>
      <Card title="Due dates printed on documents" wide>{data.due.length ? <div className="table-scroll"><table><thead><tr><th>Party</th><th>Type</th><th>Due</th><th>Amount</th><th>Status</th></tr></thead>
        <tbody>{data.due.map(d => <tr key={d.id}><td>{d.party ?? '—'}</td><td>{label(TYPE_LABEL, d.doc_type)}</td><td>{new Date(d.due_date + 'T00:00:00').toLocaleDateString('en-IN')}</td>
          <td>{d.amount === null ? '—' : money(d.amount)}</td>
          <td title={d.days >= 0 ? undefined : `${-d.days} days ago`}>{d.days > 0 ? `Due in ${d.days} days` : d.days === 0 ? 'Due today' : 'Past due date'}</td></tr>)}</tbody></table></div>
        : <p className="muted">No due dates printed on saved documents.</p>}
        <p className="muted">Payment status is not tracked; this lists the due date printed on each document.</p></Card>
    </div>
  </section>
}
