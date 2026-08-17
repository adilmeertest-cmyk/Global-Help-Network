const API = import.meta.env.VITE_API_URL || ''

export type ApiOptions = RequestInit & { auth?: boolean; retry?: boolean }

function formatApiError(json: any, fallback = 'Something went wrong') {
  if (typeof json?.detail === 'string') {
    const known: Record<string, string> = {
      DUPLICATE_EMAIL: 'This email is already registered. Please sign in instead.',
      DUPLICATE_USERNAME: 'This username is already taken. Please choose another one.',
      TOKEN_INVALID: 'Your session is invalid. Please sign in again.',
      TOKEN_EXPIRED: 'Your session has expired. Please sign in again.',
      FORBIDDEN: 'You do not have permission to perform this action.',
    }
    return known[json.detail] || json.detail
  }
  if (Array.isArray(json?.detail)) {
    return json.detail.map((item: any) => {
      const field = Array.isArray(item?.loc) ? item.loc.filter((x: unknown) => x !== 'body').join('.') : ''
      return `${field ? `${field}: ` : ''}${item?.msg || 'Invalid value'}`
    }).join(' • ')
  }
  return json?.message || fallback
}

async function refreshAccessToken() {
  const refresh = localStorage.getItem('ghn_refresh_token')
  if (!refresh) return false
  try {
    const res = await fetch(`${API}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refresh }),
    })
    const json = await res.json().catch(() => null)
    if (!res.ok || !json?.data?.access_token) return false
    localStorage.setItem('ghn_access_token', json.data.access_token)
    if (json.data.refresh_token) localStorage.setItem('ghn_refresh_token', json.data.refresh_token)
    return true
  } catch {
    return false
  }
}

export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const { auth: useAuth = true, retry = true, ...request } = options
  const headers = new Headers(request.headers)
  if (request.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const access = localStorage.getItem('ghn_access_token')
  if (useAuth && access) headers.set('Authorization', `Bearer ${access}`)

  let res: Response
  try {
    res = await fetch(`${API}${path}`, { ...request, headers })
  } catch {
    throw new Error('Unable to reach the server. Please check the deployment and try again.')
  }

  if (res.status === 401 && useAuth && retry && localStorage.getItem('ghn_refresh_token')) {
    if (await refreshAccessToken()) return api<T>(path, { ...options, retry: false })
    clearSession()
  }

  if (res.status === 204) return undefined as T

  const contentType = res.headers.get('content-type') || ''
  const json = contentType.includes('application/json')
    ? await res.json().catch(() => null)
    : null

  if (!res.ok) {
    if (json) throw new Error(formatApiError(json, `Request failed (${res.status})`))
    if (res.status >= 500) throw new Error('The backend is currently unavailable. Please check the server/database configuration.')
    throw new Error(`Request failed (${res.status})`)
  }

  if (!json) throw new Error('The server returned an invalid response.')
  return json
}

export type User = { id:number; name:string; username:string; email?:string; role:string; account_status?:string; country?:string; city?:string; bio?:string; skills?:string[]; interests?:string[]; profile_picture_url?:string; reputation_score?:number; helpful_answers_count?:number; solved_requests_count?:number }
export type Category = { id:number; name:string; slug:string; description?:string; icon?:string }
export type HelpRequest = { id:number; title:string; description:string; status:string; urgency:string; help_type:string; country?:string; city?:string; category_id:number; author?:User; answers_count?:number; comments_count?:number; created_at?:string; updated_at?:string }

export const auth = {
  login: (login:string,password:string) => api<{data:{user:User;access_token:string;refresh_token:string}}>('/api/v1/auth/login',{method:'POST',body:JSON.stringify({login,password}),auth:false}),
  register: (payload:Record<string,unknown>) => api<{data:{user:User;access_token:string;refresh_token:string}}>('/api/v1/auth/register',{method:'POST',body:JSON.stringify(payload),auth:false}),
  me: () => api<{data:User}>('/api/v1/users/me'),
  logout: () => api('/api/v1/auth/logout',{method:'POST',body:JSON.stringify({refresh_token:localStorage.getItem('ghn_refresh_token')||''}),auth:false,retry:false})
}

export const data = {
  feed: (mode='newest',q='',categoryId?:number) => api<{data:HelpRequest[];meta:{pages:number}}>(`/api/v1/feed?mode=${encodeURIComponent(mode)}&page_size=30${categoryId ? `&category_id=${categoryId}` : ''}`,{auth:false}).then(result => {
    if (!q.trim()) return result
    const needle = q.trim().toLowerCase()
    return { ...result, data: result.data.filter(item => `${item.title} ${item.description}`.toLowerCase().includes(needle)) }
  }),
  categories: () => api<{data:Category[]}>('/api/v1/categories',{auth:false}),
  request: (id:number) => api<{data:HelpRequest}>(`/api/v1/help-requests/${id}`,{auth:false}),
  answers: (id:number) => api<{data:Array<{id:number;content:string;helpful_count:number;is_best_answer:boolean;user?:User}>}>(`/api/v1/help-requests/${id}/answers`,{auth:false}),
  createRequest: (payload:Record<string,unknown>) => api<{data:HelpRequest}>('/api/v1/help-requests',{method:'POST',body:JSON.stringify(payload)}),
  answer: (id:number,content:string) => api(`/api/v1/help-requests/${id}/answers`,{method:'POST',body:JSON.stringify({content})}),
  helpful: (id:number) => api(`/api/v1/answers/${id}/helpful`,{method:'POST'}),
  best: (id:number) => api(`/api/v1/answers/${id}/best`,{method:'PATCH'}),
  notifications: () => api<{data:Array<{id:number;title:string;body:string;is_read:boolean;created_at:string}>}>(`/api/v1/notifications`),
  conversations: () => api<{data:Array<{id:number;other_user_id:number;last_message_at?:string}>}>(`/api/v1/conversations`),
  messages: (id:number) => api<{data:Array<{id:number;sender_id:number;receiver_id:number;content:string;read_at?:string;created_at:string}>}>(`/api/v1/conversations/${id}/messages`),
  sendMessage: (id:number,content:string) => api(`/api/v1/conversations/${id}/messages`,{method:'POST',body:JSON.stringify({content})}),
  markConversationRead: (id:number) => api(`/api/v1/conversations/${id}/read`,{method:'PATCH'}),
  markNotificationRead: (id:number) => api(`/api/v1/notifications/${id}/read`,{method:'PATCH'}),
  markAllNotificationsRead: () => api('/api/v1/notifications/read-all',{method:'PATCH'}),
  adminStats: () => api<{data:Record<string,number>}>('/api/v1/admin/dashboard/stats'),
  adminUsers: (q='') => api<{data:User[]}>('/api/v1/admin/users?page_size=100'+(q ? `&q=${encodeURIComponent(q)}` : '')),
  adminReports: () => api<{data:Array<{id:number;reporter_id:number;target_type:string;target_id:number;reason:string;status:string;review_note?:string;created_at:string}>}>('/api/v1/admin/reports?page_size=100'),
  adminUserStatus: (id:number,status:string) => api(`/api/v1/admin/users/${id}/status`,{method:'PATCH',body:JSON.stringify({status})}),
  adminReportStatus: (id:number,status:string) => api(`/api/v1/admin/reports/${id}`,{method:'PATCH',body:JSON.stringify({status})}),
}

export function saveSession(data:{user:User;access_token:string;refresh_token:string}) {
  localStorage.setItem('ghn_access_token',data.access_token)
  localStorage.setItem('ghn_refresh_token',data.refresh_token)
  localStorage.setItem('ghn_user',JSON.stringify(data.user))
}
export function clearSession(){localStorage.removeItem('ghn_access_token');localStorage.removeItem('ghn_refresh_token');localStorage.removeItem('ghn_user')}
export function cachedUser():User|null { try{return JSON.parse(localStorage.getItem('ghn_user')||'null')}catch{return null} }
