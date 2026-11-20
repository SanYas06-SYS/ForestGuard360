import { useEffect, useRef } from 'react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

export default function ForestMap({ points=[], areas=[], routes=[] }) {
  const container=useRef(null)
  const mapRef=useRef(null), fitted=useRef(false)
  useEffect(()=>{
    const map=L.map(container.current).setView([16.7,74.3],10)
    mapRef.current=map
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',maxZoom:19}).addTo(map)
    return()=>{map.remove();mapRef.current=null;fitted.current=false}
  },[])
  useEffect(()=>{
    const map=mapRef.current
    if(!map)return
    const layer=L.layerGroup().addTo(map)
    const bounds=[]
    for(const point of points){
      if(point.latitude==null||point.longitude==null)continue
      const location=[Number(point.latitude),Number(point.longitude)]
      if(!location.every(Number.isFinite))continue
      bounds.push(location)
      const label=document.createElement('span');label.textContent=point.label
      L.circleMarker(location,{radius:8,color:point.color||'#2e6744',fillOpacity:.8}).addTo(layer).bindPopup(label)
    }
    for(const area of areas){const label=document.createElement('span');label.textContent=area.name;L.polygon(area.coordinates,{color:area.kind==='RESTRICTED'?'#b3453d':'#4d7897'}).addTo(layer).bindPopup(label);bounds.push(...area.coordinates)}
    for(const route of routes){const label=document.createElement('span');label.textContent=route.name;L.polyline(route.coordinates,{color:'#2e6744',weight:5}).addTo(layer).bindPopup(label);bounds.push(...route.coordinates)}
    if(bounds.length&&!fitted.current){map.fitBounds(bounds,{padding:[30,30],maxZoom:14,animate:false});fitted.current=true}
    return()=>layer.remove()
  },[points,areas,routes])
  return <div ref={container} aria-label="Interactive forest map" className="relative z-0 h-[440px] w-full rounded-2xl border border-[#dfe5dd]"/>
}
