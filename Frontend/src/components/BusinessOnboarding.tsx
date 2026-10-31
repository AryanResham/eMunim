import { useState } from 'react'
import { request } from '@/api/backend'

export interface BusinessProfile {
  legal_name: string
  trade_name: string
  gstins: string[]
  address: string
}

export function BusinessOnboarding({ profile, onSaved }: { profile: BusinessProfile | null; onSaved: (profile: BusinessProfile) => void }) {
  const [name, setName] = useState(profile?.legal_name ?? '')
  const [trade, setTrade] = useState(profile?.trade_name ?? '')
  const [gstins, setGstins] = useState(profile?.gstins.join(', ') ?? '')
  const [address, setAddress] = useState(profile?.address ?? '')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  return <form className="panel" onSubmit={async e => {
    e.preventDefault(); setBusy(true); setError('')
    try {
      onSaved(await request<BusinessProfile>('/business-profile', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ legal_name: name, trade_name: trade, gstins: gstins.split(',').map(s => s.trim()).filter(Boolean), address }) }))
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not save business details') }
    finally { setBusy(false) }
  }}>
    <h2>Your business details</h2>
    <p>Save your business identity to help distinguish your business from suppliers and customers. This profile is shared by this eMunim installation.</p>
    {error && <p role="alert" className="alert error">{error}</p>}
    <fieldset disabled={busy}>
      <label>Legal business name<input required maxLength={200} value={name} onChange={e => setName(e.target.value)} /></label>
      <label>Trade name<input maxLength={200} value={trade} onChange={e => setTrade(e.target.value)} /></label>
      <label>GSTINs (comma separated; leave blank if unregistered)<input value={gstins} onChange={e => setGstins(e.target.value.toUpperCase())} /></label>
      <label>Business address<textarea maxLength={1000} value={address} onChange={e => setAddress(e.target.value)} /></label>
      <button type="submit">{busy ? 'Saving…' : 'Save business details'}</button>
    </fieldset>
  </form>
}
