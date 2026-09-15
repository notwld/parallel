import { Link } from '@tanstack/react-router';
import { useMutation, useQuery } from '@tanstack/react-query';
import { toast } from 'sonner';

import { ApiError } from '@/api/client';
import { queryKeys } from '@/api/query-client';
import { AppShell, AuthGate } from '@/components/layout/AppShell';
import { QueryState } from '@/components/loading/QueryState';
import { ListSkeleton } from '@/components/loading/skeletons';
import { Button } from '@/components/ui/button';
import { fetchSessions, revokeSession } from '@/features/auth/api';
import { useSession } from '@/features/auth/hooks';

export function AccountPage() {
  return (
    <AppShell title="Account">
      <AuthGate>
        <AccountBody />
      </AuthGate>
    </AppShell>
  );
}

function AccountBody() {
  const { account } = useSession();
  const sessions = useQuery({
    queryKey: queryKeys.sessions,
    queryFn: ({ signal }) => fetchSessions(signal),
  });
  const revoke = useMutation({
    mutationFn: (id: string) => revokeSession(id),
    onSuccess: () => {
      toast.success('Session revoked');
      void sessions.refetch();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Revoke failed'),
  });

  return (
    <div className="space-y-10">
      <section className="space-y-2">
        <h2 className="text-lg font-medium">Profile</h2>
        <dl className="grid gap-2 text-sm sm:grid-cols-[8rem_1fr]">
          <dt className="text-muted-foreground">Username</dt>
          <dd>{account?.username}</dd>
          <dt className="text-muted-foreground">Email</dt>
          <dd>{account?.email}</dd>
          <dt className="text-muted-foreground">Verified</dt>
          <dd>{account?.email_verified ? 'Yes' : 'No'}</dd>
        </dl>
        <p className="text-sm text-muted-foreground">
          <Link to="/password-reset" className="underline-offset-4 hover:underline">
            Reset password
          </Link>
        </p>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-medium">Sessions</h2>
        <QueryState
          isPending={sessions.isPending}
          isError={sessions.isError}
          onRetry={() => void sessions.refetch()}
          skeleton={<ListSkeleton rows={3} />}
          loadingLabel="Loading sessions"
          isEmpty={!sessions.data?.length}
          emptyTitle="No active sessions"
        >
          <ul className="divide-y divide-border">
            {sessions.data?.map((s) => (
              <li key={s.id} className="flex items-center justify-between gap-3 py-3 text-sm">
                <div>
                  <p className="font-medium">{s.current ? 'This device' : 'Other session'}</p>
                  <p className="text-muted-foreground">
                    {s.user_agent || 'Unknown client'}
                    {s.last_seen_at ? ` · ${new Date(s.last_seen_at).toLocaleString()}` : ''}
                  </p>
                </div>
                {!s.current ? (
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={revoke.isPending}
                    onClick={() => revoke.mutate(s.id)}
                  >
                    Revoke
                  </Button>
                ) : null}
              </li>
            ))}
          </ul>
        </QueryState>
      </section>
    </div>
  );
}
