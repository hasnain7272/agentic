/**
 * API client configuration.
 */

interface ApiResponse<T> {
  data?: T;
  error?: string;
  status: 'accepted' | 'success' | 'error';
}

export function getTenantId() {
  return localStorage.getItem('tenant_id') || '';
}

export function getAuthToken() {
  return localStorage.getItem('auth_token') || '';
}

// Removed getBYOKToken: BYOM configurations are securely stored in the backend DB now.

export const API_BASE_URL = import.meta.env.VITE_API_URL || '';
export const WS_BASE_URL = import.meta.env.VITE_API_URL 
  ? import.meta.env.VITE_API_URL.replace(/^http/, 'ws') 
  : `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}`;

async function request<T>(
  method: string,
  endpoint: string,
  payload?: any,
  options: { headers?: Record<string, string> } = {}
): Promise<ApiResponse<T>> {
  try {
    const token = getAuthToken();
    const tenantId = getTenantId();
    const isFormData = payload instanceof FormData;
    
    const init: RequestInit = {
      method,
      cache: 'no-store',
      headers: {
        ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
        ...(tenantId ? { 'X-Tenant-Id': tenantId } : {}),
        'Cache-Control': 'no-cache',
        ...options.headers,
      },
    };
    
    if (payload !== undefined) {
      init.body = isFormData ? payload : JSON.stringify(payload);
    }
    const response = await fetch(`${API_BASE_URL}/api/v1${endpoint}`, init);
    
    // Global Auth Interceptor: Redirect to login on 401
    if (response.status === 401) {
      console.warn("[SaaS Auth] 401 Unauthorized. Redirecting to login...");
      localStorage.removeItem('auth_token');
      if (!window.location.hash.includes('/login')) {
        window.location.href = '#/login';
      }
    }

    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || data.error || 'API Request Failed');
    return { data, status: response.status === 202 ? 'accepted' : 'success' };
  } catch (e: any) {
    return { error: e.message, status: 'error' };
  }
}

export const apiClient = {
  post<T>(endpoint: string, payload: any, options: { headers?: Record<string, string> } = {}) {
    return request<T>('POST', endpoint, payload, options);
  },
  get<T>(endpoint: string) {
    return request<T>('GET', endpoint);
  },
  patch<T>(endpoint: string, payload: any) {
    return request<T>('PATCH', endpoint, payload);
  },
  delete<T>(endpoint: string) {
    return request<T>('DELETE', endpoint);
  },
};
