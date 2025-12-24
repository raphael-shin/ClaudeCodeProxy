const API_URL = process.env.NEXT_PUBLIC_BACKEND_API_URL || 'http://localhost:8000';

class ApiClient {
  private token: string | null = null;

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('token', token);
    }
  }

  getToken(): string | null {
    if (!this.token && typeof window !== 'undefined') {
      this.token = localStorage.getItem('token');
    }
    return this.token;
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('token');
    }
  }

  private async fetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(options.headers as Record<string, string>),
    };

    if (this.getToken()) {
      headers['Authorization'] = `Bearer ${this.getToken()}`;
    }

    const res = await fetch(`${API_URL}${path}`, { ...options, headers });

    if (res.status === 401) {
      this.clearToken();
      if (typeof window !== 'undefined') {
        window.location.href = '/login';
      }
      throw new Error('Unauthorized');
    }

    if (!res.ok) {
      throw new Error(`API error: ${res.status}`);
    }

    if (res.status === 204) return {} as T;
    return res.json();
  }

  async login(username: string, password: string): Promise<{ access_token: string }> {
    const credentials = btoa(`${username}:${password}`);
    const res = await fetch(`${API_URL}/admin/auth/login`, {
      method: 'POST',
      headers: { Authorization: `Basic ${credentials}` },
    });
    if (!res.ok) throw new Error('Login failed');
    const data = await res.json();
    this.setToken(data.access_token);
    return data;
  }

  // Users
  getUsers = () => this.fetch<User[]>('/admin/users');
  getUser = (id: string) => this.fetch<User>(`/admin/users/${id}`);
  createUser = (data: { name: string; description?: string }) =>
    this.fetch<User>('/admin/users', { method: 'POST', body: JSON.stringify(data) });
  deactivateUser = (id: string) =>
    this.fetch<User>(`/admin/users/${id}/deactivate`, { method: 'POST' });
  deleteUser = (id: string) =>
    this.fetch<void>(`/admin/users/${id}`, { method: 'DELETE' });

  // Access Keys
  getAccessKeys = (userId: string) =>
    this.fetch<AccessKey[]>(`/admin/users/${userId}/access-keys`);
  createAccessKey = (
    userId: string,
    data: { bedrock_region?: string; bedrock_model?: string } = {}
  ) =>
    this.fetch<AccessKey>(`/admin/users/${userId}/access-keys`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  revokeAccessKey = (keyId: string) =>
    this.fetch<void>(`/admin/access-keys/${keyId}`, { method: 'DELETE' });
  rotateAccessKey = (keyId: string) =>
    this.fetch<AccessKey>(`/admin/access-keys/${keyId}/rotate`, { method: 'POST' });
  registerBedrockKey = (keyId: string, bedrockApiKey: string) =>
    this.fetch<{ status: string }>(`/admin/access-keys/${keyId}/bedrock-key`, {
      method: 'POST',
      body: JSON.stringify({ bedrock_api_key: bedrockApiKey }),
    });

  // Usage
  getUsage = (params: UsageParams) => {
    const query = new URLSearchParams();
    if (params.user_id) query.set('user_id', params.user_id);
    if (params.access_key_id) query.set('access_key_id', params.access_key_id);
    if (params.bucket_type) query.set('bucket_type', params.bucket_type);
    if (params.start_time) query.set('start_time', params.start_time);
    if (params.end_time) query.set('end_time', params.end_time);
    return this.fetch<UsageResponse>(`/admin/usage?${query}`);
  };

  getTopUsers = (params: UsageParams & { limit?: number }) => {
    const query = new URLSearchParams();
    if (params.bucket_type) query.set('bucket_type', params.bucket_type);
    if (params.start_time) query.set('start_time', params.start_time);
    if (params.end_time) query.set('end_time', params.end_time);
    if (params.limit) query.set('limit', String(params.limit));
    return this.fetch<UsageTopUser[]>(`/admin/usage/top-users?${query}`);
  };
}

export const api = new ApiClient();

export interface User {
  id: string;
  name: string;
  description: string | null;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface AccessKey {
  id: string;
  key_prefix: string;
  status: string;
  bedrock_region: string;
  bedrock_model: string;
  created_at: string;
  raw_key?: string;
}

export interface UsageParams {
  user_id?: string;
  access_key_id?: string;
  bucket_type?: string;
  start_time?: string;
  end_time?: string;
}

export interface UsageBucket {
  bucket_start: string;
  requests: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
}

export interface UsageResponse {
  buckets: UsageBucket[];
  total_requests: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_tokens: number;
}

export interface UsageTopUser {
  user_id: string;
  name: string;
  total_tokens: number;
  total_requests: number;
}
