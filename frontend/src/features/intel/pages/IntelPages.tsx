import { Link, useParams } from '@tanstack/react-router';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';

import { queryKeys } from '@/api/query-client';
import { AppShell, AuthGate } from '@/components/layout/AppShell';
import { QueryState } from '@/components/loading/QueryState';
import { ClaimListSkeleton, FormSkeleton } from '@/components/loading/skeletons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { fetchEvidence, fetchIntelClaim, fetchIntelClaims } from '@/features/intel/api';

export function IntelListPage() {
  const { worldSlug } = useParams({ from: '/w/$worldSlug/intel' });
  return (
    <AppShell title="Intel">
      <AuthGate>
        <IntelListBody slug={worldSlug} />
      </AuthGate>
    </AppShell>
  );
}

function IntelListBody({ slug }: { slug: string }) {
  const [q, setQ] = useState('');
  const [submitted, setSubmitted] = useState('');
  const claims = useQuery({
    queryKey: queryKeys.intelClaims(slug, submitted),
    queryFn: ({ signal }) => fetchIntelClaims(slug, submitted, signal),
  });

  return (
    <div className="space-y-6">
      <form
        className="flex max-w-md gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(q.trim());
        }}
      >
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search claims you know"
          aria-label="Search claims"
        />
        <Button type="submit" variant="outline">
          Search
        </Button>
      </form>

      <QueryState
        isPending={claims.isPending}
        isError={claims.isError}
        errorMessage="Could not load intel."
        onRetry={() => void claims.refetch()}
        skeleton={<ClaimListSkeleton />}
        loadingLabel="Loading intel"
        isEmpty={!claims.data?.length}
        emptyTitle="No claims in your knowledge"
        emptyDescription="Only claims you have encountered appear here. Search never reveals unknown secrets."
      >
        <ul className="divide-y divide-border">
          {claims.data?.map((c) => (
            <li key={c.id} className="py-4">
              <Link
                to="/w/$worldSlug/intel/claims/$claimId"
                params={{ worldSlug: slug, claimId: c.id }}
                className="font-medium text-foreground no-underline hover:underline"
              >
                {c.proposition}
              </Link>
              <p className="mt-1 text-sm text-muted-foreground">
                {c.my_state.stance} · confidence {c.my_state.confidence.toFixed(2)} ·{' '}
                {c.my_state.verification}
              </p>
            </li>
          ))}
        </ul>
      </QueryState>

      <Button asChild variant="ghost" size="sm">
        <Link to="/w/$worldSlug" params={{ worldSlug: slug }}>
          Back to world
        </Link>
      </Button>
    </div>
  );
}

export function IntelClaimPage() {
  const { worldSlug, claimId } = useParams({ from: '/w/$worldSlug/intel/claims/$claimId' });
  return (
    <AppShell title="Claim">
      <AuthGate>
        <ClaimBody slug={worldSlug} claimId={claimId} />
      </AuthGate>
    </AppShell>
  );
}

function ClaimBody({ slug, claimId }: { slug: string; claimId: string }) {
  const claim = useQuery({
    queryKey: queryKeys.intelClaim(slug, claimId),
    queryFn: ({ signal }) => fetchIntelClaim(slug, claimId, signal),
  });

  return (
    <QueryState
      isPending={claim.isPending}
      isError={claim.isError}
      errorMessage="Not found."
      onRetry={() => void claim.refetch()}
      skeleton={<FormSkeleton fields={4} />}
      loadingLabel="Loading claim"
    >
      {claim.data ? (
        <article className="max-w-2xl space-y-4">
          <p className="text-lg leading-relaxed">{claim.data.proposition}</p>
          <dl className="grid gap-2 text-sm sm:grid-cols-[8rem_1fr]">
            <dt className="text-muted-foreground">Stance</dt>
            <dd>{claim.data.my_state.stance}</dd>
            <dt className="text-muted-foreground">Confidence</dt>
            <dd>{claim.data.my_state.confidence.toFixed(2)}</dd>
            <dt className="text-muted-foreground">Verification</dt>
            <dd>{claim.data.my_state.verification}</dd>
            <dt className="text-muted-foreground">Source</dt>
            <dd>{claim.data.sources.map((s) => s.display).join(', ') || '—'}</dd>
          </dl>
          {claim.data.evidence.length ? (
            <ul className="space-y-1 text-sm">
              {claim.data.evidence.map((id) => (
                <li key={id}>
                  <Link
                    to="/w/$worldSlug/intel/evidence/$evidenceId"
                    params={{ worldSlug: slug, evidenceId: id }}
                    className="underline-offset-4 hover:underline"
                  >
                    Evidence {id.slice(0, 8)}…
                  </Link>
                </li>
              ))}
            </ul>
          ) : null}
          <p className="text-sm text-muted-foreground">
            Actions: {claim.data.allowed_actions.join(', ') || 'none'}
          </p>
          <Button asChild variant="ghost" size="sm">
            <Link to="/w/$worldSlug/intel" params={{ worldSlug: slug }}>
              All intel
            </Link>
          </Button>
        </article>
      ) : null}
    </QueryState>
  );
}

export function IntelEvidencePage() {
  const { worldSlug, evidenceId } = useParams({
    from: '/w/$worldSlug/intel/evidence/$evidenceId',
  });
  return (
    <AppShell title="Evidence">
      <AuthGate>
        <EvidenceBody slug={worldSlug} evidenceId={evidenceId} />
      </AuthGate>
    </AppShell>
  );
}

function EvidenceBody({ slug, evidenceId }: { slug: string; evidenceId: string }) {
  const evidence = useQuery({
    queryKey: queryKeys.intelEvidence(slug, evidenceId),
    queryFn: ({ signal }) => fetchEvidence(slug, evidenceId, signal),
  });

  return (
    <QueryState
      isPending={evidence.isPending}
      isError={evidence.isError}
      errorMessage="Not found."
      onRetry={() => void evidence.refetch()}
      skeleton={<FormSkeleton fields={3} />}
      loadingLabel="Loading evidence"
    >
      {evidence.data ? (
        <dl className="grid max-w-lg gap-2 text-sm sm:grid-cols-[8rem_1fr]">
          <dt className="text-muted-foreground">Media</dt>
          <dd>{evidence.data.media_type}</dd>
          <dt className="text-muted-foreground">Visibility</dt>
          <dd>{evidence.data.visibility}</dd>
          <dt className="text-muted-foreground">Created</dt>
          <dd>{new Date(evidence.data.created_at).toLocaleString()}</dd>
        </dl>
      ) : null}
    </QueryState>
  );
}
