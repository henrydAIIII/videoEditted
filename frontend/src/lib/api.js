const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, options)
  const contentType = response.headers.get('content-type') ?? ''
  const payload = contentType.includes('application/json') ? await response.json() : null

  if (!response.ok) {
    const message = payload?.message ?? `请求失败：${response.status}`
    throw new ApiError(message, response.status)
  }

  return payload
}

export async function fetchHealth() {
  return request('/api/health')
}

export async function uploadAssets({ pptVideo, speakerVideo, subtitles }) {
  const formData = new FormData()
  formData.append('ppt_video', pptVideo)
  formData.append('speaker_video', speakerVideo)
  formData.append('subtitles', subtitles)

  return request('/api/upload', {
    method: 'POST',
    body: formData,
  })
}

export async function fetchJobStatus(jobId) {
  try {
    return await request(`/api/status/${jobId}`)
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null
    }
    throw error
  }
}

export function buildDownloadUrl(jobId) {
  return `${API_BASE_URL}/api/download/${jobId}`
}
