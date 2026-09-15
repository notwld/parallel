import axios, { AxiosError, type AxiosInstance, type AxiosRequestConfig } from 'axios';

import { newIdempotencyKey } from '@/api/idempotency';

export type ApiErrorBody = {
  code?: string;
  detail?: string;
  fields?: Record<string, string[]>;
};

export class ApiError extends Error {
  status: number;
  body: ApiErrorBody;

  constructor(status: number, body: ApiErrorBody) {
    super(body.detail || body.code || `HTTP ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.body = body;
  }
}

/** Session cookies + Django CSRF (D005). Prefer Vite `/api` proxy; CORS is fallback. */
export const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  xsrfCookieName: 'csrftoken',
  xsrfHeaderName: 'X-CSRFToken',
  withXSRFToken: true,
  headers: { Accept: 'application/json' },
  timeout: 30_000,
});

http.interceptors.response.use(
  (response) => response,
  (error: AxiosError<ApiErrorBody>) => {
    if (axios.isCancel(error) || error.code === 'ERR_CANCELED') {
      return Promise.reject(error);
    }
    const status = error.response?.status ?? 0;
    const body = error.response?.data ?? { detail: error.message };
    return Promise.reject(new ApiError(status, body));
  },
);

export async function ensureCsrf(): Promise<void> {
  await http.get('/auth/csrf/');
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const { data } = await http.get<T>(path, { signal });
  return data;
}

type SendOptions = {
  signal?: AbortSignal;
  /** When true, attach Idempotency-Key (generated if omitted). */
  idempotent?: boolean;
  idempotencyKey?: string;
  headers?: Record<string, string>;
};

export async function apiSend<T>(
  method: 'post' | 'put' | 'patch' | 'delete',
  path: string,
  body?: unknown,
  options: SendOptions = {},
): Promise<T> {
  const headers: Record<string, string> = { ...options.headers };
  if (options.idempotent) {
    headers['Idempotency-Key'] = options.idempotencyKey || newIdempotencyKey();
  }
  const config: AxiosRequestConfig = {
    method,
    url: path,
    data: body,
    signal: options.signal,
    headers,
  };
  const { data } = await http.request<T>(config);
  return data;
}
