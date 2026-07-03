import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState } from "react";
import { Card, Stars } from "@/components/ui-bits";
import { CONTACTS, SECTORS, LOCATIONS, type Contact } from "@/lib/mock-data";
import { Search, Filter, X, Star } from "lucide-react";

export const Route = createFileRoute("/contacts")({
  head: () => ({ meta: [{ title: "Contacts · AI Middleman" }] }),
  component: ContactsPage,
});

function ContactsPage() {
  const [q, setQ] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const [location, setLocation] = useState<string | null>(null);
  const [vipOnly, setVipOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [selected, setSelected] = useState<Contact | null>(null);

  const filtered = useMemo(
    () =>
      CONTACTS.filter(
        (c) =>
          (!q || (c.name + c.company + c.title).toLowerCase().includes(q.toLowerCase())) &&
          (!sector || c.sector === sector) &&
          (!location || c.location === location) &&
          (!vipOnly || c.vip),
      ),
    [q, sector, location, vipOnly],
  );

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Contacts</h1>
          <p className="text-muted-foreground mt-1 text-sm">Browse and enrich 50,284 professional contacts.</p>
        </div>
        <button onClick={() => setShowFilters((v) => !v)} className="inline-flex items-center gap-2 h-9 px-3 rounded-xl bg-muted text-sm hover:bg-accent">
          <Filter className="w-4 h-4" /> Filters
        </button>
      </div>

      <div className={`grid gap-6 ${showFilters ? "md:grid-cols-[240px_1fr]" : "grid-cols-1"}`}>
        {showFilters && (
          <Card className="p-4 h-fit space-y-4">
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-2">Sector</div>
              <div className="flex flex-wrap gap-1.5">
                {SECTORS.map((s) => (
                  <button
                    key={s.name}
                    onClick={() => setSector(sector === s.name ? null : s.name)}
                    className={`text-xs px-2.5 h-7 rounded-full border ${sector === s.name ? "border-transparent" : "border-border bg-muted"}`}
                    style={sector === s.name ? { background: `color-mix(in oklab, ${s.color} 25%, transparent)`, color: s.color } : {}}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-2">Location</div>
              <select value={location ?? ""} onChange={(e) => setLocation(e.target.value || null)} className="w-full h-9 px-3 rounded-xl bg-muted text-sm focus:outline-none">
                <option value="">Any location</option>
                {LOCATIONS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-2">Seniority</div>
              <div className="space-y-1.5 text-sm">
                {["Junior", "Mid", "Senior", "Executive"].map((s) => (
                  <label key={s} className="flex items-center gap-2"><input type="checkbox" className="accent-current" /> {s}</label>
                ))}
              </div>
            </div>
            <label className="flex items-center justify-between text-sm">
              <span>VIP only</span>
              <input type="checkbox" checked={vipOnly} onChange={(e) => setVipOnly(e.target.checked)} />
            </label>
          </Card>
        )}

        <Card className="overflow-hidden">
          <div className="p-3 border-b border-border">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by name, company, title…" className="w-full h-9 pl-9 rounded-xl bg-muted text-sm focus:outline-none" />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-surface-2/40 sticky top-0">
                <tr className="text-xs text-muted-foreground">
                  {["Name", "Title", "Company", "Sector", "Location", "Seniority", "Strength", "VIP"].map((h) => (
                    <th key={h} className="text-left font-medium px-4 py-2.5">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((c) => {
                  const s = SECTORS.find((x) => x.name === c.sector);
                  return (
                    <tr key={c.id} onClick={() => setSelected(c)} className="border-t border-border/60 hover:bg-muted/50 cursor-pointer">
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-primary-soft text-primary-soft-foreground grid place-items-center text-xs font-semibold shrink-0">{c.initials}</div>
                          <span className="font-medium">{c.name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{c.title}</td>
                      <td className="px-4 py-2.5">{c.company}</td>
                      <td className="px-4 py-2.5"><span className="inline-flex items-center gap-1.5 text-xs"><span className="w-2 h-2 rounded-full" style={{ background: s?.color }} />{c.sector}</span></td>
                      <td className="px-4 py-2.5 text-muted-foreground">{c.location}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{c.seniority}</td>
                      <td className="px-4 py-2.5"><Stars n={c.strength} /></td>
                      <td className="px-4 py-2.5">{c.vip && <Star className="w-4 h-4 text-warning fill-current" />}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="p-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
            <span>Showing {filtered.length} of 50,284</span>
            <div className="flex items-center gap-1">
              <button className="h-7 px-2.5 rounded-lg bg-muted">Prev</button>
              <button className="h-7 px-2.5 rounded-lg bg-primary-soft text-primary-soft-foreground">1</button>
              <button className="h-7 px-2.5 rounded-lg bg-muted">2</button>
              <button className="h-7 px-2.5 rounded-lg bg-muted">3</button>
              <button className="h-7 px-2.5 rounded-lg bg-muted">Next</button>
            </div>
          </div>
        </Card>
      </div>

      {/* Slide-over */}
      {selected && (
        <div className="fixed inset-0 z-50 flex">
          <div className="flex-1 bg-foreground/20" onClick={() => setSelected(null)} />
          <div className="w-full max-w-md bg-surface border-l border-border overflow-y-auto">
            <div className="p-5 border-b border-border flex items-start justify-between gap-3">
              <div className="flex gap-3 min-w-0">
                <div className="w-14 h-14 rounded-2xl bg-primary-soft text-primary-soft-foreground grid place-items-center text-lg font-semibold shrink-0">{selected.initials}</div>
                <div className="min-w-0">
                  <div className="font-semibold truncate">{selected.name}</div>
                  <div className="text-xs text-muted-foreground truncate">{selected.title}</div>
                  <div className="text-xs text-muted-foreground truncate">{selected.company} · {selected.location}</div>
                </div>
              </div>
              <button onClick={() => setSelected(null)} className="p-1.5 rounded-lg hover:bg-muted"><X className="w-4 h-4" /></button>
            </div>
            <div className="p-5 space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <Field label="Sector" value={selected.sector} />
                <Field label="Seniority" value={selected.seniority} />
                <Field label="Strength" value={<Stars n={selected.strength} />} />
                <Field label="VIP" value={selected.vip ? "Yes" : "No"} />
              </div>
              <div>
                <div className="text-xs font-medium text-muted-foreground mb-2">Matched in {selected.matchedIn} requests</div>
                <ul className="space-y-2 text-sm">
                  {Array.from({ length: Math.min(3, selected.matchedIn) }).map((_, i) => (
                    <li key={i} className="rounded-xl bg-muted/60 p-3">
                      <div className="text-xs text-muted-foreground">{["2d ago", "1w ago", "3w ago"][i]}</div>
                      <div>Suggested for a {selected.sector.toLowerCase()} intro in {selected.location}.</div>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-xl bg-muted/60 p-3">
      <div className="text-[11px] text-muted-foreground">{label}</div>
      <div className="text-sm mt-0.5">{value}</div>
    </div>
  );
}
