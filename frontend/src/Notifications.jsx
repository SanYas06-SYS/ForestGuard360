import { useEffect, useState } from 'react'
import { api } from './api.js'
export default function Notifications(){
 const [items,setItems]=useState([]),[error,setError]=useState(''),[loading,setLoading]=useState(true)
 useEffect(()=>{let active=true;const load=()=>api('/api/notifications').then(r=>{if(active){setItems(r.items);setError('');setLoading(false)}}).catch(e=>{if(active){setError(e.message);setLoading(false)}});load();const timer=setInterval(load,15000);return()=>{active=false;clearInterval(timer)}},[])
 async function open(item){try{await api(`/api/notifications/${item.id}/read`,{method:'PATCH'});window.location.assign(`/incidents/${item.incident_type}/${item.incident_id}`)}catch(e){setError(e.message)}}
 return <div className="mx-auto max-w-3xl space-y-4"><h1 className="text-3xl font-semibold">Assignment inbox</h1><p>New assignments for your account and team. Updates every 15 seconds while open.</p>{error&&<p role="alert" className="notice error">{error}</p>}{loading?<p>Loading…</p>:!items.length?<p className="notice">No assignments yet.</p>:items.map(item=><button key={item.id} onClick={()=>open(item)} className="block w-full rounded-xl border bg-white p-5 text-left"><strong>{!item.read_at?'● ':''}{item.title}</strong><p>{item.body}</p><small>{new Date(item.created_at).toLocaleString()}</small></button>)}</div>
}
