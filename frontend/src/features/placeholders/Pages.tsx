import { Link, useParams } from '@tanstack/react-router';

import { AppShell, AuthGate } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { FormSkeleton } from '@/components/loading/skeletons';
import { QueryState } from '@/components/loading/QueryState';

/** Placeholder until FE062 world API wiring lands. */
export function WorldPlaceholderPage() {
  const { worldSlug } = useParams({ from: '/w/$worldSlug' });
  return (
    <AppShell title={`World · ${worldSlug}`}>
      <QueryState
        isPending={false}
        isError={false}
        skeleton={<FormSkeleton />}
        isEmpty
        emptyTitle="World surface loading next"
        emptyDescription="Landing, join, and character panels wire to /api/v1/worlds/ in FE062."
      >
        {null}
      </QueryState>
      <Button asChild variant="outline" className="mt-4">
        <Link to="/">Back home</Link>
      </Button>
    </AppShell>
  );
}

export function ChatPlaceholderPage() {
  return (
    <AppShell title="Chat">
      <AuthGate>
        <QueryState
          isPending={false}
          isError={false}
          skeleton={<FormSkeleton />}
          isEmpty
          emptyTitle="Chat surface loading next"
          emptyDescription="Servers, channels, WebSocket timeline, and typing land in FE063."
        >
          {null}
        </QueryState>
      </AuthGate>
    </AppShell>
  );
}
