import { request } from '@/api/backend'
import { BusinessOnboarding } from '@/components/BusinessOnboarding'
import type { BusinessProfile } from '@/components/BusinessOnboarding'
import { useEffect, useState } from 'react'
import { BackgroundOrbs } from '@/components/layout/BackgroundOrbs'
import { Sidebar } from '@/components/layout/Sidebar'
import { UploadWorkflow } from '@/components/upload/UploadWorkflow'
import { Records } from '@/components/Records'
import { Settings } from '@/components/Settings'
import { Research } from '@/components/Research'

export default function App() {
  const [collapsed,setCollapsed]=useState(()=>window.matchMedia('(max-width: 850px)').matches)
  const [page,setPage]=useState('uploads')
  const [profile,setProfile]=useState<BusinessProfile|null>(null)
  const [loading,setLoading]=useState(true)
  const [profileError,setProfileError]=useState('')
  async function loadProfile() {
    setLoading(true); setProfileError('')
    try { setProfile(await request<BusinessProfile|null>('/business-profile')) }
    catch(e) { setProfileError(e instanceof Error ? e.message : 'Could not load business details') }
    finally { setLoading(false) }
  }
  useEffect(()=>{ void loadProfile() },[])
  if (loading) return <main className="panel">Starting eMunim and preparing models?</main>
  if (profileError) return <main className="panel"><p role="alert">{profileError}</p><button onClick={loadProfile}>Retry</button></main>
  if (!profile) return <main className="p-6"><BusinessOnboarding profile={null} onSaved={setProfile}/></main>
  return <div className="h-screen w-screen overflow-hidden relative"><BackgroundOrbs/>
    <Sidebar collapsed={collapsed} onToggle={()=>setCollapsed(v=>!v)} activePage={page} onNavigate={setPage}/>
    <main style={{paddingLeft:collapsed?64:224}} className="h-full flex flex-col relative z-10">
      <header className="px-6 py-4 border-b"><h1 className="text-xl font-semibold">eMunim · {page==='uploads'?'Document processing':page[0].toUpperCase()+page.slice(1)}</h1><p className="text-sm text-stone-500">Extract, verify and save accounting documents</p></header>
      <div className="flex-1 overflow-y-auto p-6">{page==='uploads'?<UploadWorkflow/>:page==='settings'?<><BusinessOnboarding profile={profile} onSaved={setProfile}/><Settings/></>:page==='research'?<Research/>:<Records dashboard={page==='dashboard'}/>}</div>
    </main>
  </div>
}
