import { Link, useParams } from '@tanstack/react-router';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';

import { ApiError } from '@/api/client';
import { mutationScopes, queryKeys } from '@/api/query-client';
import { AppShell } from '@/components/layout/AppShell';
import { QueryState } from '@/components/loading/QueryState';
import { FormSkeleton, ListSkeleton } from '@/components/loading/skeletons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useSession } from '@/features/auth/hooks';
import { fetchMyCharacter, fetchWorldLanding, joinWorld } from '@/features/worlds/api';

export function WorldPage() {
  const { worldSlug } = useParams({ from: '/w/$worldSlug' });
  return (
    <AppShell>
      <WorldBody slug={worldSlug} />
    </AppShell>
  );
}

function WorldBody({ slug }: { slug: string }) {
  const { isAuthenticated, isLoading: authLoading } = useSession();
  const client = useQueryClient();
  const landing = useQuery({
    queryKey: queryKeys.worldLanding(slug),
    queryFn: ({ signal }) => fetchWorldLanding(slug, signal),
  });
  const character = useQuery({
    queryKey: queryKeys.worldCharacter(slug),
    queryFn: ({ signal }) => fetchMyCharacter(slug, signal),
    enabled: isAuthenticated,
  });

  const [roleId, setRoleId] = useState('');
  const [displayName, setDisplayName] = useState('');

  const join = useMutation({
    scope: mutationScopes.worldJoin(slug),
    mutationFn: () =>
      joinWorld(slug, {
        role_template_id: roleId,
        display_name: displayName,
      }),
    onSuccess: (char) => {
      client.setQueryData(queryKeys.worldCharacter(slug), char);
      toast.success(`Joined as ${char.display_name}`);
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : 'Could not join');
    },
  });

  function onJoin(e: FormEvent) {
    e.preventDefault();
    if (!roleId) {
      toast.error('Choose a role');
      return;
    }
    join.mutate();
  }

  const joined = Boolean(character.data);

  return (
    <div className="space-y-10">
      <QueryState
        isPending={landing.isPending}
        isError={landing.isError}
        errorMessage="World not found or unavailable."
        onRetry={() => void landing.refetch()}
        skeleton={<FormSkeleton fields={4} />}
        loadingLabel="Loading world"
      >
        {landing.data ? (
          <section className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {landing.data.status} · {landing.data.population} members · world time{' '}
              {new Date(landing.data.world_time).toLocaleString()}
            </p>
            <h1 className="text-3xl font-medium tracking-tight md:text-4xl">{landing.data.title}</h1>
            <p className="max-w-2xl text-lg leading-relaxed text-muted-foreground">
              {landing.data.premise}
            </p>
            <div className="flex flex-wrap gap-3">
              <Button asChild variant="outline">
                <Link to="/w/$worldSlug/intel" params={{ worldSlug: slug }}>
                  Intel
                </Link>
              </Button>
            </div>
          </section>
        ) : null}
      </QueryState>

      {isAuthenticated ? (
        <QueryState
          isPending={authLoading || character.isPending}
          isError={character.isError}
          onRetry={() => void character.refetch()}
          skeleton={<ListSkeleton rows={2} />}
          loadingLabel="Loading character"
        >
          {joined && character.data ? (
            <section className="space-y-3 border-t border-border pt-8">
              <h2 className="text-lg font-medium">Your character</h2>
              <dl className="grid gap-2 text-sm sm:grid-cols-[8rem_1fr]">
                <dt className="text-muted-foreground">Name</dt>
                <dd>{character.data.display_name}</dd>
                <dt className="text-muted-foreground">Role</dt>
                <dd>{character.data.role_name}</dd>
                <dt className="text-muted-foreground">Status</dt>
                <dd>{character.data.status}</dd>
              </dl>
              {character.data.capability_codes.length ? (
                <p className="text-sm text-muted-foreground">
                  Capabilities: {character.data.capability_codes.join(', ')}
                </p>
              ) : null}
            </section>
          ) : (
            <section className="space-y-4 border-t border-border pt-8">
              <h2 className="text-lg font-medium">Join this world</h2>
              <form onSubmit={onJoin} className="max-w-md space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="display_name">Display name</Label>
                  <Input
                    id="display_name"
                    required
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                  />
                </div>
                <fieldset className="space-y-3">
                  <legend className="text-sm font-medium">Choose a role</legend>
                  <div className="space-y-2">
                    {(landing.data?.roles || [])
                      .filter((role) => role.claimable && !role.invite_only)
                      .map((role) => (
                      <label
                        key={role.id}
                        className="flex cursor-pointer gap-3 rounded-lg border border-border p-3 has-[:checked]:border-primary"
                      >
                        <input
                          type="radio"
                          name="role"
                          value={role.id}
                          checked={roleId === role.id}
                          onChange={() => setRoleId(role.id)}
                          className="mt-1"
                        />
                        <span>
                          <span className="block font-medium">{role.name}</span>
                          {role.description ? (
                            <span className="text-sm text-muted-foreground">{role.description}</span>
                          ) : null}
                        </span>
                      </label>
                    ))}
                  </div>
                </fieldset>
                <Button type="submit" disabled={join.isPending || !landing.data?.roles.length}>
                  {join.isPending ? 'Joining…' : 'Join world'}
                </Button>
              </form>
            </section>
          )}
        </QueryState>
      ) : (
        <section className="border-t border-border pt-8">
          <p className="text-sm text-muted-foreground">Sign in to join this world.</p>
          <Button asChild className="mt-3">
            <Link to="/login">Log in</Link>
          </Button>
        </section>
      )}
    </div>
  );
}
