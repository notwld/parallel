import { QueryClient } from '@tanstack/react-query';

import { ApiError } from '@/api/client';

function retryDelay(attempt: number) {
  // Exponential backoff, capped; jitter to avoid herds.
  const base = Math.min(1000 * 2 ** attempt, 30_000);
  return base * (0.5 + Math.random() * 0.5);
}

function shouldRetryQuery(failureCount: number, error: Error) {
  if (failureCount >= 2) return false;
  if (error instanceof ApiError) {
    if (error.status === 401 || error.status === 403 || error.status === 404) return false;
    if (error.status === 429) return true;
    if (error.status >= 500) return true;
    return false;
  }
  return true;
}

/** Clear on logout / world switch (P012 / D019). */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        retry: shouldRetryQuery,
        retryDelay,
        refetchOnWindowFocus: true,
        networkMode: 'online',
      },
      mutations: {
        retry: (failureCount, error) => {
          if (failureCount >= 1) return false;
          if (error instanceof ApiError && error.status === 429) return true;
          if (error instanceof ApiError && error.status >= 500) return true;
          return false;
        },
        retryDelay,
        networkMode: 'online',
      },
    },
  });
}

export const queryKeys = {
  health: ['health'] as const,
  me: ['auth', 'me'] as const,
  sessions: ['auth', 'sessions'] as const,
  worldLanding: (slug: string) => ['worlds', slug, 'landing'] as const,
  worldCharacter: (slug: string) => ['worlds', slug, 'character'] as const,
  chatServers: ['chat', 'servers'] as const,
  chatChannels: (serverId: string | number) => ['chat', 'servers', String(serverId), 'channels'] as const,
  chatMessages: (channelId: string | number) => ['chat', 'channels', String(channelId), 'messages'] as const,
  intelClaims: (slug: string, q = '') => ['knowledge', slug, 'intel', 'claims', q] as const,
  intelClaim: (slug: string, claimId: string) => ['knowledge', slug, 'intel', 'claims', claimId] as const,
  intelEvidence: (slug: string, evidenceId: string) =>
    ['knowledge', slug, 'intel', 'evidence', evidenceId] as const,
};

/** Serial scope so channel sends never race each other. */
export const mutationScopes = {
  chatSend: (channelId: string | number) => ({ id: `chat-send:${channelId}` }),
  worldJoin: (slug: string) => ({ id: `world-join:${slug}` }),
};
