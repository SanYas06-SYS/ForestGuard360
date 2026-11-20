import { useEffect, useState } from 'react'
import { api } from './api.js'
import LocationPicker from './LocationPicker.jsx'

export default function TeamLocationForm({team,onSaved}){
  const [location,setLocation]=useState({latitude:team.latitude??'',longitude:team.longitude??''}),[status,setStatus]=useState(team.status),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false)
  useEffect(()=>{setLocation({latitude:team.latitude??'',longitude:team.longitude??''});setStatus(team.status)},[team.latitude,team.longitude,team.status])
  async function save(event){
    event.preventDefault();setError('');setSaved(false)
    if(location.latitude===''||location.longitude===''){setError('Choose the team’s location on the map first.');return}
    setBusy(true)
    try{await api(`/api/response-teams/${team.id}`,{method:'PATCH',body:JSON.stringify({...location,status})});await onSaved();setSaved(true)}catch(e){setError(e.message)}finally{setBusy(false)}
  }
  return <form onSubmit={save} className="mt-4 border-t pt-4"><LocationPicker compact value={location} onChange={point=>{setLocation(point);setSaved(false)}} label={`${team.name} location`}/><label className="field-label">Team availability<select value={status} onChange={e=>{setStatus(e.target.value);setSaved(false)}} className="mt-2 w-full border p-2"><option value="AVAILABLE">Available</option><option value="BUSY">Busy</option><option value="OFFLINE">Offline</option></select></label>{error&&<p className="notice error" role="alert">{error}</p>}{saved&&<p className="notice success" role="status">Team location saved.</p>}<button disabled={busy} className="primary-button mt-3 w-full">{busy?'Saving…':'Save team location'}</button></form>
}
