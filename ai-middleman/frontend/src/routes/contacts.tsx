import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, SectionHeader, Stars } from "@/components/ui-bits";
import { SECTORS, EXAMPLE_QUERIES } from "@/lib/mock-data";
import { api, type ContactRow, type ContactWrite, type MatchResult } from "@/lib/api";
import { Search, Filter, X, Star, Plus, Sparkles, Loader2, Pencil, Trash2, ArrowLeft } from "lucide-react";

export const Route = createFileRoute("/contacts")({
  head: () => ({ meta: [{ title: "Contacts · AI Middleman" }] }),
  component: ContactsPage,
});

function initials(name: string) {
  return name.split(" ").map((n) => n[0]).slice(0, 2).join("");
}

function emptyForm(): ContactWrite {
  return {
    full_name: "", phone: null, email: null, company: null, title: null,
    sector: null, specialty: null, location: null, seniority: null,
    expertise_tags: null, can_help_with: null, looking_for: null,
    relationship_strength: null, how_alex_knows_them: null, is_vip: false,
    preferred_contact_channel: null, comment: null,
  };
}

type PanelMode = "view" | "edit" | "create";
type MatchInfo = { confidence: number; reasoning: string } | null;

function ContactsPage() {
  const queryClient = useQueryClient();

  // Browse + filter state
  const [q, setQ] = useState("");
  const [sector, setSector] = useState<string | null>(null);
  const [location, setLocation] = useState<string | null>(null);
  const [seniority, setSeniority] = useState<string | null>(null);
  const [vipOnly, setVipOnly] = useState(false);
  const [showFilters, setShowFilters] = useState(true);
  const [page, setPage] = useState(1);
  const pageSize = 25;

  // AI matching (merged in from the old /matching page)
  const [showMatcher, setShowMatcher] = useState(false);
  const [matchQuery, setMatchQuery] = useState("VP Leveraged Finance in London, unitranche focus");
  const matchMutation = useMutation({ mutationFn: (query: string) => api.match(query) });
  const matchResult: MatchResult | undefined = matchMutation.data;

  // Slide-over: view / edit / create, plus AI-match context when opened from a match result
  const [panel, setPanel] = useState<{ mode: PanelMode; contactId: number | null } | null>(null);
  const [form, setForm] = useState<ContactWrite>(emptyForm());
  const [matchInfo, setMatchInfo] = useState<MatchInfo>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const filterOptions = useQuery({ queryKey: ["filters"], queryFn: api.filterOptions });
  const contactsQuery = useQuery({
    queryKey: ["contacts", { q, sector, location, seniority, vipOnly, page }],
    queryFn: () => api.contacts({ search: q || undefined, sector: sector ?? undefined, location: location ?? undefined, seniority: seniority ?? undefined, vip: vipOnly || undefined, page, pageSize }),
  });
  const detailQuery = useQuery({
    queryKey: ["contact", panel?.contactId],
    queryFn: () => api.contact(panel!.contactId!),
    enabled: !!panel?.contactId && panel.mode !== "create",
  });

  const invalidateContacts = () => {
    queryClient.invalidateQueries({ queryKey: ["contacts"] });
    queryClient.invalidateQueries({ queryKey: ["contact"] });
  };
  const createMutation = useMutation({
    mutationFn: (body: ContactWrite) => api.createContact(body),
    onSuccess: (created) => { invalidateContacts(); setPanel({ mode: "view", contactId: created.id }); setFormError(null); },
    onError: () => setFormError("Couldn't save this contact — check the required fields and try again."),
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, body }: { id: number; body: ContactWrite }) => api.updateContact(id, body),
    onSuccess: (updated) => { invalidateContacts(); setPanel({ mode: "view", contactId: updated.id }); setFormError(null); },
    onError: () => setFormError("Couldn't save changes — check the required fields and try again."),
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteContact(id),
    onSuccess: () => { invalidateContacts(); setPanel(null); },
  });

  const total = contactsQuery.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const filtered = contactsQuery.data?.items ?? [];

  function openView(id: number, info: MatchInfo = null) {
    setMatchInfo(info);
    setPanel({ mode: "view", contactId: id });
  }
  function openCreate() {
    setForm(emptyForm());
    setMatchInfo(null);
    setFormError(null);
    setPanel({ mode: "create", contactId: null });
  }
  function startEdit() {
    const c = detailQuery.data?.contact;
    if (!c) return;
    const { id: _id, ...rest } = c;
    setForm(rest);
    setFormError(null);
    setPanel((p) => (p ? { ...p, mode: "edit" } : p));
  }
  function closePanel() {
    setPanel(null);
    setMatchInfo(null);
    setFormError(null);
  }
  function saveForm() {
    if (!form.full_name.trim()) { setFormError("Name is required."); return; }
    if (panel?.mode === "create") createMutation.mutate(form);
    else if (panel?.mode === "edit" && panel.contactId) updateMutation.mutate({ id: panel.contactId, body: form });
  }

  const saving = createMutation.isPending || updateMutation.isPending;
  const c = detailQuery.data?.contact;

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Contacts</h1>
          <p className="text-muted-foreground mt-1 text-sm">Browse, enrich, and let AI find the right person in {total.toLocaleString()} contacts.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setShowMatcher((v) => !v)} className={`inline-flex items-center gap-2 h-9 px-3 rounded-xl text-sm ${showMatcher ? "bg-primary-soft text-primary-soft-foreground" : "bg-muted hover:bg-accent"}`}>
            <Sparkles className="w-4 h-4" /> AI Match
          </button>
          <button onClick={openCreate} className="inline-flex items-center gap-2 h-9 px-3 rounded-xl bg-primary-soft text-primary-soft-foreground text-sm font-medium hover:opacity-90">
            <Plus className="w-4 h-4" /> Add Contact
          </button>
          <button onClick={() => setShowFilters((v) => !v)} className="inline-flex items-center gap-2 h-9 px-3 rounded-xl bg-muted text-sm hover:bg-accent">
            <Filter className="w-4 h-4" /> Filters
          </button>
        </div>
      </div>

      {/* AI Contact Matching — merged in from the old standalone Matching page */}
      {showMatcher && (
        <Card className="p-5 mb-6">
          <SectionHeader title="AI Contact Matching" subtitle="Describe who you need and let AI find the best matches in the network below." />
          <div className="flex flex-wrap gap-2 mb-3">
            {EXAMPLE_QUERIES.map((eq) => (
              <button key={eq} onClick={() => setMatchQuery(eq)} className="text-xs px-3 h-7 rounded-full bg-muted text-muted-foreground hover:bg-accent hover:text-accent-foreground">
                {eq}
              </button>
            ))}
          </div>
          <textarea
            value={matchQuery}
            onChange={(e) => setMatchQuery(e.target.value)}
            rows={2}
            className="w-full rounded-xl bg-surface-2/40 border border-border p-3 text-sm resize-none focus:outline-none focus:border-ring"
          />
          <div className="mt-3 flex items-center justify-between">
            {matchMutation.isError && <span className="text-xs text-destructive">Couldn't reach the matching API.</span>}
            <button
              onClick={() => matchQuery.trim() && matchMutation.mutate(matchQuery)}
              disabled={matchMutation.isPending}
              className="ml-auto inline-flex items-center gap-2 h-9 px-4 rounded-xl bg-primary-soft text-primary-soft-foreground text-sm font-medium hover:opacity-90 disabled:opacity-60"
            >
              {matchMutation.isPending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
              {matchMutation.isPending ? "Searching…" : "Find Matches"}
            </button>
          </div>

          {matchResult && matchResult.matches.length === 0 && (
            <div className="mt-4 text-sm text-muted-foreground text-center py-4">
              {matchResult.clarification_question ?? "No strong match found — try broadening the search."}
            </div>
          )}
          {matchResult && matchResult.matches.length > 0 && (
            <ul className="mt-4 space-y-2">
              {matchResult.matches.map((r) => {
                const score = Math.round(r.confidence * 100);
                return (
                  <li key={r.contact_id}>
                    <button
                      onClick={() => openView(r.contact_id, { confidence: r.confidence, reasoning: r.reasoning })}
                      className="w-full flex items-center gap-3 p-3 rounded-xl bg-muted/40 hover:bg-accent text-left transition"
                    >
                      <div className="w-9 h-9 rounded-lg bg-primary-soft text-primary-soft-foreground grid place-items-center text-xs font-semibold shrink-0">{initials(r.name)}</div>
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm truncate">{r.name}</div>
                        <div className="text-xs text-muted-foreground truncate">{r.role}</div>
                      </div>
                      <span className={`rounded-full px-2.5 py-1 text-xs font-semibold tabular-nums shrink-0 ${score >= 85 ? "bg-success/20 text-success" : score >= 70 ? "bg-warning/20 text-warning" : "bg-muted text-muted-foreground"}`}>
                        {score}%
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      )}

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
                  <label key={s} className="flex items-center gap-2 cursor-pointer">
                    <input
                      type="checkbox"
                      className="accent-current"
                      checked={seniority === s}
                      onChange={() => { setSeniority(seniority === s ? null : s); setPage(1); }}
                    /> {s}
                  </label>
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
                ) : filtered.map((row: ContactRow) => {
                  const s = SECTORS.find((x) => x.name === row.sector);
                  return (
                    <tr key={row.id} onClick={() => openView(row.id)} className="border-t border-border/60 hover:bg-muted/50 cursor-pointer">
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 rounded-lg bg-primary-soft text-primary-soft-foreground grid place-items-center text-xs font-semibold shrink-0">{initials(row.full_name)}</div>
                          <span className="font-medium">{row.full_name}</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-muted-foreground">{row.title}</td>
                      <td className="px-4 py-2.5">{row.company}</td>
                      <td className="px-4 py-2.5"><span className="inline-flex items-center gap-1.5 text-xs"><span className="w-2 h-2 rounded-full" style={{ background: s?.color }} />{row.sector}</span></td>
                      <td className="px-4 py-2.5 text-muted-foreground">{row.location}</td>
                      <td className="px-4 py-2.5 text-muted-foreground">{row.seniority}</td>
                      <td className="px-4 py-2.5"><Stars n={row.relationship_strength ?? 0} /></td>
                      <td className="px-4 py-2.5">{row.is_vip && <Star className="w-4 h-4 text-warning fill-current" />}</td>
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

      {/* Slide-over: view / edit / create */}
      {panel && (
        <div className="fixed inset-0 z-50 flex">
          <div className="flex-1 bg-foreground/20" onClick={closePanel} />
          <div className="w-full max-w-md bg-surface border-l border-border overflow-y-auto">
            {panel.mode === "create" || panel.mode === "edit" ? (
              <ContactFormPanel
                form={form}
                setForm={setForm}
                title={panel.mode === "create" ? "Add Contact" : "Edit Contact"}
                error={formError}
                saving={saving}
                onCancel={panel.mode === "create" ? closePanel : () => setPanel((p) => (p ? { ...p, mode: "view" } : p))}
                onSave={saveForm}
              />
            ) : (
              <>
                <div className="p-5 border-b border-border flex items-start justify-between gap-3">
                  <div className="flex gap-3 min-w-0">
                    <div className="w-14 h-14 rounded-2xl bg-primary-soft text-primary-soft-foreground grid place-items-center text-lg font-semibold shrink-0">
                      {c ? initials(c.full_name) : "…"}
                    </div>
                    <div className="min-w-0">
                      <div className="font-semibold truncate">{c?.full_name ?? "Loading…"}</div>
                      <div className="text-xs text-muted-foreground truncate">{c?.title}</div>
                      <div className="text-xs text-muted-foreground truncate">{c?.company} · {c?.location}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={startEdit} title="Edit" className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground"><Pencil className="w-4 h-4" /></button>
                    <button
                      onClick={() => c && confirm(`Remove ${c.full_name} from the network?`) && deleteMutation.mutate(c.id)}
                      title="Delete"
                      className="p-1.5 rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                    <button onClick={closePanel} className="p-1.5 rounded-lg hover:bg-muted"><X className="w-4 h-4" /></button>
                  </div>
                </div>
                <div className="p-5 space-y-4">
                  {matchInfo && (
                    <div className="rounded-xl border border-primary-soft bg-primary-soft/30 p-3">
                      <div className="flex items-center gap-1.5 text-xs font-semibold text-primary-soft-foreground">
                        <Sparkles className="w-3.5 h-3.5" /> AI match — {Math.round(matchInfo.confidence * 100)}% confidence
                      </div>
                      <p className="text-xs mt-1 text-foreground/80">{matchInfo.reasoning}</p>
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-3">
                    <Field label="Sector" value={c?.sector} />
                    <Field label="Seniority" value={c?.seniority} />
                    <Field label="Strength" value={<Stars n={c?.relationship_strength ?? 0} />} />
                    <Field label="VIP" value={c?.is_vip ? "Yes" : "No"} />
                    {c?.phone && <Field label="Phone" value={c.phone} />}
                    {c?.email && <Field label="Email" value={c.email} />}
                  </div>
                  {c?.comment && <Field label="Notes" value={c.comment} />}
                  <div>
                    <div className="text-xs font-medium text-muted-foreground mb-2">Recent matches</div>
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
              </>
            )}
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

function ContactFormPanel({
  form, setForm, title, error, saving, onCancel, onSave,
}: {
  form: ContactWrite;
  setForm: (f: ContactWrite) => void;
  title: string;
  error: string | null;
  saving: boolean;
  onCancel: () => void;
  onSave: () => void;
}) {
  const set = <K extends keyof ContactWrite>(key: K, value: ContactWrite[K]) => setForm({ ...form, [key]: value });
  const input = "w-full h-9 px-3 rounded-xl bg-muted text-sm focus:outline-none focus:ring-2 focus:ring-ring";
  const label = "text-xs font-medium text-muted-foreground mb-1 block";

  return (
    <>
      <div className="p-5 border-b border-border flex items-center gap-3">
        <button onClick={onCancel} className="p-1.5 rounded-lg hover:bg-muted text-muted-foreground"><ArrowLeft className="w-4 h-4" /></button>
        <div className="font-semibold">{title}</div>
      </div>
      <div className="p-5 space-y-3">
        {error && <div className="text-xs text-destructive rounded-lg bg-destructive/10 px-3 py-2">{error}</div>}
        <div>
          <label className={label}>Full name *</label>
          <input className={input} value={form.full_name} onChange={(e) => set("full_name", e.target.value)} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className={label}>Title</label><input className={input} value={form.title ?? ""} onChange={(e) => set("title", e.target.value || null)} /></div>
          <div><label className={label}>Company</label><input className={input} value={form.company ?? ""} onChange={(e) => set("company", e.target.value || null)} /></div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className={label}>Sector</label><input className={input} value={form.sector ?? ""} onChange={(e) => set("sector", e.target.value || null)} /></div>
          <div><label className={label}>Specialty</label><input className={input} value={form.specialty ?? ""} onChange={(e) => set("specialty", e.target.value || null)} /></div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className={label}>Location</label><input className={input} value={form.location ?? ""} onChange={(e) => set("location", e.target.value || null)} /></div>
          <div><label className={label}>Seniority</label><input className={input} value={form.seniority ?? ""} onChange={(e) => set("seniority", e.target.value || null)} /></div>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className={label}>Phone</label><input className={input} value={form.phone ?? ""} onChange={(e) => set("phone", e.target.value || null)} /></div>
          <div><label className={label}>Email</label><input className={input} value={form.email ?? ""} onChange={(e) => set("email", e.target.value || null)} /></div>
        </div>
        <div>
          <label className={label}>Relationship strength (1–5)</label>
          <input type="number" min={1} max={5} className={input} value={form.relationship_strength ?? ""} onChange={(e) => set("relationship_strength", e.target.value ? Number(e.target.value) : null)} />
        </div>
        <div>
          <label className={label}>Expertise / tags</label>
          <input className={input} value={form.expertise_tags ?? ""} onChange={(e) => set("expertise_tags", e.target.value || null)} />
        </div>
        <div>
          <label className={label}>Can help with</label>
          <textarea rows={2} className={`${input} h-auto py-2 resize-none`} value={form.can_help_with ?? ""} onChange={(e) => set("can_help_with", e.target.value || null)} />
        </div>
        <div>
          <label className={label}>How Alex knows them</label>
          <textarea rows={2} className={`${input} h-auto py-2 resize-none`} value={form.how_alex_knows_them ?? ""} onChange={(e) => set("how_alex_knows_them", e.target.value || null)} />
        </div>
        <div>
          <label className={label}>Notes</label>
          <textarea rows={2} className={`${input} h-auto py-2 resize-none`} value={form.comment ?? ""} onChange={(e) => set("comment", e.target.value || null)} />
        </div>
        <label className="flex items-center justify-between text-sm py-1">
          <span>VIP</span>
          <input type="checkbox" checked={form.is_vip} onChange={(e) => set("is_vip", e.target.checked)} />
        </label>
        <div className="flex gap-2 pt-2">
          <button onClick={onCancel} className="flex-1 h-10 rounded-xl bg-muted text-sm font-medium hover:bg-accent">Cancel</button>
          <button onClick={onSave} disabled={saving} className="flex-1 h-10 rounded-xl bg-primary-soft text-primary-soft-foreground text-sm font-medium hover:opacity-90 disabled:opacity-60">
            {saving ? "Saving…" : "Save"}
          </button>
        </div>
      </div>
    </>
  );
}
