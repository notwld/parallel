import { useQuery, useQueryClient } from '@tanstack/react-query';

import { fetchMe } from '@/features/auth/api';
import { queryKeys } from '@/api/query-client';

export function useSession() {
  const query = useQuery({
    queryKey: queryKeys.me,
    queryFn: ({ signal }) => fetchMe(signal),
    staleTime: 60_000,
  });
  return {
    account: query.data ?? null,
    isLoading: query.isPending,
    isAuthenticated: Boolean(query.data),
    refetch: query.refetch,
    query,
  };
}

export function useClearSessionCache() {
  const client = useQueryClient();
  return () => {
    client.removeQueries({ queryKey: queryKeys.me });
    client.removeQueries({ queryKey: queryKeys.sessions });
    client.removeQueries({ queryKey: ['chat'] });
    client.removeQueries({ queryKey: ['knowledge'] });
    client.removeQueries({ queryKey: ['worlds'] });
  };
}
