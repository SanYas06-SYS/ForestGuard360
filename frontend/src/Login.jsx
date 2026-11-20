import { useState } from 'react'
import { Leaf, LoaderCircle, ArrowRight, Eye, EyeOff, ShieldCheck, MapPin, Trees } from 'lucide-react'
import { api } from './api.js'

export default function Login({ onLogin }) {
  const [creating,setCreating]=useState(false),[name,setName]=useState(''),[email,setEmail]=useState(''),[password,setPassword]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false),[showPassword,setShowPassword]=useState(false)
  const params=new URLSearchParams(window.location.search)
  async function submit(event){event.preventDefault();setBusy(true);setError('');try{const result=await api(creating?'/api/auth/register':'/api/auth/login',{method:'POST',body:JSON.stringify({name,email,password})});onLogin(result.user)}catch(cause){setError(cause.message)}finally{setBusy(false)}}
  return <main className="login-page">
    <section className="login-story"><a href="/login" className="brand"><span className="brand-mark"><Leaf size={24}/></span><span>VanRakshak <b>360</b><small>FOREST CARE, CONNECTED</small></span></a>
      <div className="story-copy"><span className="eyebrow">PROTECT · RESPOND · EXPLORE</span><h1>A safer forest.<br/>A shared responsibility.</h1><p>Report a concern, support a response, or discover a responsible way to explore.</p><img src="/static/core/images/forest-scene.svg" alt="Illustration of a forest landscape"/><div className="story-features"><span><ShieldCheck size={18}/>Forest protection</span><span><Trees size={18}/>Wildlife care</span><span><MapPin size={18}/>Responsible visits</span></div></div><p className="story-footer">Integrated forest monitoring & wildlife protection</p>
    </section>
    <section className="login-content"><form onSubmit={submit} className="login-card"><span className="eyebrow">WELCOME TO VANRAKSHAK</span><h2>{creating?'Create your account':'Welcome back'}</h2><p className="login-intro">{creating?'Join the community to report concerns and follow their progress.':'Sign in to see your reports and the tools for your role.'}</p>
      {params.has('signedout')&&<p role="status" className="notice success">You have signed out of this tab.</p>}{params.has('expired')&&<p role="status" className="notice">Your session ended. Please sign in again.</p>}{error&&<p role="alert" className="notice error">{error}</p>}
      {creating&&<label className="field-label">Full name<input required maxLength={120} autoComplete="name" placeholder="Your full name" value={name} onChange={e=>setName(e.target.value)}/></label>}
      <label className="field-label">Email address<input required type="email" autoComplete="username" placeholder="you@example.com" value={email} onChange={e=>setEmail(e.target.value)}/></label>
      <label className="field-label">Password<div className="password-field"><input required type={showPassword?'text':'password'} minLength={creating?8:1} autoComplete={creating?'new-password':'current-password'} placeholder={creating?'At least 8 characters':'Enter your password'} value={password} onChange={e=>setPassword(e.target.value)}/><button type="button" aria-label={showPassword?'Hide password':'Show password'} onClick={()=>setShowPassword(!showPassword)}>{showPassword?<EyeOff size={18}/>:<Eye size={18}/>}</button></div></label>
      <button disabled={busy} className="primary-button login-submit">{busy?<LoaderCircle size={18} className="animate-spin"/>:<ArrowRight size={18}/>} {busy?'Please wait…':creating?'Create account':'Sign in'}</button>
      <p className="account-switch">{creating?'Already have an account?':'New to VanRakshak?'} <button type="button" onClick={()=>{setCreating(!creating);setPassword('');setError('')}}>{creating?'Sign in':'Create an account'}</button></p>
      <div className="login-divider"/><a href="/tourism" className="visitor-link"><span className="visitor-icon"><MapPin size={20}/></span><span><strong>Just visiting?</strong><small>Explore trails and forest guidelines</small></span><ArrowRight size={18}/></a>
      <p className="tab-note">Each tab has its own sign-in. You can use a different account in another tab.</p>
    </form></section>
  </main>
}
