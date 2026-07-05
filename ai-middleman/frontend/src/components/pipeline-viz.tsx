import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card } from "@/components/ui-bits";
import { api, type PipelineEvent } from "@/lib/api";
import {
  Mail, Radio, Search, BrainCircuit, Link2, PenLine, Send, CheckCircle2,
} from "lucide-react";

const STAGE_NODES = [
  { key: "received", icon: Mail, label: "Message received" },
  { key: "relaying", icon: Radio, label: "Relaying to Alex" },
  { key: "checking", icon: Search, label: "Quick pattern check" },
  { key: "intent", icon: BrainCircuit, label: "AI: is this a request?" },
  { key: "matching", icon: Link2, label: "Matching contacts" },
  { key: "drafting", icon: PenLine, label: "Writing a draft" },
  { key: "awaiting_approval", icon: Send, label: "Waiting on Alex" },
  { key: "resolved", icon: CheckCircle2, label: "Resolved" },
] as const;

// One accent per stage, grouped into phases (relay → understand → match/draft
// → approve → done). Full literal class strings so Tailwind's scanner keeps
// them. The same accent drives the stepper nodes AND the feed's left border,
// so a log line's colour matches the stage it came from.
type Accent = { icon: string; ring: string; fill: string; glow: string; line: string; feed: string };
const STAGE_ACCENT: Record<string, Accent> = {
  received:          { icon: "text-sky-500",    ring: "border-sky-400",    fill: "bg-sky-400/15",    glow: "shadow-sky-400/50",    line: "bg-sky-400",    feed: "border-l-sky-400" },
  relaying:          { icon: "text-sky-500",    ring: "border-sky-400",    fill: "bg-sky-400/15",    glow: "shadow-sky-400/50",    line: "bg-sky-400",    feed: "border-l-sky-400" },
  checking:          { icon: "text-violet-500", ring: "border-violet-400", fill: "bg-violet-400/15", glow: "shadow-violet-400/50", line: "bg-violet-400", feed: "border-l-violet-400" },
  intent:            { icon: "text-violet-500", ring: "border-violet-400", fill: "bg-violet-400/15", glow: "shadow-violet-400/50", line: "bg-violet-400", feed: "border-l-violet-400" },
  matching:          { icon: "text-amber-500",  ring: "border-amber-400",  fill: "bg-amber-400/15",  glow: "shadow-amber-400/50",  line: "bg-amber-400",  feed: "border-l-amber-400" },
  drafting:          { icon: "text-amber-500",  ring: "border-amber-400",  fill: "bg-amber-400/15",  glow: "shadow-amber-400/50",  line: "bg-amber-400",  feed: "border-l-amber-400" },
  awaiting_approval: { icon: "text-primary",    ring: "border-primary",    fill: "bg-primary/15",    glow: "shadow-primary/50",    line: "bg-primary",    feed: "border-l-primary" },
  resolved:          { icon: "text-success",    ring: "border-success",    fill: "bg-success/15",    glow: "shadow-success/50",    line: "bg-success",    feed: "border-l-success" },
};
const FALLBACK: Accent = { icon: "text-muted-foreground", ring: "border-border", fill: "bg-muted/40", glow: "shadow-border", line: "bg-border", feed: "border-l-border" };
const accentFor = (key: string) => STAGE_ACCENT[key] ?? FALLBACK;

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function usePipelineFeed() {
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [active, setActive] = useState<Record<string, boolean>>({});
  // Stages that have fired in the CURRENT run — reset when a new message
  // arrives ("received"). Lets the stepper show completed stages as "done"
  // instead of reverting them to grey, so the flow through the pipeline is
  // visible at a glance rather than a single flashing node.
  const [reached, setReached] = useState<Record<string, boolean>>({});
  const sinceRef = useRef(0);
  const timers = useRef<Record<string, ReturnType<typeof setTimeout>>>({});

  const query = useQuery({
    queryKey: ["pipeline-events"],
    queryFn: () => api.pipelineEvents(sinceRef.current),
    refetchInterval: 800,
    retry: 2,
  });

  useEffect(() => {
    const batch = query.data?.events;
    if (!batch || batch.length === 0) return;
    sinceRef.current = query.data!.since;
    setEvents((prev) => {
      const seen = new Set(prev.map((e) => e.id));
      const fresh = batch.filter((e) => !seen.has(e.id));
      return fresh.length ? [...fresh, ...prev].slice(0, 80) : prev;
    });
    batch.forEach((e) => {
      if (e.stage === "received") setReached({}); // new message → fresh run
      setActive((a) => ({ ...a, [e.stage]: true }));
      setReached((r) => ({ ...r, [e.stage]: true }));
      clearTimeout(timers.current[e.stage]);
      timers.current[e.stage] = setTimeout(() => {
        setActive((a) => ({ ...a, [e.stage]: false }));
      }, 2200);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data]);

  return { events, active, reached, isError: query.isError, error: query.error as Error | null };
}

type StageState = "pending" | "active" | "done";
function stageState(key: string, active: Record<string, boolean>, reached: Record<string, boolean>): StageState {
  if (active[key]) return "active";
  if (reached[key]) return "done";
  return "pending";
}

/** Horizontal flow diagram — used on the full-page /pipeline view. */
export function PipelineFlow({ active, reached = {} }: { active: Record<string, boolean>; reached?: Record<string, boolean> }) {
  return (
    <Card className="p-6">
      <div className="flex flex-wrap items-stretch justify-center gap-1.5">
        {STAGE_NODES.map((s, i) => {
          const Icon = s.icon;
          const st = stageState(s.key, active, reached);
          const a = accentFor(s.key);
          const lit = st !== "pending";
          return (
            <div key={s.key} className="flex items-center gap-1.5">
              <div
                className={`relative flex flex-col items-center justify-center gap-2 w-[132px] p-4 rounded-2xl border-2 transition-all duration-500 ${
                  st === "active"
                    ? `${a.ring} ${a.fill} shadow-[0_0_26px_-4px] ${a.glow} scale-[1.04]`
                    : st === "done"
                    ? `${a.ring} ${a.fill}`
                    : "border-border/60 bg-muted/30"
                }`}
              >
                {st === "active" && (
                  <span className={`pointer-events-none absolute inset-0 rounded-2xl border-2 ${a.ring} animate-ping opacity-60`} />
                )}
                <Icon className={`w-6 h-6 transition-colors ${lit ? a.icon : "text-muted-foreground"}`} />
                <div className={`text-xs text-center leading-tight ${st === "active" ? "font-semibold text-foreground" : lit ? "text-foreground/80" : "text-muted-foreground"}`}>
                  {s.label}
                </div>
              </div>
              {i < STAGE_NODES.length - 1 && (
                <span className={`text-lg transition-colors duration-500 ${reached[s.key] ? a.icon : "text-border"}`}>→</span>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

/** Compact vertical stepper — used alongside the Inbox conversation. */
export function PipelineFlowCompact({ active, reached = {} }: { active: Record<string, boolean>; reached?: Record<string, boolean> }) {
  return (
    <div className="flex flex-col px-3 py-2">
      {STAGE_NODES.map((s, i) => {
        const Icon = s.icon;
        const st = stageState(s.key, active, reached);
        const a = accentFor(s.key);
        const lit = st !== "pending";
        const last = i === STAGE_NODES.length - 1;
        return (
          <div key={s.key} className="flex gap-3">
            {/* node + connector column */}
            <div className="flex flex-col items-center">
              <div
                className={`relative grid place-items-center w-8 h-8 rounded-full border-2 transition-all duration-500 ${
                  st === "active"
                    ? `${a.ring} ${a.fill} shadow-[0_0_16px_-3px] ${a.glow}`
                    : st === "done"
                    ? `${a.ring} ${a.fill}`
                    : "border-border bg-muted/40"
                }`}
              >
                {st === "active" && (
                  <span className={`pointer-events-none absolute inset-0 rounded-full border-2 ${a.ring} animate-ping opacity-60`} />
                )}
                <Icon className={`w-4 h-4 transition-colors ${lit ? a.icon : "text-muted-foreground"}`} />
              </div>
              {!last && (
                <div className={`w-0.5 flex-1 min-h-[14px] my-1 rounded-full transition-colors duration-500 ${reached[s.key] ? a.line : "bg-border"}`} />
              )}
            </div>
            {/* label */}
            <div className={`pt-1 ${last ? "" : "pb-2"}`}>
              <div className={`text-xs leading-tight ${st === "active" ? "font-semibold text-foreground" : lit ? "text-foreground/80" : "text-muted-foreground"}`}>
                {s.label}
              </div>
              {st === "active" && <div className={`text-[10px] font-medium ${a.icon}`}>running…</div>}
            </div>
          </div>
        );
      })}
    </div>
  );
}

export function PipelineFeed({ events, compact = false }: { events: PipelineEvent[]; compact?: boolean }) {
  if (events.length === 0) {
    return (
      <div className="text-sm text-muted-foreground py-6 text-center">
        Waiting for the next message — send one as Sam to kick off the pipeline.
      </div>
    );
  }
  return (
    <ul className={`space-y-1.5 overflow-y-auto ${compact ? "max-h-[220px]" : "max-h-[420px]"}`}>
      {events.map((e) => (
        <li
          key={e.id}
          className={`flex items-baseline gap-3 rounded-lg bg-muted/40 px-3 py-2 text-sm border-l-4 ${accentFor(e.stage).feed}`}
        >
          <span className="text-xs text-muted-foreground shrink-0 tabular-nums">{fmtTime(e.ts)}</span>
          <span className={compact ? "text-xs" : undefined}>{e.message}</span>
        </li>
      ))}
    </ul>
  );
}
