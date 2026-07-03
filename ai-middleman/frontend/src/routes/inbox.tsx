import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Card } from "@/components/ui-bits";
import { THREADS, AUDIT_LOG } from "@/lib/mock-data";
import { Check, Pencil, X, Search, Sparkles, History } from "lucide-react";

export const Route = createFileRoute("/inbox")({
  head: () => ({ meta: [{ title: "Inbox · AI Middleman" }] }),
  component: InboxPage,
});

function InboxPage() {
  const [selectedId, setSelectedId] = useState(THREADS[0].id);
  const [filter, setFilter] = useState<"all" | "pending" | "answered">("all");
  const [tab, setTab] = useState<"threads" | "audit">("threads");
  const selected = THREADS.find((t) => t.id === selectedId)!;

  const filtered = THREADS.filter((t) => filter === "all" || t.status === filter);

  return (
    <div className="h-[calc(100vh-3.5rem)] flex flex-col">
      <div className="px-6 pt-6 pb-3 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Inbox</h1>
          <p className="text-sm text-muted-foreground">Review AI-drafted replies before they go out on WhatsApp.</p>
        </div>
        <div className="flex items-center rounded-xl bg-muted p-0.5">
          <button onClick={() => setTab("threads")} className={`px-3 h-8 text-xs rounded-lg ${tab === "threads" ? "bg-surface shadow-soft" : "text-muted-foreground"}`}>Threads</button>
          <button onClick={() => setTab("audit")} className={`px-3 h-8 text-xs rounded-lg inline-flex items-center gap-1 ${tab === "audit" ? "bg-surface shadow-soft" : "text-muted-foreground"}`}><History className="w-3 h-3" />Audit</button>
        </div>
      </div>

      {tab === "audit" ? (
        <div className="px-6 pb-6">
          <Card className="p-5">
            <ul className="divide-y divide-border">
              {AUDIT_LOG.map((a, i) => (
                <li key={i} className="py-3 flex items-center gap-3 text-sm">
                  <div className="w-8 h-8 rounded-full bg-accent grid place-items-center text-xs font-semibold text-accent-foreground shrink-0">{a.who[0]}</div>
                  <div className="flex-1 min-w-0">
                    <div><span className="font-medium">{a.who}</span> <span className="text-muted-foreground">{a.action.toLowerCase()}</span> {a.subject}</div>
                    <div className="text-xs text-muted-foreground">{a.time}</div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      ) : (
        <div className="flex-1 min-h-0 px-6 pb-6 grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4">
          {/* Threads list */}
          <Card className="flex flex-col min-h-0 overflow-hidden">
            <div className="p-3 border-b border-border space-y-2">
              <div className="relative">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
                <input placeholder="Search threads" className="w-full h-9 pl-9 pr-3 rounded-xl bg-muted text-sm focus:outline-none" />
              </div>
              <div className="flex gap-1.5">
                {(["all", "pending", "answered"] as const).map((f) => (
                  <button
                    key={f}
                    onClick={() => setFilter(f)}
                    className={`px-2.5 h-7 rounded-full text-xs capitalize ${
                      filter === f ? "bg-primary-soft text-primary-soft-foreground" : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {f}
                  </button>
                ))}
              </div>
            </div>
            <ul className="flex-1 overflow-y-auto">
              {filtered.map((t) => (
                <li key={t.id}>
                  <button
                    onClick={() => setSelectedId(t.id)}
                    className={`w-full text-left p-3 border-b border-border/60 flex gap-3 hover:bg-muted/50 ${selectedId === t.id ? "bg-accent/60" : ""}`}
                  >
                    <div className="w-9 h-9 rounded-xl bg-primary-soft text-primary-soft-foreground grid place-items-center text-xs font-semibold shrink-0">
                      {t.contact.split(" ").map((n) => n[0]).slice(0, 2).join("")}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <div className="font-medium text-sm truncate flex-1">{t.contact}</div>
                        <div className="text-[11px] text-muted-foreground shrink-0">{t.time}</div>
                      </div>
                      <div className="text-xs text-muted-foreground truncate">{t.preview}</div>
                    </div>
                    {t.pending > 0 && <span className="w-5 h-5 shrink-0 rounded-full bg-primary-soft text-primary-soft-foreground text-[10px] font-semibold grid place-items-center">{t.pending}</span>}
                  </button>
                </li>
              ))}
            </ul>
          </Card>

          {/* Conversation */}
          <Card className="flex flex-col min-h-0 overflow-hidden">
            <div className="h-14 px-4 border-b border-border flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-primary-soft text-primary-soft-foreground grid place-items-center text-xs font-semibold">
                {selected.contact.split(" ").map((n) => n[0]).slice(0, 2).join("")}
              </div>
              <div className="min-w-0">
                <div className="font-medium text-sm truncate">{selected.contact}</div>
                <div className="text-xs text-muted-foreground">{selected.phone}</div>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-3 bg-surface-2/40">
              {selected.messages.map((m, i) => (
                <div key={i} className={`flex ${m.from === "us" ? "justify-end" : "justify-start"}`}>
                  <div className={`max-w-[70%] rounded-2xl px-3.5 py-2 text-sm ${m.from === "us" ? "bg-primary-soft text-primary-soft-foreground rounded-br-md" : "bg-surface rounded-bl-md shadow-soft"}`}>
                    {m.text}
                    <div className="text-[10px] opacity-60 mt-1 text-right">{m.time}</div>
                  </div>
                </div>
              ))}
            </div>

            {selected.suggested ? (
              <div className="p-4 border-t border-border">
                <div className="rounded-2xl border border-primary-soft bg-primary-soft/40 p-4">
                  <div className="flex items-center gap-2 text-xs font-medium text-primary-soft-foreground">
                    <Sparkles className="w-3.5 h-3.5" /> AI Suggested Reply
                    <span className="ml-auto rounded-full bg-surface px-2 py-0.5 text-[11px] tabular-nums">{selected.suggested.confidence}% confidence</span>
                  </div>
                  <div className="mt-3 text-xs text-muted-foreground">
                    Match: <span className="text-foreground font-medium">{selected.suggested.match}</span> · {selected.suggested.role} @ {selected.suggested.company}
                  </div>
                  <p className="mt-2 text-sm">{selected.suggested.reply}</p>
                  <div className="mt-3 flex gap-2">
                    <button className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg bg-success/20 text-success text-xs font-medium hover:bg-success/30"><Check className="w-3.5 h-3.5" />Approve</button>
                    <button className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg bg-muted text-foreground text-xs font-medium hover:bg-muted/80"><Pencil className="w-3.5 h-3.5" />Edit</button>
                    <button className="inline-flex items-center gap-1.5 h-8 px-3 rounded-lg bg-destructive/15 text-destructive text-xs font-medium hover:bg-destructive/25"><X className="w-3.5 h-3.5" />Reject</button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="p-8 border-t border-border text-center">
                <div className="mx-auto w-12 h-12 rounded-2xl bg-accent grid place-items-center mb-3">
                  <Sparkles className="w-5 h-5 text-accent-foreground" />
                </div>
                <div className="text-sm font-medium">No strong match found</div>
                <p className="text-xs text-muted-foreground mt-1 max-w-sm mx-auto">The AI couldn't confidently match this request. Try broadening the search criteria.</p>
                <button className="mt-3 inline-flex items-center gap-1.5 h-9 px-4 rounded-xl bg-primary-soft text-primary-soft-foreground text-sm font-medium">Broaden search</button>
              </div>
            )}
          </Card>
        </div>
      )}
    </div>
  );
}
