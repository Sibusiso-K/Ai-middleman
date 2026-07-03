import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, Stars } from "@/components/ui-bits";
import { SECTORS } from "@/lib/mock-data";
import { api, type ContactRow } from "@/lib/api";
import { Search, Filter, X, Star } from "lucide-react";

export const Route = createFileRoute("/contacts")({
  head: () => ({ meta: [{ title: "Contacts · AI Middleman" }] }),
  component: ContactsPage,
});

function initials(name: string) {
  return name.split(" ").map((n) => n[0]).slice(0, 2).join("");
}

function ContactsPage() {
  const [q, setQ] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const [location, setLocation] = useState<string | null>(null);
  const [vipOnly, setVipOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<ContactRow | null>(null);
  const pageSize = 25;

  const filterOptions = useQuery({ queryKey: ["filters"], queryFn: api.filterOptions });
  const contactsQuery = useQuery({
    queryKey: ["contacts", { q, sector, location, vipOnly, page }],
    queryFn: () => api.contacts({ search: q || undefined, sector: sector ?? undefined, location: location ?? undefined, vip: vipOnly || undefined, page, pageSize }),
  });
  const detailQuery = useQuery({
    queryKey: ["contact", selected?.id],
    queryFn: () => api.contact(selected!.id),
    enabled: !!selected,
  });

  const total = contactsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const filtered = contactsQuery.data?.items ?? [];

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto">
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Contacts</h1>
          <p className="text-muted-foreground mt-1 text-sm">Browse and enrich {total.toLocaleString()} professional contacts.</p>
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
                {(filterOptions.data?.sectors ?? []).map((name) => {
                  const color = SECTORS.find((s) => s.name === name)?.color ?? SECTORS[0].color;
                  return (
                    <button
                      key={name}
                      onClick={() => { setSector(sector === name ? null : name); setPage(1); }}
                      className={`text-xs px-2.5 h-7 rounded-full border ${sector === name ? "border-transparent" : "border-border bg-muted"}`}
                      style={sector === name ? { background: `color-mix(in oklab, ${color} 25%, transparent)`, color } : {}}
                    >
                      {name}
                    </button>
                  );
                })}
              </div>
            </div>
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-2">Location</div>
              <select value={location ?? ""} onChange={(e) => { setLocation(e.target.value || null); setPage(1); }} className="w-full h-9 px-3 rounded-xl bg-muted text-sm focus:outline-none">
                <option value="">Any location</option>
                {(filterOptions.data?.locations ?? []).map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div>
              <div className="text-xs font-medium text-muted-foreground mb-2">Seniority</div>
              <div className="space-y-1.5 text-sm">
                {(filterOptions.data?.seniorities ?? []).map((s) => (
                  <label key={s} className="flex items-center gap-2"><input type="checkbox" className="accent-current" /> {s}</label>
                ))}
              </div>
            </div>
            <label className="flex items-center justify-between text-sm">
              <span>VIP only</span>
              <input type="checkbox" checked={vipOnly} onChange={(e) => { setVipOnly(e.target.checked); setPage(1); }} />
            </label>
          </Card>
        )}

        <Card className="overflow-hidden">
          <div className="p-3 border-b border-border">
            <div className="relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
              <input value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} placeholder="Search by name, company, title…" className="w-full h-9 pl-9 rounded-xl bg-muted text-sm focus:outline-none" />
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
                {contactsQuery.isLoading ? (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">Loading contacts…</td></tr>
                ) : filtered.length === 0 ? (
                  <tr><td colSpan={8} className="px-4 py-8 text-center text-muted-foreground">No contacts match these filters.</td></tr>
                ) : filtered.map((c) => {
                  const s = SECTORS.find((x) => x.name === c.sector);
                  return (
                    <tr key={c.id} onClick={() => setSelected(c)} className="border-t border-border/60 hover:bg-muted/50 cursor-pointer">
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-primary-soft text-primary-soft-foreground grid place-items-center text-xs font-semibold shrink-0">{initials(c.full_name)}</div>
                          <span className="font-medium">{c.full_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{c.title}</td>
                      <td className="px-4 py-2.5">{c.company}</td>
                      <td className="px-4 py-2.5"><span className="inline-flex items-center gap-1.5 text-xs"><span className="w-2 h-2 rounded-full" style={{ background: s?.color }} />{c.sector}</span></td>
                      <td className="px-4 py-2.5 text-muted-foreground">{c.location}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{c.seniority}</td>
                      <td className="px-4 py-2.5"><Stars n={c.relationship_strength ?? 0} /></td>
                      <td className="px-4 py-2.5">{c.is_vip && <Star className="w-4 h-4 text-warning fill-current" />}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className="p-3 border-t border-border flex items-center justify-between text-xs text-muted-foreground">
            <span>Showing {filtered.length ? (page - 1) * pageSize + 1 : 0}–{(page - 1) * pageSize + filtered.length} of {total.toLocaleString()}</span>
            <div className="flex items-center gap-1">
              <button disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))} className="h-7 px-2.5 rounded-lg bg-muted disabled:opacity-40">Prev</button>
              <span className="px-2 tabular-nums">{page} / {totalPages}</span>
              <button disabled={page >= totalPages} onClick={() => setPage((p) => Math.min(totalPages, p + 1))} className="h-7 px-2.5 rounded-lg bg-muted disabled:opacity-40">Next</button>
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
                <div className="w-14 h-14 rounded-2xl bg-primary-soft text-primary-soft-foreground grid place-items-center text-lg font-semibold shrink-0">{initials(selected.full_name)}</div>
                <div className="min-w-0">
                  <div className="font-semibold truncate">{selected.full_name}</div>
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
                <Field label="Strength" value={<Stars n={selected.relationship_strength ?? 0} />} />
                <Field label="VIP" value={selected.is_vip ? "Yes" : "No"} />
              </div>
              <div>
                <div className="text-xs font-medium text-muted-foreground mb-2">Matched in {selected.intros_made ?? 0} requests</div>
                {detailQuery.isLoading ? (
                  <div className="text-sm text-muted-foreground">Loading history…</div>
                ) : !detailQuery.data?.recent_matches.length ? (
                  <div className="text-sm text-muted-foreground">No recorded matches yet.</div>
                ) : (
                  <ul className="space-y-2 text-sm">
                    {detailQuery.data.recent_matches.map((m, i) => (
                      <li key={i} className="rounded-xl bg-muted/60 p-3">
                        <div className="text-xs text-muted-foreground">{new Date(m.created_at).toLocaleDateString()} · {Math.round(m.confidence * 100)}% confidence</div>
                        <div>{m.reasoning || m.message_text}</div>
                      </li>
                    ))}
                  </ul>
                )}
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
