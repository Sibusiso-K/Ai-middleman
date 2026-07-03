import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, SectionHeader } from "@/components/ui-bits";
import { api, type PipelineEvent } from "@/lib/api";
import {
  Mail, Radio, Search, BrainCircuit, Link2, PenLine, Send, CheckCircle2,
} from "lucide-react";

export const Route = createFileRoute("/pipeline")({
  head: () => ({ meta: [{ title: "Pipeline · AI Middleman" }] }),
  component: PipelinePage,
});

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

const STAGE_BORDER: Record<string, string> = {
  received: "border-l-sky-400", relaying: "border-l-sky-400",
  checking: "border-l-violet-400", intent: "border-l-violet-400",
  matching: "border-l-amber-400", drafting: "border-l-amber-400",
  awaiting_approval: "border-l-yellow-400", resolved: "border-l-success",
};

function fmtTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function PipelinePage() {
  const [events, setEvents] = useState<PipelineEvent[]>([]);
  const [active, setActive] = useState<Record<string, boolean>>({});
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
    setEvents((prev) => [...batch, ...prev].slice(0, 80));
    batch.forEach((e) => {
      setActive((a) => ({ ...a, [e.stage]: true }));
      clearTimeout(timers.current[e.stage]);
      timers.current[e.stage] = setTimeout(() => {
        setActive((a) => ({ ...a, [e.stage]: false }));
      }, 2200);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query.data]);

  return (
    <div className="px-6 py-6 space-y-6">
      <SectionHeader
        title="Live Pipeline"
        subtitle="What the server is doing right now, translated from the terminal into plain English."
      />

      {query.isError && (
        <div className="text-sm text-destructive">
          Could not reach the API ({(query.error as Error)?.message ?? "unknown error"}).
        </div>
      )}

      <Card className="p-6">
        <div className="flex flex-wrap items-stretch justify-center gap-2">
          {STAGE_NODES.map((s, i) => {
            const Icon = s.icon;
            const isActive = !!active[s.key];
            return (
              <div key={s.key} className="flex items-center gap-2">
                <div
                  className={`flex flex-col items-center justify-center gap-2 w-[140px] p-4 rounded-2xl border-2 transition-all duration-300 ${
                    isActive
                      ? "border-success bg-success/10 shadow-[0_0_22px_-2px] shadow-success/40 scale-105"
                      : "border-border/60 bg-muted/30"
                  }`}
                >
                  <Icon className={`w-6 h-6 ${isActive ? "text-success" : "text-muted-foreground"}`} />
                  <div className={`text-xs text-center leading-tight ${isActive ? "font-semibold" : "text-muted-foreground"}`}>
                    {s.label}
                  </div>
                </div>
                {i < STAGE_NODES.length - 1 && (
                  <span className={`text-lg transition-colors ${isActive ? "text-success" : "text-border"}`}>→</span>
                )}
              </div>
            );
          })}
        </div>
      </Card>

      <Card className="p-5">
        <div className="text-sm font-semibold mb-3">Activity feed</div>
        {events.length === 0 ? (
          <div className="text-sm text-muted-foreground py-6 text-center">
            Waiting for the next message — send one as Sam in the Inbox to kick off the pipeline.
          </div>
        ) : (
          <ul className="space-y-1.5 max-h-[420px] overflow-y-auto">
            {events.map((e) => (
              <li
                key={e.id}
                className={`flex items-baseline gap-3 rounded-lg bg-muted/40 px-3 py-2 text-sm border-l-4 ${STAGE_BORDER[e.stage] ?? "border-l-border"}`}
              >
                <span className="text-xs text-muted-foreground shrink-0">{fmtTime(e.ts)}</span>
                <span>{e.message}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
