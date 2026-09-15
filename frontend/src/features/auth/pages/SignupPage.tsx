import { Link, useNavigate } from '@tanstack/react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';

import { ApiError } from '@/api/client';
import { queryKeys } from '@/api/query-client';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { signup } from '@/features/auth/api';

export function SignupPage() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  const mutation = useMutation({
    mutationFn: () => signup({ email, password, username: username || undefined }),
    onSuccess: async (account) => {
      client.setQueryData(queryKeys.me, {
        id: account.id,
        username: account.username,
        email: account.email,
        email_verified: account.email_verified,
        preferences: account.preferences,
      });
      if (account.verification_token) {
        toast.message('Account created', {
          description: 'Verification token returned locally (no email provider yet).',
        });
      } else {
        toast.success('Account created');
      }
      await navigate({ to: '/login' });
    },
    onError: (err) => {
      toast.error(err instanceof ApiError ? err.message : 'Could not sign up');
    },
  });

  function onSubmit(e: FormEvent) {
    e.preventDefault();
    mutation.mutate();
  }

  return (
    <AppShell>
      <form onSubmit={onSubmit} className="mx-auto max-w-sm space-y-4 py-6">
        <h1 className="text-2xl font-medium tracking-tight">Sign up</h1>
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
          <Label htmlFor="username">Username (optional)</Label>
          <Input
            id="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={mutation.isPending}>
          {mutation.isPending ? 'Creating…' : 'Create account'}
        </Button>
        <p className="text-sm text-muted-foreground">
          Already have an account?{' '}
          <Link to="/login" className="underline-offset-4 hover:underline">
            Log in
          </Link>
        </p>
      </form>
    </AppShell>
  );
}
