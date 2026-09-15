import { Button } from '@/components/ui/button';
import type { SocketStatus } from '@/realtime/channel-socket';

export function ConnectionBanner({
  status,
  onRetry,
}: {
  status: SocketStatus;
  onRetry?: () => void;
}) {
  if (status === 'open' || status === 'idle' || status === 'closed') return null;

  if (status === 'failed') {
    return (
      <div
        className="flex items-center justify-between gap-3 border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-sm"
        role="alert"
      >
        <span>Connection lost. Messages may be delayed.</span>
        {onRetry ? (
          <Button type="button" size="xs" variant="outline" onClick={onRetry}>
            Reconnect
          </Button>
        ) : null}
      </div>
    );
  }

  return (
    <div
      className="border-b border-border bg-muted/40 px-4 py-1.5 text-xs text-muted-foreground"
      role="status"
      aria-live="polite"
    >
      {status === 'connecting' ? 'Connecting…' : 'Reconnecting…'}
    </div>
  );
}
