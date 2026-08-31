import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { Loader2, AlertTriangle, Check, Building2, SlidersHorizontal } from 'lucide-react'
import { fetchSettings, updateSettings, type AppSettings } from '@/api/backend'

const inputStyle = {
  background: 'rgba(0,0,0,0.04)',
  border: '1px solid rgba(0,0,0,0.09)',
  color: '#1A1816',
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="block text-xs font-semibold mb-1.5" style={{ color: '#78726A' }}>
        {label}
      </label>
      {children}
      {hint && <p className="text-[11px] mt-1" style={{ color: '#A09890' }}>{hint}</p>}
    </div>
  )
}

function SectionCard({
  icon: Icon,
  title,
  description,
  children,
}: {
  icon: typeof Building2
  title: string
  description: string
  children: React.ReactNode
}) {
  return (
    <div
      className="rounded-xl px-5 py-5"
      style={{ background: 'rgba(255,255,255,0.6)', border: '1px solid rgba(0,0,0,0.08)' }}
    >
      <div className="flex items-center gap-2.5 mb-1">
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ background: 'rgba(75,108,183,0.1)' }}
        >
          <Icon size={15} style={{ color: '#4B6CB7' }} />
        </div>
        <h2 className="text-sm font-semibold" style={{ color: '#1A1816' }}>{title}</h2>
      </div>
      <p className="text-xs mb-4" style={{ color: '#A09890' }}>{description}</p>
      {children}
    </div>
  )
}

export function Settings() {
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchSettings()
      .then((s) => !cancelled && setSettings(s))
      .catch(() => !cancelled && setError('Could not reach the backend. Make sure the API server is running.'))
      .finally(() => !cancelled && setLoading(false))
    return () => {
      cancelled = true
    }
  }, [])

  function update<K extends keyof AppSettings>(key: K, value: AppSettings[K]) {
    setSettings((s) => (s ? { ...s, [key]: value } : s))
    setSaved(false)
  }

  async function handleSave() {
    if (!settings) return
    setSaving(true)
    setError(null)
    try {
      const result = await updateSettings({
        businessName: settings.businessName,
        businessGstin: settings.businessGstin,
        businessAddress: settings.businessAddress,
        classifierL1Threshold: settings.classifierL1Threshold,
        classifierL2Threshold: settings.classifierL2Threshold,
        extractorLayoutlmThreshold: settings.extractorLayoutlmThreshold,
        gstTaxMatchTolerance: settings.gstTaxMatchTolerance,
        gstRateMatchTolerance: settings.gstRateMatchTolerance,
      })
      setSettings(result)
      setSaved(true)
    } catch (err) {
      console.error('Settings save failed:', err)
      setError('Failed to save settings.')
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Loader2 size={22} className="animate-spin" style={{ color: '#A09890' }} />
      </div>
    )
  }

  if (error && !settings) {
    return (
      <div className="flex flex-col items-center justify-center h-full gap-2 text-center px-8">
        <AlertTriangle size={22} style={{ color: '#DC2626' }} />
        <p className="text-sm font-medium" style={{ color: '#1A1816' }}>{error}</p>
      </div>
    )
  }

  if (!settings) return null

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="max-w-2xl mx-auto space-y-5 pb-8"
    >
      <SectionCard
        icon={Building2}
        title="Business Profile"
        description="Used to identify your organization; not yet wired into document extraction."
      >
        <div className="space-y-3">
          <Field label="Business Name">
            <input
              type="text"
              value={settings.businessName}
              onChange={(e) => update('businessName', e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none"
              style={inputStyle}
              placeholder="Acme Traders Pvt. Ltd."
            />
          </Field>
          <Field label="GSTIN">
            <input
              type="text"
              value={settings.businessGstin}
              onChange={(e) => update('businessGstin', e.target.value.toUpperCase())}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none font-mono"
              style={inputStyle}
              placeholder="27AAPFU0939F1ZV"
              maxLength={15}
            />
          </Field>
          <Field label="Address">
            <textarea
              value={settings.businessAddress}
              onChange={(e) => update('businessAddress', e.target.value)}
              className="w-full px-3 py-2 rounded-lg text-sm outline-none resize-none"
              style={inputStyle}
              rows={2}
              placeholder="123 MG Road, Bengaluru, KA 560001"
            />
          </Field>
        </div>
      </SectionCard>

      <SectionCard
        icon={SlidersHorizontal}
        title="Validation Thresholds"
        description="Tune how strict document classification and validation are. Changes apply to documents processed after saving."
      >
        <div className="space-y-4">
          <Field
            label={`Classifier L1 (regex) confidence threshold — ${settings.classifierL1Threshold.toFixed(2)}`}
            hint="Above this, a keyword-matched document type is accepted without running the ML classifier."
          >
            <input
              type="range"
              min={0.5}
              max={0.99}
              step={0.01}
              value={settings.classifierL1Threshold}
              onChange={(e) => update('classifierL1Threshold', parseFloat(e.target.value))}
              className="w-full accent-[#4B6CB7]"
            />
          </Field>

          <Field
            label={`Classifier L2 (ML) confidence threshold — ${settings.classifierL2Threshold.toFixed(2)}`}
            hint="Below this, a document is flagged L3 (needs human review) instead of auto-classified."
          >
            <input
              type="range"
              min={0.3}
              max={0.95}
              step={0.01}
              value={settings.classifierL2Threshold}
              onChange={(e) => update('classifierL2Threshold', parseFloat(e.target.value))}
              className="w-full accent-[#4B6CB7]"
            />
          </Field>

          <Field
            label={`Extraction confidence threshold — ${settings.extractorLayoutlmThreshold.toFixed(2)}`}
            hint="Extracted fields below this LayoutLM confidence are dropped rather than shown."
          >
            <input
              type="range"
              min={0.1}
              max={0.9}
              step={0.01}
              value={settings.extractorLayoutlmThreshold}
              onChange={(e) => update('extractorLayoutlmThreshold', parseFloat(e.target.value))}
              className="w-full accent-[#4B6CB7]"
            />
          </Field>

          <div className="grid grid-cols-2 gap-3 pt-1">
            <Field label="GST tax symmetry tolerance (₹)" hint="Max allowed CGST/SGST difference.">
              <input
                type="number"
                step={0.01}
                min={0}
                value={settings.gstTaxMatchTolerance}
                onChange={(e) => update('gstTaxMatchTolerance', parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                style={inputStyle}
              />
            </Field>
            <Field label="GST rate sanity tolerance (%)" hint="Tolerance around valid GST slabs.">
              <input
                type="number"
                step={0.1}
                min={0}
                value={settings.gstRateMatchTolerance}
                onChange={(e) => update('gstRateMatchTolerance', parseFloat(e.target.value) || 0)}
                className="w-full px-3 py-2 rounded-lg text-sm outline-none"
                style={inputStyle}
              />
            </Field>
          </div>
        </div>
      </SectionCard>

      {error && (
        <p className="text-xs px-1" style={{ color: '#DC2626' }}>{error}</p>
      )}

      <div className="flex items-center gap-3">
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-4 py-2 rounded-lg text-sm font-semibold text-white cursor-pointer disabled:opacity-60 disabled:cursor-not-allowed transition-all"
          style={{ background: '#4B6CB7' }}
        >
          {saving ? 'Saving...' : 'Save Changes'}
        </button>
        {saved && (
          <motion.span
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-1 text-xs font-medium"
            style={{ color: '#2E7D32' }}
          >
            <Check size={13} /> Saved
          </motion.span>
        )}
      </div>
    </motion.div>
  )
}
