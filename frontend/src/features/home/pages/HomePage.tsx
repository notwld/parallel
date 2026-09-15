import { Link } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';

import { queryKeys } from '@/api/query-client';
import { AppShell } from '@/components/layout/AppShell';
import { QueryState } from '@/components/loading/QueryState';
import { ListSkeleton } from '@/components/loading/skeletons';
import { Button } from '@/components/ui/button';
import { fetchHealth } from '@/features/home/api/health';

export function HomePage() {
  const health = useQuery({
    queryKey: queryKeys.health,
    queryFn: ({ signal }) => fetchHealth(signal),
  });

  return (
    <AppShell>
      <section className="py-10 md:py-16" aria-labelledby="title">
        <h1
          id="title"
          className="max-w-[14ch] text-[clamp(2.5rem,6vw,4.5rem)] leading-[1.08] font-normal tracking-[-0.04em]"
        >
          Another world is happening.
        </h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-muted-foreground">
          Discover information. Decide who to trust. Change what happens next.
        </p>
        <div className="mt-8 flex flex-wrap gap-3">
          <Button type="button" size="lg" asChild>
            <Link to="/w/$worldSlug" params={{ worldSlug: 'earth-2097' }}>
              Enter Earth-2097
            </Link>
          </Button>
          <Button type="button" size="lg" variant="outline" asChild>
            <Link to="/chat">Open chat</Link>
          </Button>
        </div>
      </section>

      <section className="border-t border-border py-10" aria-labelledby="status-title">
        <h2 id="status-title" className="text-lg font-medium tracking-tight">
          System
        </h2>
        <QueryState
          isPending={health.isPending}
          isError={health.isError}
          errorMessage="API offline — start the backend to connect."
          onRetry={() => void health.refetch()}
          skeleton={<ListSkeleton rows={1} />}
          loadingLabel="Checking API"
        >
          <p className="mt-3 text-sm text-muted-foreground" role="status">
            {health.data?.status === 'ok' ? 'API connected' : 'Unexpected health response'}
          </p>
        </QueryState>
      </section>
    </AppShell>
  );
}
