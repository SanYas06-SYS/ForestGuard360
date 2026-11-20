import { useEffect, useRef, useState } from 'react'
import { LocateFixed, LoaderCircle, MapPin, Check } from 'lucide-react'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

const valid=value=>value?.latitude!==''&&value?.longitude!==''&&value?.latitude!=null&&value?.longitude!=null&&Number.isFinite(Number(value.latitude))&&Number.isFinite(Number(value.longitude))
export default function LocationPicker({value,onChange,label='Choose a location',compact=false}){
  const container=useRef(null),mapRef=useRef(null),marker=useRef(null),changeRef=useRef(onChange)
  const [locating,setLocating]=useState(false),[error,setError]=useState('')
  changeRef.current=onChange
  useEffect(()=>{
    const map=L.map(container.current,{scrollWheelZoom:false}).setView(valid(value)?[Number(value.latitude),Number(value.longitude)]:[16.7,74.3],valid(value)?15:10)
    mapRef.current=map
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:19,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'}).addTo(map)
    const choose=latlng=>{const point=latlng.wrap();changeRef.current({latitude:Number(point.lat.toFixed(6)),longitude:Number(point.lng.toFixed(6))})}
    map.on('click',event=>choose(event.latlng))
    map.on('keypress',event=>{if(event.originalEvent.key==='Enter'){event.originalEvent.preventDefault();choose(map.getCenter())}})
    const observer=new ResizeObserver(()=>map.invalidateSize());observer.observe(container.current)
    return()=>{observer.disconnect();map.remove();mapRef.current=null;marker.current=null}
  },[])
  useEffect(()=>{
    const map=mapRef.current;if(!map)return
    if(!valid(value)){if(marker.current){marker.current.remove();marker.current=null};return}
    const position=[Number(value.latitude),Number(value.longitude)]
    if(!marker.current){
      marker.current=L.marker(position,{draggable:true,icon:L.divIcon({className:'location-pin',html:'<span></span>',iconSize:[28,36],iconAnchor:[14,36]}),title:'Selected location. Drag to move.',alt:'Selected location'}).addTo(map)
      marker.current.on('dragend',()=>{const point=marker.current.getLatLng().wrap();changeRef.current({latitude:Number(point.lat.toFixed(6)),longitude:Number(point.lng.toFixed(6))})})
    }else marker.current.setLatLng(position)
    if(!map.getBounds().contains(position))map.setView(position,15,{animate:false})
  },[value?.latitude,value?.longitude])
  function locate(){
    if(!navigator.geolocation){setError('Your browser cannot read your location. Choose a point on the map instead.');return}
    setLocating(true);setError('')
    navigator.geolocation.getCurrentPosition(({coords})=>{
      changeRef.current({latitude:Number(coords.latitude.toFixed(6)),longitude:Number(coords.longitude.toFixed(6))})
      mapRef.current?.setView([coords.latitude,coords.longitude],16,{animate:false});setLocating(false)
    },()=>{setError('Location access was unavailable. You can still choose the spot on the map.');setLocating(false)},{enableHighAccuracy:true,timeout:10000,maximumAge:30000})
  }
  return <div className="location-picker"><div className="location-picker-heading"><strong><MapPin size={16}/>{label}</strong><button type="button" onClick={locate} disabled={locating}>{locating?<LoaderCircle size={16} className="animate-spin"/>:<LocateFixed size={16}/>} {locating?'Finding you…':'Use my location'}</button></div><p>Tap the map to place a pin, or drag the pin to the exact spot.</p>{error&&<p role="alert" className="notice error">{error}</p>}<div ref={container} role="region" aria-label={label+' map'} style={{height:compact?230:320}} className="location-picker-map"/><div className="location-picker-status" role="status">{valid(value)?<><Check size={15}/>Location selected<button type="button" onClick={()=>onChange({latitude:'',longitude:''})}>Clear</button></>:<><MapPin size={15}/>Choose a spot on the map</>}</div><p className="location-help">Zoom with + / −. Keyboard: use arrow keys to move the map, then Enter to select its centre.</p></div>
}
