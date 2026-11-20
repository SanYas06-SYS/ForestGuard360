import { api } from './api.js'

export async function uploadReportImage(file) {
  const form = new FormData()
  form.append('image', file)
  return api('/api/uploads/report-image', { method: 'POST', body: form })
}
