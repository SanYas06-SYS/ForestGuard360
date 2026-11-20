import { useEffect, useState } from 'react'
import { getToken } from './api.js'
export default function ReportImage({src,...props}){
  const [url,setUrl]=useState(''),[error,setError]=useState('')
  useEffect(()=>{
    if(!src?.startsWith('/api/report-images/')){setUrl(src);return}
    const controller=new AbortController();let objectUrl
    setUrl('');setError('')
    fetch(src,{headers:{Authorization:`Bearer ${getToken()}`},credentials:'omit',cache:'no-store',signal:controller.signal}).then(async response=>{if(!response.ok)throw new Error('Photo could not be loaded.');return response.blob()}).then(blob=>{if(!controller.signal.aborted){objectUrl=URL.createObjectURL(blob);setUrl(objectUrl)}}).catch(e=>{if(e.name!=='AbortError')setError(e.message)})
    return()=>{controller.abort();if(objectUrl)URL.revokeObjectURL(objectUrl)}
  },[src])
  if(error)return <p role="alert" className="notice error">{error}</p>
  return url?<img src={url} {...props}/>:<p className="text-sm">Loading photo…</p>
}
