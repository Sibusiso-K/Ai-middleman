import { createFileRoute } from "@tanstack/react-router";
import { Card, SectionHeader } from "@/components/ui-bits";
import { SCATTER_DATA, SECTORS, TOP_SKILLS } from "@/lib/mock-data";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell,
} from "recharts";

export const Route = createFileRoute("/analytics")({
  head: () => ({ meta: [{ title: "Analytics · AI Middleman" }] }),
  component: AnalyticsPage,
});

const SECTOR_DEALS = SECTORS.map((s, i) => ({
  name: s.name,
  color: s.color,
  value: 6 + ((i * 13) % 18),
}));

const maxSkill = Math.max(...TOP_SKILLS.map((s) => s.count));

function AnalyticsPage() {
  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Analytics</h1>
        <p className="text-muted-foreground mt-1 text-sm">What the network is doing, and what people are asking for.</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="p-5">
          <SectionHeader title="Relationship Strength vs Intros Made" subtitle="Colored by sector" />
          <div className="h-72">
            <ResponsiveContainer>
              <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                <XAxis type="number" dataKey="x" name="Strength" domain={[0, 5]} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
                <YAxis type="number" dataKey="y" name="Intros" tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
                <ZAxis range={[60, 60]} />
                <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12, fontSize: 12 }} />
                {SECTORS.map((s) => (
                  <Scatter key={s.name} name={s.name} data={SCATTER_DATA.filter((d) => d.sector === s.name)} fill={s.color} />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {SECTORS.map((s) => (
              <span key={s.name} className="text-xs inline-flex items-center gap-1.5 text-muted-foreground">
                <span className="w-2 h-2 rounded-full" style={{ background: s.color }} /> {s.name}
              </span>
            ))}
          </div>
        </Card>

        <Card className="p-5">
          <SectionHeader title="Average Deals Closed by Sector" />
          <div className="h-72">
            <ResponsiveContainer>
              <BarChart data={SECTOR_DEALS} margin={{ left: 0, right: 10, top: 10 }}>
                <CartesianGrid stroke="var(--color-border)" vertical={false} />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12, fontSize: 12 }} />
                <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                  {SECTOR_DEALS.map((s) => <Cell key={s.name} fill={s.color} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      <Card className="p-5">
        <SectionHeader title="Top Requested Skills & Sectors" subtitle="What the WhatsApp bot is actually being asked for" />
        <ul className="space-y-2.5">
          {TOP_SKILLS.map((s, i) => (
            <li key={s.name} className="flex items-center gap-3">
              <div className="w-6 text-xs text-muted-foreground tabular-nums">{i + 1}.</div>
              <div className="flex-1 min-w-0">
                <div className="flex justify-between text-sm">
                  <span className="font-medium truncate">{s.name}</span>
                  <span className="text-muted-foreground tabular-nums">{s.count}</span>
                </div>
                <div className="mt-1 h-1.5 rounded-full bg-muted overflow-hidden">
                  <div className="h-full rounded-full bg-primary-soft" style={{ width: `${(s.count / maxSkill) * 100}%` }} />
                </div>
              </div>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
