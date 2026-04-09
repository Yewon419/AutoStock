const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001/api/v1'

async function request(method, path, body = null) {
  const token = localStorage.getItem('token')
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = `Bearer ${token}`

  const res = await fetch(`${BASE_URL}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : null,
  })

  if (!res.ok) {
    if (res.status === 401) throw new Error('UNAUTHORIZED')
    const err = await res.json().catch(() => ({ detail: '오류가 발생했습니다' }))
    throw new Error(err.detail || '오류가 발생했습니다')
  }

  return res.json()
}

export const api = {
  get: (path) => request('GET', path),
  post: (path, body) => request('POST', path, body),
  put: (path, body) => request('PUT', path, body),
  delete: (path) => request('DELETE', path),
}
