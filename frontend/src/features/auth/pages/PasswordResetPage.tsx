import { Link } from '@tanstack/react-router';
import { useMutation } from '@tanstack/react-query';
import { useState, type FormEvent } from 'react';
import { toast } from 'sonner';

import { ApiError } from '@/api/client';
import { AppShell } from '@/components/layout/AppShell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { confirmPasswordReset, requestPasswordReset } from '@/features/auth/api';

export function PasswordResetPage() {
  const [email, setEmail] = useState('');
  const [token, setToken] = useState('');
  const [password, setPassword] = useState('');
  const [resetToken, setResetToken] = useState<string | null>(null);

  const request = useMutation({
    mutationFn: () => requestPasswordReset(email),
    onSuccess: (body) => {
      toast.success(body.detail);
      if (body.reset_token) setResetToken(body.reset_token);
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Request failed'),
  });

  const confirm = useMutation({
    mutationFn: () => confirmPasswordReset(token || resetToken || '', password),
    onSuccess: (body) => toast.success(body.detail),
    onError: (err) => toast.error(err instanceof ApiError ? err.message : 'Reset failed'),
  });

  function onRequest(e: FormEvent) {
    e.preventDefault();
    request.mutate();
  }

  function onConfirm(e: FormEvent) {
    e.preventDefault();
    confirm.mutate();
  }

  return (
    <AppShell>
      <div className="mx-auto max-w-sm space-y-10 py-6">
        <form onSubmit={onRequest} className="space-y-4">
          <h1 className="text-2xl font-medium tracking-tight">Reset password</h1>
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={request.isPending}>
            {request.isPending ? 'Sending…' : 'Send reset'}
          </Button>
          {resetToken ? (
            <p className="text-xs break-all text-muted-foreground">
              Local reset token: {resetToken}
            </p>
          ) : null}
        </form>

        <form onSubmit={onConfirm} className="space-y-4 border-t border-border pt-8">
          <h2 className="text-lg font-medium">Confirm with token</h2>
          <div className="space-y-2">
            <Label htmlFor="token">Token</Label>
            <Input
              id="token"
              required
              value={token || resetToken || ''}
              onChange={(e) => setToken(e.target.value)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">New password</Label>
            <Input
              id="password"
              type="password"
              required
              minLength={8}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={confirm.isPending}>
            {confirm.isPending ? 'Updating…' : 'Update password'}
          </Button>
        </form>

        <p className="text-sm text-muted-foreground">
          <Link to="/login" className="underline-offset-4 hover:underline">
            Back to login
          </Link>
        </p>
      </div>
    </AppShell>
  );
}
