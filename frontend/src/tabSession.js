// Browsers can copy sessionStorage when duplicating a tab or opening via an opener.
// Ask an already-open document whether it owns this tab ID before restoring login.
let initialization
export function initializeTabSession() {
  if (initialization) return initialization
  initialization = new Promise(resolve => {
    const key = 'vanrakshak:tab-id'
    let id = sessionStorage.getItem(key) || crypto.randomUUID()
    sessionStorage.setItem(key, id)
    if (!('BroadcastChannel' in window)) { resolve(); return }
    const instance = crypto.randomUUID()
    const channel = new BroadcastChannel('vanrakshak-tabs')
    let ready = false
    channel.onmessage = ({ data }) => {
      if (data.id !== id || data.instance === instance) return
      if (data.type === 'claim' && (ready || instance < data.instance)) {
        channel.postMessage({ type: 'occupied', id, instance, target: data.instance })
      }
      if (data.type === 'occupied' && data.target === instance && !ready) {
        sessionStorage.removeItem('vanrakshak:tab-session')
        id = crypto.randomUUID()
        sessionStorage.setItem(key, id)
      }
    }
    channel.postMessage({ type: 'claim', id, instance })
    setTimeout(() => { ready = true; resolve() }, 180)
    window.addEventListener('pagehide', () => channel.close(), { once: true })
  })
  return initialization
}
