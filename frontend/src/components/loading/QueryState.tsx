import type { ReactNode } from 'react';

import { Button } from '@/components/ui/button';

type QueryStateProps = {
  isPending: boolean;
  isError: boolean;
  isEmpty?: boolean;
  errorMessage?: string;
  emptyTitle?: string;
  emptyDescription?: string;
  onRetry?: () => void;
  skeleton: ReactNode;
  children: ReactNode;
  /** Concise status for AT; one per region. */
  loadingLabel?: string;
};

/**
 * Pending → layout-matched skeleton (aria-busy).
 * Error → recovery. Empty → teach. Loaded → children.
 */
export function QueryState({
  isPending,
  isError,
  isEmpty = false,
  errorMessage = 'Something went wrong.',
  emptyTitle = 'Nothing here yet',
  emptyDescription,
  onRetry,
  skeleton,
  children,
  loadingLabel = 'Loading',
}: QueryStateProps) {
  if (isPending) {
    return (
      <div role="status" aria-busy="true" aria-live="polite">
        <span className="sr-only">{loadingLabel}</span>
        {skeleton}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-3 py-8" role="alert">
        <p className="text-sm text-destructive">{errorMessage}</p>
        {onRetry ? (
          <Button type="button" variant="outline" size="sm" onClick={onRetry}>
            Try again
          </Button>
        ) : null}
      </div>
    );
  }

  if (isEmpty) {
    return (
      <div className="space-y-2 py-10">
        <h2 className="text-lg font-medium tracking-tight">{emptyTitle}</h2>
        {emptyDescription ? (
          <p className="max-w-md text-sm text-muted-foreground">{emptyDescription}</p>
        ) : null}
      </div>
    );
  }

  return <>{children}</>;
}
