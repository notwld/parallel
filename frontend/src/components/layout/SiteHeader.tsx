import { Link } from '@tanstack/react-router';

export function SiteHeader() {
  return (
    <header className="flex items-center justify-between gap-6 border-b border-border py-8">
      <Link to="/" className="text-xl font-extrabold tracking-[0.15em] text-foreground no-underline">
        PARALLEL<span className="text-primary"> / </span>
      </Link>
      <p className="text-sm text-muted-foreground">Development foundation</p>
    </header>
  );
}
