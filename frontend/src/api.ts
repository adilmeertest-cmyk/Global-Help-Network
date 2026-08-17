const API = import.meta.env.VITE_API_URL || ''

type ApiOptions = RequestInit & { auth?: boolean }
export async function api<T>(path: string, options: ApiOptions = {}): Promise<T> {
  const headers = new Headers(options.headers)
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  const access = localStorage.getItem('ghn_access_token')
  if (options.auth !== false && access) headers.set('Authorization', `Bearer ${access}`)
  const res = await fetch(`${API}${path}`, { ...options, headers })
  if (res.status === 204) return undefined as T
  const json = await res.json().catch(() => ({ detail: 'Unexpected server response' }))
  if (!res.ok) throw new Error(json.detail || json.message || 'Something went wrong')
  return json
}

export type User = { id:number; name:string; username:string; email?:string; role:string; country?:string; city?:string; reputation_score?:number; solved_requests_count?:number }
export type Category = { id:number; name:string; slug:string; description?:string; icon?:string }
export type HelpRequest = { id:number; title:string; description:string; status:string; urgency:string; help_type:string; country?:string; city?:string; category_id:number; author?:User; answers_count?:number; comments_count?:number; created_at?:string }

export const auth = {
  login: (login:string,password:string) => api<{data:{user:User;access_token:string;refresh_token:string}}>('/api/v1/auth/login',{method:'POST',body:JSON.stringify({login,password}),auth:false}),
  register: (payload:Record<string,unknown>) => api<{data:{user:User;access_token:string;refresh_token:string}}>('/api/v1/auth/register',{method:'POST',body:JSON.stringify(payload),auth:false}),
  me: () => api<{data:User}>('/api/v1/users/me'),
  logout: () => api('/api/v1/auth/logout',{method:'POST',body:JSON.stringify({refresh_token:localStorage.getItem('ghn_refresh_token')||''})})
}
export const data = {
  feed: (mode='newest',q='') => api<{data:HelpRequest[];meta:{pages:number}}>('/api/v1/feed?mode='+encodeURIComponent(mode)+'&page_size=30'+(q?'&q='+encodeURIComponent(q):''),{auth:false}),
  categories: () => api<{data:Category[]}>('/api/v1/categories',{auth:false}),
  request: (id:number) => api<{data:HelpRequest}>(`/api/v1/help-requests/${id}`,{auth:false}),
  answers: (id:number) => api<{data:Array<{id:number;content:string;helpful_count:number;is_best_answer:boolean;user?:User}>>>(`/api/v1/help-requests/${id}/answers`,{auth:false}),
  createRequest: (payload:Record<string,unknown>) => api<{data:HelpRequest}>('/api/v1/help-requests',{method:'POST',body:JSON.stringify(payload)}),
  answer: (id:number,content:string) => api(`/api/v1/help-requests/${id}/answers`,{method:'POST',body:JSON.stringify({content})}),
  helpful: (id:number) => api(`/api/v1/answers/${id}/helpful`,{method:'POST'}),
  best: (id:number) => api(`/api/v1/answers/${id}/best`,{method:'PATCH'}),
  notifications: () => api<{data:Array<{id:number;title:string;body:string;is_read:boolean;created_at:string}>}>('/api/v1/notifications'),
  conversations: () => api<{data:Array<{id:number;title?:string;updated_at:string}>}>('/api/v1/conversations'),
}
export function saveSession(data:{user:User;access_token:string;refresh_token:string}) { localStorage.setItem('ghn_access_token',data.access_token); localStorage.setItem('ghn_refresh_token',data.refresh_token); localStorage.setItem('ghn_user',JSON.stringify(data.user)) }
export function clearSession(){localStorage.removeItem('ghn_access_token');localStorage.removeItem('ghn_refresh_token');localStorage.removeItem('ghn_user')}
export function cachedUser():User|null { try{return JSON.parse(localStorage.getItem('ghn_user')||'null')}catch{return null} }
