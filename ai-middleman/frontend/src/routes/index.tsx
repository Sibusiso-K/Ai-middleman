import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import {
  PieChart, Pie, Cell, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid,
} from "recharts";
import { Card, SectionHeader } from "@/components/ui-bits";
import { ACTIVITY, SECTOR_STATS, LOCATION_STATS, SECTORS } from "@/lib/mock-data";
import { CheckCircle2, Circle, X, Sparkles, MessageSquareText, UserPlus, ArrowUpRight } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({ meta: [{ title: "Home · AI Middleman" }] }),
  component: HomePage,
});

const KPIS = [
  { label: "Total Contacts", value: "50,284", delta: "+412 this week" },
  { label: "VIP Contacts", value: "1,847", delta: "+23 flagged" },
  { label: "Avg Relationship Strength", value: "3.8", delta: "of 5.0" },
  { label: "Sectors Covered", value: "7", delta: "Global" },
];

const CHECKLIST = [
  { label: "Connect OpenAI API key", done: true },
  { label: "Configure WhatsApp webhook", done: true },
  { label: "Import contact database", done: false },
  { label: "Invite reviewers to Inbox", done: false },
];

const ICONS = { match: Sparkles, draft: MessageSquareText, sent: CheckCircle2, contact: UserPlus } as const;

function HomePage() {
  const [showOnboarding, setShowOnboarding] = useState(true);

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
              <h3 className="font-semibold">Finish setting up</h3>
              <p className="text-sm text-muted-foreground mt-0.5">A few things left before AI Middleman is fully wired to your WhatsApp workspace.</p>
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

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {KPIS.map((k) => (
          <Card key={k.label} className="p-5">
            <div className="text-xs text-muted-foreground">{k.label}</div>
            <div className="text-3xl font-semibold tabular-nums mt-2">{k.value}</div>
            <div className="text-xs text-muted-foreground mt-1">{k.delta}</div>
          </Card>
        ))}
      </div>

      <Card className="p-5">
        <SectionHeader title="Today" subtitle="Live activity across the middleman pipeline" />
        <ul className="divide-y divide-border">
          {ACTIVITY.map((a, i) => {
            const Icon = ICONS[a.icon as keyof typeof ICONS];
            return (
              <li key={i} className="py-3 flex items-center gap-3">
                <div className="w-8 h-8 rounded-xl bg-accent grid place-items-center shrink-0">
                  <Icon className="w-4 h-4 text-accent-foreground" />
                </div>
                <div className="flex-1 min-w-0 text-sm truncate">{a.text}</div>
                <div className="text-xs text-muted-foreground shrink-0">{a.time}</div>
              </li>
            );
          })}
        </ul>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card className="p-5">
          <SectionHeader title="Contacts by Sector" />
          <div className="flex items-center gap-4">
            <div className="w-40 h-40 shrink-0">
              <ResponsiveContainer>
                <PieChart>
                  <Pie data={SECTOR_STATS} innerRadius={44} outerRadius={72} paddingAngle={2} dataKey="value" stroke="none">
                    {SECTOR_STATS.map((s) => <Cell key={s.name} fill={s.color} />)}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
            <ul className="flex-1 min-w-0 space-y-1.5 text-sm">
              {SECTOR_STATS.map((s) => (
                <li key={s.name} className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: s.color }} />
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
              <BarChart data={LOCATION_STATS} layout="vertical" margin={{ left: 10, right: 20 }}>
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
