import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Card } from "@/components/ui-bits";
import { CONTACTS, EXAMPLE_QUERIES, SECTORS } from "@/lib/mock-data";
import { Sparkles, Send, X } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";

export const Route = createFileRoute("/matching")({
  head: () => ({ meta: [{ title: "Matching · AI Middleman" }] }),
  component: MatchingPage,
});

const results = CONTACTS.slice(0, 6).map((c, i) => ({
  ...c,
  score: 96 - i * 6,
  reason: [
    "Deep unitranche book — closed 8 deals in London in 2024.",
    "Ran cross-border M&A desk at previous firm.",
    "Direct match on seniority + specialism.",
    "Warm relationship via 3 mutual introductions.",
    "Sector adjacent — worth a broader check.",
    "Location match but weaker specialism overlap.",
  ][i],
  factors: {
    Location: 60 + (i % 3) * 15,
    "Role/Skill": 90 - i * 8,
    Seniority: 70 + ((i * 5) % 25),
    Relationship: 40 + (i * 10) % 60,
    "VIP Status": i === 0 ? 100 : (i * 20) % 80,
  },
}));

function MatchingPage() {
  const [query, setQuery] = useState("VP Leveraged Finance in London, unitranche focus");
  const [selected, setSelected] = useState<string | null>(results[0].id);
  const sel = results.find((r) => r.id === selected);

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">AI Contact Matching</h1>
        <p className="text-muted-foreground mt-1">Describe who you need and let AI find the best matches in seconds.</p>
      </div>

      <Card className="p-5 mb-6">
        <div className="flex flex-wrap gap-2 mb-3">
          {EXAMPLE_QUERIES.map((q) => (
            <button key={q} onClick={() => setQuery(q)} className="text-xs px-3 h-7 rounded-full bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground">
              {q}
            </button>
          ))}
        </div>
        <textarea
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          rows={3}
          className="w-full rounded-xl bg-surface-2/40 border border-border p-4 text-sm resize-none focus:outline-none focus:border-ring"
        />
        <div className="mt-3 flex justify-end">
          <button className="inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-primary-soft text-primary-soft-foreground text-sm font-medium hover:opacity-90">
            <Sparkles className="w-4 h-4" /> Find Matches
          </button>
        </div>
      </Card>

      <div className={`grid gap-6 ${sel ? "lg:grid-cols-[1fr_360px]" : "grid-cols-1"}`}>
        <div className="space-y-3">
          {results.map((r) => {
            const sector = SECTORS.find((s) => s.name === r.sector);
            return (
              <Card
                key={r.id}
                className={`p-4 cursor-pointer transition ${selected === r.id ? "ring-2 ring-primary-soft" : "hover:shadow-card"}`}
              >
                <div className="flex items-center gap-4" onClick={() => setSelected(r.id)}>
                  <div className="w-11 h-11 rounded-xl bg-primary-soft text-primary-soft-foreground grid place-items-center font-semibold text-sm shrink-0">
                    {r.initials}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold truncate">{r.name}</span>
                      <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: `color-mix(in oklab, ${sector?.color} 20%, transparent)`, color: sector?.color }}>{r.sector}</span>
                    </div>
                    <div className="text-xs text-muted-foreground truncate">{r.title} · {r.company} · {r.location}</div>
                    <div className="text-xs mt-1.5 text-foreground/80">{r.reason}</div>
                  </div>
                  <div className="flex flex-col items-end gap-2 shrink-0">
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold tabular-nums ${r.score >= 85 ? "bg-success/20 text-success" : r.score >= 70 ? "bg-warning/20 text-warning" : "bg-muted text-muted-foreground"}`}>
                      {r.score}%
                    </span>
                    <button className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg bg-muted hover:bg-accent hover:text-accent-foreground text-xs font-medium">
                      <Send className="w-3 h-3" /> Send to Sam
                    </button>
                  </div>
                </div>
              </Card>
            );
          })}
        </div>

        {sel && (
          <Card className="p-5 h-fit lg:sticky lg:top-6">
            <div className="flex items-center justify-between gap-2">
              <h3 className="font-semibold">Match breakdown</h3>
              <button onClick={() => setSelected(null)} className="p-1 rounded-lg hover:bg-muted text-muted-foreground"><X className="w-4 h-4" /></button>
            </div>
            <div className="mt-1 text-sm text-muted-foreground">{sel.name}</div>
            <div className="mt-4 h-48">
              <ResponsiveContainer>
                <BarChart data={Object.entries(sel.factors).map(([name, value]) => ({ name, value }))} layout="vertical" margin={{ left: 10, right: 10 }}>
                  <XAxis type="number" domain={[0, 100]} hide />
                  <YAxis type="category" dataKey="name" width={90} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} />
                  <Bar dataKey="value" radius={[6, 6, 6, 6]}>
                    {Object.values(sel.factors).map((v, i) => (
                      <Cell key={i} fill={v >= 80 ? "var(--color-success)" : v >= 50 ? SECTORS[0].color : "var(--color-muted-foreground)"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-4 text-xs text-muted-foreground">Composite score is a weighted blend of role fit, seniority, geography, relationship strength and VIP flag.</div>
          </Card>
        )}
      </div>
    </div>
  );
}
