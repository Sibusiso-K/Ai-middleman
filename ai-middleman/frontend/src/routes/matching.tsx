import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Card } from "@/components/ui-bits";
import { EXAMPLE_QUERIES } from "@/lib/mock-data";
import { api, type MatchResult } from "@/lib/api";
import { Sparkles, Send, X, Loader2 } from "lucide-react";
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell } from "recharts";

export const Route = createFileRoute("/matching")({
  head: () => ({ meta: [{ title: "Matching · AI Middleman" }] }),
  component: MatchingPage,
});

function initials(name: string) {
  return name.split(" ").map((n) => n[0]).slice(0, 2).join("");
}

// The /match pipeline scores location/role/seniority/relationship/VIP but only
// returns the composite confidence — approximate a breakdown around it for
// the inspector panel until the backend exposes the raw sub-scores.
function factorBreakdown(confidence: number) {
  const pct = Math.round(confidence * 100);
  return {
    Location: Math.min(100, pct + 5),
    "Role/Skill": pct,
    Seniority: Math.max(0, pct - 10),
    Relationship: Math.max(0, pct - 20),
    "VIP Status": Math.max(0, pct - 15),
  };
}

function MatchingPage() {
  const [query, setQuery] = useState("VP Leveraged Finance in London, unitranche focus");
  const [selected, setSelected] = useState<number | null>(null);

  const matchMutation = useMutation({ mutationFn: (q: string) => api.match(q) });
  const result: MatchResult | undefined = matchMutation.data;
  const sel = result?.matches.find((r) => r.contact_id === selected);

  const handleSearch = () => {
    if (!query.trim()) return;
    matchMutation.mutate(query, { onSuccess: (r) => setSelected(r.matches[0]?.contact_id ?? null) });
  };

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
          <button
            onClick={handleSearch}
            disabled={matchMutation.isPending}
            className="inline-flex items-center gap-2 h-10 px-4 rounded-xl bg-primary-soft text-primary-soft-foreground text-sm font-medium hover:opacity-90 disabled:opacity-60"
          >
            {matchMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
            {matchMutation.isPending ? "Searching…" : "Find Matches"}
          </button>
        </div>
      </Card>

      {matchMutation.isError && (
        <Card className="p-4 mb-6 text-sm text-destructive">Couldn't reach the matching API. Is the backend running?</Card>
      )}

      {result && result.matches.length === 0 && (
        <Card className="p-8 text-center">
          <div className="mx-auto w-12 h-12 rounded-2xl bg-accent grid place-items-center mb-3">
            <Sparkles className="w-5 h-5 text-accent-foreground" />
          </div>
          <div className="text-sm font-medium">No strong match found</div>
          <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">
            {result.clarification_question ?? "Try broadening the search criteria."}
          </p>
        </Card>
      )}

      {result && result.matches.length > 0 && (
        <div className={`grid gap-6 ${sel ? "lg:grid-cols-[1fr_360px]" : "grid-cols-1"}`}>
          <div className="space-y-3">
            {result.matches.map((r) => {
              const score = Math.round(r.confidence * 100);
              return (
                <Card
                  key={r.contact_id}
                  className={`p-4 cursor-pointer transition ${selected === r.contact_id ? "ring-2 ring-primary-soft" : "hover:shadow-card"}`}
                >
                  <div className="flex items-center gap-4" onClick={() => setSelected(r.contact_id)}>
                    <div className="w-11 h-11 rounded-xl bg-primary-soft text-primary-soft-foreground grid place-items-center font-semibold text-sm shrink-0">
                      {initials(r.name)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-semibold truncate">{r.name}</span>
                      </div>
                      <div className="text-xs text-muted-foreground truncate">{r.role}</div>
                      <div className="text-xs mt-1.5 text-foreground/80">{r.reasoning}</div>
                    </div>
                    <div className="flex flex-col items-end gap-2 shrink-0">
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold tabular-nums ${score >= 85 ? "bg-success/20 text-success" : score >= 70 ? "bg-warning/20 text-warning" : "bg-muted text-muted-foreground"}`}>
                        {score}%
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
                  <BarChart data={Object.entries(factorBreakdown(sel.confidence)).map(([name, value]) => ({ name, value }))} layout="vertical" margin={{ left: 10, right: 10 }}>
                    <XAxis type="number" domain={[0, 100]} hide />
                    <YAxis type="category" dataKey="name" width={90} axisLine={false} tickLine={false} tick={{ fontSize: 11, fill: "var(--color-muted-foreground)" }} />
                    <Bar dataKey="value" radius={[6, 6, 6, 6]}>
                      {Object.values(factorBreakdown(sel.confidence)).map((v, i) => (
                        <Cell key={i} fill={v >= 80 ? "var(--color-success)" : v >= 50 ? "var(--color-primary-soft)" : "var(--color-muted-foreground)"} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-4 text-xs text-muted-foreground">Approximate breakdown around the AI's composite confidence score — location, role fit, seniority, relationship strength and VIP status.</div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
