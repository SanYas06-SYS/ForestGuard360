import { useEffect, useState } from 'react'
import { api, getToken } from './api.js'
export default function NativePush({user}){
 const [message,setMessage]=useState('Checking Android notifications…')
 useEffect(()=>{if(!user||!['OFFICER','RESCUE'].includes(user.role))return;let active=true,registered='',pending=false;async function sync(){const state=window.vanrakshakPush;if(!state)return;if(!state.token){setMessage(state.message);return}const key=getToken()+':'+state.token;if(registered===key||pending)return;pending=true;try{await api('/api/push/devices',{method:'POST',body:JSON.stringify({token:state.token})});registered=key;if(active)setMessage('This phone is registered for team alerts.')}catch(e){if(active)setMessage('Notification registration failed. '+e.message)}finally{pending=false}}sync();const timer=setInterval(sync,30000);window.addEventListener('native-push-ready',sync);return()=>{active=false;clearInterval(timer);window.removeEventListener('native-push-ready',sync)}},[user?.id])
 if(!navigator.userAgent.includes('VanRakshakGuard/'))return null
 return <p role="status" className="notice mb-4">{message}</p>
}
