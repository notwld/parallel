import { Skeleton } from '@/components/ui/skeleton';

/** Layout-matched placeholders; shapes mirror loaded UI to avoid CLS. */

export function PageHeaderSkeleton() {
  return (
    <div className="flex items-center justify-between gap-4 py-6" aria-hidden>
      <Skeleton className="h-7 w-40" />
      <Skeleton className="h-8 w-24" />
    </div>
  );
}

export function FormSkeleton({ fields = 3 }: { fields?: number }) {
  return (
    <div className="mx-auto max-w-sm space-y-4 py-10" aria-hidden>
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-4 w-full max-w-xs" />
      {Array.from({ length: fields }).map((_, i) => (
        <div key={i} className="space-y-2">
          <Skeleton className="h-3 w-20" />
          <Skeleton className="h-9 w-full" />
        </div>
      ))}
      <Skeleton className="h-9 w-full" />
    </div>
  );
}

export function ListSkeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div className="space-y-3" aria-hidden>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex items-center gap-3">
          <Skeleton className="size-9 shrink-0 rounded-full" />
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-4 w-[66%] max-w-[16rem]" />
            <Skeleton className="h-3 w-full max-w-sm" />
          </div>
        </div>
      ))}
    </div>
  );
}

export function MessagePaneSkeleton() {
  return (
    <div className="flex h-[min(70vh,32rem)] flex-col gap-3 p-4" aria-hidden>
      <Skeleton className="h-5 w-40" />
      <div className="flex-1 space-y-3 overflow-hidden">
        {Array.from({ length: 8 }).map((_, i) => (
          <div key={i} className={`flex ${i % 3 === 0 ? 'justify-end' : 'justify-start'}`}>
            <Skeleton className={`h-12 ${i % 2 === 0 ? 'w-[40%]' : 'w-[50%]'} max-w-md rounded-2xl`} />
          </div>
        ))}
      </div>
      <Skeleton className="h-10 w-full" />
    </div>
  );
}

export function ClaimCardSkeleton() {
  return (
    <div className="space-y-3 border-b border-border py-4" aria-hidden>
      <Skeleton className="h-4 w-full max-w-xl" />
      <Skeleton className="h-4 w-[80%] max-w-lg" />
      <div className="flex gap-2">
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-5 w-20" />
      </div>
    </div>
  );
}

export function ClaimListSkeleton({ rows = 5 }: { rows?: number }) {
  return (
    <div>
      {Array.from({ length: rows }).map((_, i) => (
        <ClaimCardSkeleton key={i} />
      ))}
    </div>
  );
}
