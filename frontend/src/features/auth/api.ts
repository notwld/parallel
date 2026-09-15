import { z } from 'zod';

import { apiGet, apiSend, ensureCsrf } from '@/api/client';

export const accountSchema = z.object({
  id: z.string(),
  username: z.string(),
  email: z.string(),
  email_verified: z.boolean(),
  preferences: z.record(z.string(), z.unknown()).optional(),
});

export type Account = z.infer<typeof accountSchema>;

export async function fetchMe(signal?: AbortSignal): Promise<Account | null> {
  try {
    const data = await apiGet<unknown>('/auth/me/', signal);
    return accountSchema.parse(data);
  } catch {
    return null;
  }
}

export async function login(email: string, password: string): Promise<Account> {
  await ensureCsrf();
  const data = await apiSend<unknown>('post', '/auth/login/', { email, password });
  return accountSchema.parse(data);
}

export async function signup(input: {
  email: string;
  password: string;
  username?: string;
}): Promise<Account & { verification_token?: string }> {
  await ensureCsrf();
  const data = await apiSend<unknown>('post', '/auth/signup/', input);
  return accountSchema.extend({ verification_token: z.string().optional() }).parse(data);
}

export async function logout(): Promise<void> {
  await ensureCsrf();
  await apiSend('post', '/auth/logout/', {});
}

export async function requestPasswordReset(email: string) {
  await ensureCsrf();
  return apiSend<{ detail: string; reset_token?: string }>('post', '/auth/password-reset/', {
    email,
  });
}

export async function confirmPasswordReset(token: string, password: string) {
  await ensureCsrf();
  return apiSend<{ detail: string }>('post', '/auth/password-reset/confirm/', {
    token,
    password,
  });
}

export async function verifyEmail(token: string) {
  await ensureCsrf();
  const data = await apiSend<unknown>('post', '/auth/verify-email/', { token });
  return accountSchema.parse(data);
}

const sessionSchema = z.object({
  id: z.string(),
  created_at: z.string().optional(),
  last_seen_at: z.string().optional(),
  current: z.boolean().optional(),
  user_agent: z.string().optional(),
});

export async function fetchSessions(signal?: AbortSignal) {
  const data = await apiGet<{ sessions: unknown }>('/auth/sessions/', signal);
  return z.object({ sessions: z.array(sessionSchema) }).parse(data).sessions;
}

export async function revokeSession(sessionId: string) {
  await ensureCsrf();
  await apiSend('delete', `/auth/sessions/${sessionId}/`);
}
