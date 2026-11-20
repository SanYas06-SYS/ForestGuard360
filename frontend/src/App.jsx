import { useEffect, useState } from 'react'
import { LoaderCircle } from 'lucide-react'
import { initializeTabSession } from './tabSession.js'
import { api, clearSession } from './api.js'
import Dashboard from './Dashboard.jsx'
import IncidentQueue from './IncidentQueue.jsx'
import IncidentDetail from './IncidentDetail.jsx'
import Layout from './Layout.jsx'
import Login from './Login.jsx'
import MyReports from './MyReports.jsx'
import ReportForm from './ReportForm.jsx'
import Monitoring from './Monitoring.jsx'
import Tourism from './Tourism.jsx'
import TeamPage from './TeamPage.jsx'

const staffRoles=['ADMIN','OFFICER','RESCUE']
export default function App(){
  const [user,setUser]=useState(null),[loading,setLoading]=useState(true),[openCount,setOpenCount]=useState(0),[sessionError,setSessionError]=useState(''),[signingOut,setSigningOut]=useState(false),[logoutError,setLogoutError]=useState('')
  const path=window.location.pathname.replace(/\/$/,'')||'/dashboard'
  useEffect(()=>{
    initializeTabSession().then(()=>api('/api/auth/session')).then(result=>{setUser(result.user);if(!result.user)clearSession()}).catch(error=>setSessionError(error.message)).finally(()=>setLoading(false))
    const expired=()=>{setUser(null);window.location.replace('/login?expired=1')}
    const restored=event=>{if(event.persisted)window.location.reload()}
    window.addEventListener('session-expired',expired);window.addEventListener('pageshow',restored)
    return()=>{window.removeEventListener('session-expired',expired);window.removeEventListener('pageshow',restored)}
  },[])
  useEffect(()=>{if(user&&staffRoles.includes(user.role))api('/api/admin/overview').then(result=>setOpenCount(result.stats.open)).catch(()=>{})},[user])
  async function logout(){
    if(signingOut)return
    setSigningOut(true);setLogoutError('')
    try{await api('/api/auth/logout',{method:'POST'});clearSession();setUser(null);window.location.replace('/login?signedout=1')}
    catch(error){setLogoutError('Could not sign out. Check your connection and try again.');setSigningOut(false)}
  }
  function onLogin(nextUser){setUser(nextUser);window.location.replace(staffRoles.includes(nextUser.role)?'/dashboard':'/my-reports')}
  if(loading)return <main className="loading-screen"><LoaderCircle className="animate-spin" size={28}/><p>Opening your workspace…</p></main>
  if(sessionError)return <main className="loading-screen"><h1>Unable to connect</h1><p role="alert">{sessionError}</p><button className="primary-button" onClick={()=>window.location.reload()}>Try again</button></main>
  if(!user){if(path==='/tourism')return <Tourism user={null}/>;return <Login onLogin={onLogin}/>}
  const isStaff=staffRoles.includes(user.role)
  let page
  if(path==='/tourism')page=<Tourism user={user} embedded/>
  else if(path==='/report/fire'||path==='/fires/new')page=<ReportForm kind="fires" user={user}/>
  else if(path==='/report/conflict'||path==='/conflicts/new')page=<ReportForm kind="conflicts" user={user}/>
  else if(path==='/monitoring'&&isStaff)page=<Monitoring user={user}/>
  else if(path==='/incidents'&&isStaff)page=<IncidentQueue user={user}/>
  else if(path.startsWith('/incidents/')&&isStaff){const [,,type,id]=path.split('/');page=<IncidentDetail type={type} id={id} user={user}/>}
  else if(path==='/team'&&user.role==='ADMIN')page=<TeamPage/>
  else if(path==='/my-reports'||!isStaff)page=<MyReports/>
  else page=<Dashboard user={user}/>
  return <Layout user={user} path={path} onLogout={logout} signingOut={signingOut} openCount={openCount}>{logoutError&&<p role="alert" className="notice error">{logoutError}</p>}{page}</Layout>
}
