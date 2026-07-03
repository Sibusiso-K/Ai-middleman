import type { ReactNode } from "react";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-2xl bg-card text-card-foreground border border-border/60 shadow-soft ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex items-end justify-between gap-4 mb-4">
      <div className="min-w-0">
        <h2 className="text-base font-semibold truncate">{title}</h2>
        {subtitle && <p className="text-sm text-muted-foreground mt-0.5">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

const AVATAR_HUES = [10, 45, 90, 160, 210, 260, 300, 340];
export function initialsBg(name: string) {
  let h = 0;
  for (let i = 0; i < name.length; i++) h = (h + name.charCodeAt(i)) % AVATAR_HUES.length;
  const hue = AVATAR_HUES[h];
  return {
    background: `oklch(0.92 0.05 ${hue})`,
    color: `oklch(0.4 0.14 ${hue})`,
  };
}

export function Avatar({ name, initials, size = 36 }: { name: string; initials: string; size?: number }) {
  return (
    <div
      className="rounded-xl grid place-items-center font-semibold text-sm shrink-0"
      style={{ width: size, height: size, ...initialsBg(name) }}
    >
      {initials}
    </div>
  );
}

export function Stars({ n }: { n: number }) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: 5 }).map((_, i) => (
        <span key={i} className={i < n ? "text-warning" : "text-muted-foreground/30"}>★</span>
      ))}
    </div>
  );
}
