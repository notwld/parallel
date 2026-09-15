import { Link } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import { useSession } from '@/features/auth/hooks';
import { QueryState } from '@/components/loading/QueryState';
import { FormSkeleton } from '@/components/loading/skeletons';
import { Button } from '@/components/ui/button';

export function AuthGate({ children }: { children: ReactNode }) {
  const { isLoading, isAuthenticated, query } = useSession();

  if (isLoading) {
    return (
      <QueryState
        isPending
        isError={false}
        skeleton={<FormSkeleton fields={2} />}
        loadingLabel="Checking session"
      >
        {null}
      </QueryState>
    );
  }

  if (query.isError) {
    return (
      <QueryState
        isPending={false}
        isError
        errorMessage="Could not verify your session."
        onRetry={() => void query.refetch()}
        skeleton={null}
      >
        {null}
      </QueryState>
    );
  }

  if (!isAuthenticated) {
    return (
      <div className="space-y-3 py-8">
        <h2 className="text-lg font-medium">Sign in required</h2>
        <p className="text-sm text-muted-foreground">Log in to continue to this area of Parallel.</p>
        <Button asChild>
          <Link to="/login">Log in</Link>
        </Button>
      </div>
    );
  }

  return <>{children}</>;
}
