import { useEffect, useRef, useState } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export default function AreaEditor({value,onChange,center,label='Team patrol area'}){
 const host=useRef(null),map=useRef(null),change=useRef(onChange),points=useRef(value||[])
 const [error,setError]=useState('')
 change.current=onChange;points.current=value||[]
 useEffect(()=>{
  const m=L.map(host.current,{scrollWheelZoom:false,doubleClickZoom:false,zoomAnimation:false,fadeAnimation:false}).setView(center?.latitude!=null?[Number(center.latitude),Number(center.longitude)]:[16.7,74.3],14);map.current=m
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; OpenStreetMap contributors'}).addTo(m)
  const add=point=>{if(points.current.length>=100){setError('Use no more than 100 border points.');return}const p=point.wrap();change.current([...points.current,[Number(p.lat.toFixed(6)),Number(p.lng.toFixed(6))]])}
  m.on('click',e=>add(e.latlng));m.on('keypress',e=>{if(e.originalEvent.key==='Enter'){e.originalEvent.preventDefault();add(m.getCenter())}})
  if(points.current.length>=3)m.fitBounds(points.current,{padding:[24,24],maxZoom:16,animate:false})
  const observer=new ResizeObserver(()=>{m.invalidateSize();if(points.current.length>=3)m.fitBounds(points.current,{padding:[24,24],maxZoom:16,animate:false})});observer.observe(host.current)
  return()=>{observer.disconnect();m.remove();map.current=null}
 },[])
 useEffect(()=>{
  if(!map.current)return
  const layer=L.layerGroup().addTo(map.current)
  if(value?.length>=3)L.polygon(value,{color:'#2e6744',fillOpacity:.18,interactive:false}).addTo(layer)
  else if(value?.length)L.polyline(value,{color:'#2e6744',interactive:false}).addTo(layer)
  ;(value||[]).forEach((point,index)=>{
   const marker=L.marker(point,{draggable:true,icon:L.divIcon({className:'area-vertex',html:`<span>${index+1}</span>`,iconSize:[26,26],iconAnchor:[13,13]}),title:`Border point ${index+1}: drag to adjust`}).addTo(layer)
   marker.on('dragend',()=>{const p=marker.getLatLng().wrap();change.current(points.current.map((v,i)=>i===index?[Number(p.lat.toFixed(6)),Number(p.lng.toFixed(6))]:v))})
  })
  return()=>layer.remove()
 },[value])
 function locate(){setError('');if(!navigator.geolocation){setError('Location is unavailable. Pan and zoom the map instead.');return}navigator.geolocation.getCurrentPosition(({coords})=>map.current?.setView([coords.latitude,coords.longitude],16),()=>setError('Location unavailable. Pan and zoom the map instead.'),{timeout:10000,enableHighAccuracy:true})}
 return <div className="space-y-3"><h3 className="font-semibold">{label}</h3><p className="text-sm text-[#647367]">Zoom into a small area, then click around its border. The last point joins the first automatically. Drag numbered points to adjust. Border lines must not cross.</p><div className="flex flex-wrap gap-2"><button type="button" className="secondary-button" onClick={locate}>Zoom to my location</button><button type="button" className="secondary-button" disabled={!value?.length} onClick={()=>onChange(value.slice(0,-1))}>Undo point</button><button type="button" className="secondary-button" disabled={!value?.length} onClick={()=>onChange([])}>Clear drawing</button></div>{error&&<p role="alert" className="notice error">{error}</p>}<div ref={host} role="region" aria-label={label+' drawing map'} className="relative z-0 h-[360px] rounded-xl border"/><p role="status" className="text-sm">{value?.length||0} border points · {value?.length>=3?'Ready to save':'Add at least 3 points'}</p><p className="text-xs text-[#647367]">Keyboard: move the map with arrow keys and press Enter to add a border point at its centre. Automatic assignment uses only saved areas.</p></div>
}
