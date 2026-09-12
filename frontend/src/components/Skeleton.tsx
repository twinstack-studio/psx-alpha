/**
 * Route-level loading states.
 *
 * Every page is statically generated, so these are rarely on screen for long —
 * but they hold the layout while a route chunk arrives, which stops the shell
 * from collapsing and re-expanding around the ticker tape. Shapes mirror the
 * real page so nothing jumps when the content lands.
 *
 * There is deliberately no `app/loading.tsx`. A loading file at the root wraps
 * every child segment in the same Suspense boundary, and once Next starts
 * streaming a response its status code is already committed — which turned an
 * unknown ticker into a 200 carrying 404 content. Each route that needs a
 * skeleton declares its own; `/company/[ticker]` has none, so `notFound()`
 * there still answers with a real 404.
 */

export function SkeletonLine({ w = "100%", h = 12 }: { w?: string | number; h?: number }) {
  return <div className="skeleton" style={{ width: w, height: h }} />;
}

export function SkeletonCard({ h = 168 }: { h?: number }) {
  return (
    <div className="card p-5" style={{ height: h }}>
      <div className="flex flex-col gap-3">
        <SkeletonLine w="42%" h={10} />
        <SkeletonLine w="68%" h={26} />
        <SkeletonLine w="90%" h={10} />
        <SkeletonLine w="76%" h={10} />
      </div>
    </div>
  );
}

export function PageSkeleton({
  tiles = 4,
  chart = true,
  cards = 8,
}: {
  tiles?: number;
  chart?: boolean;
  cards?: number;
}) {
  return (
    <div className="flex animate-none flex-col gap-9" aria-busy aria-label="Loading">
      <div className="flex flex-col gap-4">
        <SkeletonLine w={220} h={22} />
        <SkeletonLine w="min(760px, 90%)" h={38} />
        <SkeletonLine w="min(560px, 80%)" h={14} />
      </div>

      {tiles > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: tiles }).map((_, i) => (
            <SkeletonCard key={i} h={148} />
          ))}
        </div>
      )}

      {chart && (
        <div className="card p-5">
          <SkeletonLine w="38%" h={14} />
          <div className="mt-4 skeleton" style={{ height: 320 }} />
        </div>
      )}

      {cards > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: cards }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      )}
    </div>
  );
}
