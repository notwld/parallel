import { Link } from '@tanstack/react-router';
import type { ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import { useClearSessionCache, useSession } from '@/features/auth/hooks';
import { logout } from '@/features/auth/api';
import { PageHeaderSkeleton } from '@/components/loading/skeletons';

const nav = [
  { to: '/', label: 'Home' },
  { to: '/w/$worldSlug', params: { worldSlug: 'earth-2097' }, label: 'World' },
  { to: '/chat', label: 'Chat' },
  { to: '/account', label: 'Account' },
] as const;

export function AppShell({ children, title }: { children: ReactNode; title?: string }) {
  const { account, isLoading, isAuthenticated, query } = useSession();
  const clearCache = useClearSessionCache();

  return (
    <div className="min-h-svh">
      <div className="mx-auto max-w-5xl px-[5%] md:px-[7%]">
        <header className="flex flex-wrap items-center justify-between gap-4 border-b border-border py-5">
          <div className="flex flex-wrap items-center gap-6">
            <Link
              to="/"
              className="text-lg font-extrabold tracking-[0.15em] text-foreground no-underline"
            >
              PARALLEL<span className="text-primary"> / </span>
            </Link>
            <nav className="flex flex-wrap gap-3 text-sm" aria-label="Primary">
              {nav.map((item) => (
                <Link
                  key={item.label}
                  to={item.to}
                  params={'params' in item ? item.params : undefined}
                  className="text-muted-foreground no-underline hover:text-foreground"
                  activeProps={{ className: 'text-foreground font-medium no-underline' }}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          </div>
          <div className="flex items-center gap-2">
            {isLoading ? (
              <div className="flex gap-2" aria-hidden>
                <PageHeaderSkeleton />
              </div>
            ) : isAuthenticated ? (
              <>
                <span className="hidden text-sm text-muted-foreground sm:inline">
                  {account?.username}
                </span>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  onClick={async () => {
                    await logout();
                    clearCache();
                    await query.refetch();
                  }}
                >
                  Log out
                </Button>
              </>
            ) : (
              <>
                <Button type="button" size="sm" variant="ghost" asChild>
                  <Link to="/login">Log in</Link>
                </Button>
                <Button type="button" size="sm" asChild>
                  <Link to="/signup">Sign up</Link>
                </Button>
              </>
            )}
          </div>
        </header>
        {title ? (
          <h1 className="pt-8 text-2xl font-medium tracking-tight">{title}</h1>
        ) : null}
        <div className="py-6">{children}</div>
      </div>
    </div>
  );
}

export { AuthGate } from '@/components/layout/AuthGate';
