import { Link, useNavigate } from '@tanstack/react-router';
import { useMutation } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';

import { ApiError } from '@/api/client';
import { queryKeys } from '@/api/query-client';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { login } from '@/features/auth/api';
import { useClearSessionCache } from '@/features/auth/hooks';
import { useQueryClient } from '@tanstack/react-query';

export function LoginPage() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const clear = useClearSessionCache();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const mutation = useMutation({
    mutationFn: () => login(email, password),
    onSuccess: async (account) => {
      clear();
      client.setQueryData(queryKeys.me, account);
      toast.success('Signed in');
      await navigate({ to: '/account' });
    },
    onError: (err) => {
      const msg = err instanceof ApiError ? err.message : 'Could not sign in';
      toast.error(msg);
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <AppShell>
      <form onSubmit={onSubmit} className="mx-auto max-w-sm space-y-4 py-6">
        <h1 className="text-2xl font-medium tracking-tight">Log in</h1>
        <p className="text-sm text-muted-foreground">Session cookies stay HttpOnly. CSRF on every write.</p>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? 'Signing in…' : 'Sign in'}
        </Button>
        <p className="text-sm text-muted-foreground">
          <Link to="/signup" className="underline-offset-4 hover:underline">
            Create an account
          </Link>
          {' · '}
          <Link to="/password-reset" className="underline-offset-4 hover:underline">
            Reset password
          </Link>
        </p>
      </form>
    </AppShell>
  );
}
