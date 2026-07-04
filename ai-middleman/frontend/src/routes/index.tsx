import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { Card, SectionHeader } from "@/components/ui-bits";
import { SECTORS } from "@/lib/mock-data";
import { api } from "@/lib/api";
import { ACTIVITY_ICONS, activityText, timeAgo } from "@/lib/activity";
import { CheckCircle2, Circle, X, Sparkles, ArrowUpRight } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [{ title: "Home · AI Middleman" }] }),
  component: HomePage,
});

const CHECKLIST = [
  { label: "Connect OpenAI API key", done: true },
  { label: "Configure WhatsApp webhook", done: true },
  { label: "Import contact database", done: true },
];

function sectorColor(name: string) {
  return SECTORS.find((s) => s.name === name)?.color ?? SECTORS[0].color;
}

function HomePage() {
  const [showOnboarding, setShowOnboarding] = useState(true);

  const sectors = useQuery({ queryKey: ["analytics", "sectors"], queryFn: api.analyticsSectors });
  const locations = useQuery({ queryKey: ["analytics", "locations"], queryFn: () => api.analyticsLocations(10) });
  const activity = useQuery({ queryKey: ["activity"], queryFn: () => api.activity(6) });

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">AI Middleman — Contact Intelligence Platform</h1>
        <p className="text-muted-foreground mt-1">Automating business connections through intelligent AI matching.</p>
      </div>

      {showOnboarding && (
        <Card className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <h3 className="font-semibold">You're all set</h3>
              <p className="text-sm text-muted-foreground mt-0.5">AI Middleman is wired to your WhatsApp workspace and ready to go.</p>
              <ul className="mt-4 space-y-2">
                {CHECKLIST.map((c) => (
                  <li key={c.label} className="flex items-center gap-2 text-sm">
                    {c.done ? <CheckCircle2 className="w-4 h-4 text-success" /> : <Circle className="w-4 h-4 text-muted-foreground" />}
                    <span className={c.done ? "text-muted-foreground line-through" : ""}>{c.label}</span>
                  </li>
                ))}
              </ul>
            </div>
            <button onClick={() => setShowOnboarding(false)} className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground">
              <X className="w-4 h-4" />
            </button>
          </div>
        </Card>
      )}

      <Card className="p-5">
        <SectionHeader title="Today" subtitle="Live activity across the middleman pipeline" />
        {activity.isLoading ? (
          <div className="py-6 text-sm text-muted-foreground">Loading activity…</div>
        ) : !activity.data?.length ? (
          <div className="py-6 text-sm text-muted-foreground">No activity yet — send a request from the Inbox to get started.</div>
        ) : (
          <ul className="divide-y divide-border">
            {activity.data.map((a, i) => {
              const Icon = ACTIVITY_ICONS[a.event_type] ?? Sparkles;
              return (
                <li key={i} className="py-3 flex items-center gap-3">
                  <div className="w-8 h-8 rounded-xl bg-accent grid place-items-center shrink-0">
                    <Icon className="w-4 h-4 text-accent-foreground" />
                  </div>
                  <div className="flex-1 min-w-0 text-sm truncate">{activityText(a)}</div>
                  <div className="text-xs text-muted-foreground shrink-0">{timeAgo(a.created_at)}</div>
                </li>
              );
            })}
          </ul>
        )}
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-5">
          <SectionHeader title="Contacts by Sector" />
          <div className="flex items-center gap-4">
            <div className="w-40 h-40 shrink-0">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={sectors.data ?? []} innerRadius={44} outerRadius={72} paddingAngle={2} dataKey="value" stroke="none">
                    {(sectors.data ?? []).map((s) => <Cell key={s.name} fill={sectorColor(s.name)} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="flex-1 min-w-0 space-y-1.5 text-sm">
              {(sectors.data ?? []).map((s) => (
                <li key={s.name} className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: sectorColor(s.name) }} />
                  <span className="flex-1 truncate">{s.name}</span>
                  <span className="text-muted-foreground tabular-nums">{s.value.toLocaleString()}</span>
                </li>
              ))}
            </ul>
          </div>
        </Card>

        <Card className="p-5">
          <SectionHeader title="Top 10 Locations" action={<a className="text-xs text-muted-foreground inline-flex items-center gap-1">All <ArrowUpRight className="w-3 h-3" /></a>} />
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={locations.data ?? []} layout="vertical" margin={{ left: 10, right: 20 }}>
                <CartesianGrid horizontal={false} stroke="var(--color-border)" />
                <XAxis type="number" hide />
                <YAxis type="category" dataKey="name" width={80} axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: "var(--color-muted-foreground)" }} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12, fontSize: 12 }} />
                <Bar dataKey="value" fill={SECTORS[0].color} radius={[6, 6, 6, 6]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>
    </div>
  );
}
