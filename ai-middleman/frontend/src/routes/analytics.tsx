import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { Card, SectionHeader } from "@/components/ui-bits";
import { SECTORS } from "@/lib/mock-data";
import { api } from "@/lib/api";
import {
  ScatterChart, Scatter, XAxis, YAxis, ZAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar, Cell, PieChart, Pie,
} from "recharts";
import { Users, Star, Gauge, Layers, MessageSquare, Sparkles, CheckCircle2, XCircle } from "lucide-react";

export const Route = createFileRoute("/analytics")({
  head: () => ({ meta: [{ title: "Analytics · AI Middleman" }] }),
  component: AnalyticsPage,
});

function sectorColor(name: string) {
  return SECTORS.find((s) => s.name === name)?.color ?? SECTORS[0].color;
}

const tooltipStyle = { background: "var(--color-popover)", border: "1px solid var(--color-border)", borderRadius: 12, fontSize: 12 } as const;
const axisTick = { fontSize: 11, fill: "var(--color-muted-foreground)" } as const;
const fmt = (n?: number) => (n ?? 0).toLocaleString();

function Kpi({ icon: Icon, label, value, hint }: { icon: typeof Users; label: string; value: string; hint?: string }) {
  return (
    <Card className="p-4 flex items-center gap-3">
      <div className="w-10 h-10 rounded-xl bg-primary-soft text-primary-soft-foreground grid place-items-center shrink-0">
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <div className="text-xl font-bold tabular-nums leading-tight">{value}</div>
        <div className="text-xs text-muted-foreground truncate">{label}</div>
      </div>
      {hint && <div className="ml-auto text-xs text-muted-foreground shrink-0">{hint}</div>}
    </Card>
  );
}

function RankedBars({ data, colorFor }: { data: { name: string; value: number }[]; colorFor?: (n: string) => string }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  return (
    <ul className="space-y-2.5">
      {data.map((d, i) => (
        <li key={d.name} className="flex items-center gap-3">
          <div className="w-5 text-xs text-muted-foreground tabular-nums">{i + 1}.</div>
          <div className="flex-1 min-w-0">
            <div className="flex justify-between text-sm">
              <span className="font-medium truncate">{d.name}</span>
              <span className="text-muted-foreground tabular-nums">{d.value}</span>
            </div>
            <div className="mt-1 h-1.5 rounded-full bg-muted overflow-hidden">
              <div className="h-full rounded-full" style={{ width: `${(d.value / max) * 100}%`, background: colorFor?.(d.name) ?? "var(--color-primary)" }} />
            </div>
          </div>
        </li>
      ))}
    </ul>
  );
}

function AnalyticsPage() {
  // Dynamic — from the live conversation log (thread_events)
  const convo = useQuery({ queryKey: ["analytics", "convo-summary"], queryFn: api.conversationSummary });
  const funnel = useQuery({ queryKey: ["analytics", "funnel"], queryFn: api.approvalFunnel });
  const reqSectors = useQuery({ queryKey: ["analytics", "req-sectors"], queryFn: api.requestedSectors });
  const reqServices = useQuery({ queryKey: ["analytics", "req-services"], queryFn: api.requestedServices });
  const topContacts = useQuery({ queryKey: ["analytics", "top-requested"], queryFn: api.topRequestedContacts });
  const reqLocations = useQuery({ queryKey: ["analytics", "req-locations"], queryFn: api.requestedLocations });
  const channelMix = useQuery({ queryKey: ["analytics", "channel-mix"], queryFn: api.channelMix });
  const calibration = useQuery({ queryKey: ["analytics", "calibration"], queryFn: api.confidenceCalibration });

  // Static — from the contacts table
  const summary = useQuery({ queryKey: ["analytics", "summary"], queryFn: api.analyticsSummary });
  const scatter = useQuery({ queryKey: ["analytics", "scatter"], queryFn: () => api.analyticsScatter(500) });
  const deals = useQuery({ queryKey: ["analytics", "deals"], queryFn: api.analyticsDealsBySector });
  const skills = useQuery({ queryKey: ["analytics", "top-skills"], queryFn: () => api.analyticsTopSkills(8) });
  const seniority = useQuery({ queryKey: ["analytics", "seniority"], queryFn: api.analyticsSeniority });
  const strength = useQuery({ queryKey: ["analytics", "strength"], queryFn: api.analyticsStrengthDistribution });
  const vip = useQuery({ queryKey: ["analytics", "vip"], queryFn: api.analyticsVipBreakdown });

  const sectorDeals = (deals.data ?? []).map((d) => ({ ...d, color: sectorColor(d.name) }));
  const maxSkill = Math.max(1, ...(skills.data ?? []).map((s) => s.count));
  const strengthData = (strength.data ?? []).map((b) => ({ name: `${b.level}★`, value: b.value }));
  const vipData = vip.data ?? [];
  const vipTotal = vipData.reduce((a, b) => a + b.value, 0);
  const vipPct = vipTotal ? Math.round(((vipData.find((v) => v.name === "VIP")?.value ?? 0) / vipTotal) * 100) : 0;
  const VIP_COLORS = ["var(--color-warning)", "var(--color-muted)"];
  const FUNNEL_COLORS: Record<string, string> = {
    Sent: "var(--color-success)", Edited: "var(--color-warning)", Skipped: "var(--color-destructive)", Pending: "var(--color-muted)",
  };
  const CHANNEL_COLORS: Record<string, string> = {
    Typed: "var(--color-primary)", "Voice note": "var(--color-warning)", Image: "oklch(0.68 0.14 200)",
  };
  const channelData = channelMix.data ?? [];
  const calibData = (calibration.data ?? []).map((b) => ({ name: b.bucket, rate: Math.round(b.send_rate * 100), n: b.resolved }));
  const funnelData = funnel.data ?? [];
  const c = convo.data;
  const s = summary.data;

  return (
    <div className="p-6 md:p-8 max-w-7xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight">Analytics</h1>
        <p className="text-muted-foreground mt-1 text-sm">What people ask for, how the AI responds, and what the network holds.</p>
      </div>

      {/* ───────── Conversation Insights (dynamic) ───────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-primary" />
          <h2 className="text-lg font-semibold">Conversation Insights</h2>
          <span className="text-xs text-muted-foreground">live — computed from every request &amp; decision</span>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Kpi icon={MessageSquare} label="Messages from Sam" value={fmt(c?.messages_from_sam)} />
          <Kpi icon={Sparkles} label="AI drafts generated" value={fmt(c?.drafts_generated)} />
          <Kpi icon={CheckCircle2} label="Approval rate" value={`${Math.round((c?.approval_rate ?? 0) * 100)}%`} hint="Sent ÷ resolved" />
          <Kpi icon={XCircle} label="Drafts skipped" value={fmt(c?.drafts_skipped)} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <SectionHeader title="What Alex Does With Drafts" subtitle="Send / Edit / Skip — the human-approval funnel" />
            <div className="flex items-center gap-4">
              <div className="w-40 h-40 shrink-0 relative">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={funnelData} innerRadius={48} outerRadius={72} paddingAngle={2} dataKey="value" stroke="none">
                      {funnelData.map((f) => <Cell key={f.name} fill={FUNNEL_COLORS[f.name] ?? "var(--color-muted)"} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v, "Drafts"]} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 grid place-items-center pointer-events-none">
                  <div className="text-center">
                    <div className="text-2xl font-bold leading-none">{Math.round((c?.approval_rate ?? 0) * 100)}%</div>
                    <div className="text-[10px] text-muted-foreground">sent</div>
                  </div>
                </div>
              </div>
              <ul className="flex-1 min-w-0 space-y-2 text-sm">
                {funnelData.map((f) => (
                  <li key={f.name} className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: FUNNEL_COLORS[f.name] }} />
                    <span className="flex-1 truncate">{f.name}</span>
                    <span className="text-muted-foreground tabular-nums">{f.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>

          <Card className="p-5">
            <SectionHeader title="Most-Requested Sectors" subtitle="Sector of every contact the AI has suggested" />
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={reqSectors.data ?? []} layout="vertical" margin={{ left: 10, right: 20, top: 4 }}>
                  <CartesianGrid horizontal={false} stroke="var(--color-border)" />
                  <XAxis type="number" tick={axisTick} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={130} tick={axisTick} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v, "Times suggested"]} />
                  <Bar dataKey="value" radius={[0, 6, 6, 0]}>
                    {(reqSectors.data ?? []).map((d) => <Cell key={d.name} fill={sectorColor(d.name)} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <SectionHeader title="Top Services Requested" subtitle="Specialties Sam's requests pull in most" />
            <RankedBars data={reqServices.data ?? []} />
          </Card>

          <Card className="p-5">
            <SectionHeader title="Most-Recommended People" subtitle="Contacts the AI surfaces most across conversations" />
            <ul className="space-y-2">
              {(topContacts.data ?? []).map((p, i) => (
                <li key={p.name + i} className="flex items-center gap-3 text-sm">
                  <div className="w-5 text-xs text-muted-foreground tabular-nums">{i + 1}.</div>
                  <div className="flex-1 min-w-0">
                    <div className="font-medium truncate">{p.name}</div>
                    <div className="text-xs text-muted-foreground truncate">{p.title} · {p.company}</div>
                  </div>
                  <div className="text-xs text-muted-foreground tabular-nums shrink-0">{p.value}×</div>
                </li>
              ))}
            </ul>
          </Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <SectionHeader title="Confidence Calibration" subtitle="Send rate by the ranker's confidence — rising = well-calibrated" />
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={calibData} margin={{ left: 0, right: 10, top: 10 }}>
                  <CartesianGrid stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="name" tick={axisTick} axisLine={false} tickLine={false} />
                  <YAxis domain={[0, 100]} unit="%" tick={axisTick} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v: number, _n, p) => [`${v}% sent (n=${p?.payload?.n ?? 0})`, "Send rate"]} />
                  <Bar dataKey="rate" fill="var(--color-primary)" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <p className="text-xs text-muted-foreground mt-2">Small sample — read the trend, not the exact bars.</p>
          </Card>

          <Card className="p-5">
            <SectionHeader title="Most-Requested Locations" subtitle="Where requests point — location of every suggested contact" />
            <div className="h-64">
              <ResponsiveContainer>
                <BarChart data={reqLocations.data ?? []} layout="vertical" margin={{ left: 10, right: 20, top: 4 }}>
                  <CartesianGrid horizontal={false} stroke="var(--color-border)" />
                  <XAxis type="number" tick={axisTick} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={120} tick={axisTick} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v, "Times suggested"]} />
                  <Bar dataKey="value" fill="var(--color-primary-soft)" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <SectionHeader title="How Requests Arrive" subtitle="Typed vs voice note vs image — the input channel mix" />
            <div className="flex items-center gap-4">
              <div className="w-40 h-40 shrink-0">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={channelData} innerRadius={44} outerRadius={72} paddingAngle={2} dataKey="value" stroke="none">
                      {channelData.map((ch) => <Cell key={ch.name} fill={CHANNEL_COLORS[ch.name] ?? "var(--color-muted)"} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v, "Messages"]} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <ul className="flex-1 min-w-0 space-y-2 text-sm">
                {channelData.map((ch) => (
                  <li key={ch.name} className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: CHANNEL_COLORS[ch.name] ?? "var(--color-muted)" }} />
                    <span className="flex-1 truncate">{ch.name}</span>
                    <span className="text-muted-foreground tabular-nums">{ch.value}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>
          <div />
        </div>
      </section>

      {/* ───────── Network Overview (static, from the contact DB) ───────── */}
      <section className="space-y-4">
        <div className="flex items-center gap-2">
          <Layers className="w-4 h-4 text-muted-foreground" />
          <h2 className="text-lg font-semibold">Network Overview</h2>
          <span className="text-xs text-muted-foreground">the 50,000-contact database Sam draws from</span>
        </div>

        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <Kpi icon={Users} label="Total contacts" value={fmt(s?.total_contacts)} />
          <Kpi icon={Star} label="VIP contacts" value={fmt(s?.vip_contacts)} hint={`${vipPct}%`} />
          <Kpi icon={Gauge} label="Avg. relationship" value={`${s?.avg_relationship_strength ?? 0}/5`} />
          <Kpi icon={Layers} label="Sectors covered" value={fmt(s?.sectors_covered)} />
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <SectionHeader title="Relationship Strength vs Intros Made" subtitle="Colored by sector" />
            <div className="h-72">
              <ResponsiveContainer>
                <ScatterChart margin={{ top: 10, right: 10, bottom: 10, left: 0 }}>
                  <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" />
                  <XAxis type="number" dataKey="x" name="Strength" domain={[0, 5]} tick={axisTick} axisLine={false} tickLine={false} />
                  <YAxis type="number" dataKey="y" name="Intros" tick={axisTick} axisLine={false} tickLine={false} />
                  <ZAxis range={[60, 60]} />
                  <Tooltip cursor={{ strokeDasharray: "3 3" }} contentStyle={tooltipStyle} />
                  {SECTORS.map((sec) => (
                    <Scatter key={sec.name} name={sec.name} data={(scatter.data ?? []).filter((d) => d.sector === sec.name)} fill={sec.color} />
                  ))}
                </ScatterChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {SECTORS.map((sec) => (
                <span key={sec.name} className="text-xs inline-flex items-center gap-1.5 text-muted-foreground">
                  <span className="w-2 h-2 rounded-full" style={{ background: sec.color }} /> {sec.name}
                </span>
              ))}
            </div>
          </Card>

          <Card className="p-5">
            <SectionHeader title="Average Deals Closed by Sector" />
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart data={sectorDeals} margin={{ left: 0, right: 10, top: 10 }}>
                  <CartesianGrid stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="name" tick={axisTick} axisLine={false} tickLine={false} />
                  <YAxis tick={axisTick} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                    {sectorDeals.map((sec) => <Cell key={sec.name} fill={sec.color} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <SectionHeader title="Contacts by Seniority" subtitle="How the network is distributed across levels" />
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart data={seniority.data ?? []} layout="vertical" margin={{ left: 10, right: 20, top: 4 }}>
                  <CartesianGrid horizontal={false} stroke="var(--color-border)" />
                  <XAxis type="number" tick={axisTick} axisLine={false} tickLine={false} />
                  <YAxis type="category" dataKey="name" width={70} tick={axisTick} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v.toLocaleString(), "Contacts"]} />
                  <Bar dataKey="value" fill="var(--color-primary)" radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <Card className="p-5">
            <SectionHeader title="Relationship Strength Distribution" subtitle="1★ = weak tie · 5★ = strong tie" />
            <div className="h-72">
              <ResponsiveContainer>
                <BarChart data={strengthData} margin={{ left: 0, right: 10, top: 10 }}>
                  <CartesianGrid stroke="var(--color-border)" vertical={false} />
                  <XAxis dataKey="name" tick={axisTick} axisLine={false} tickLine={false} />
                  <YAxis tick={axisTick} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v.toLocaleString(), "Contacts"]} />
                  <Bar dataKey="value" radius={[8, 8, 0, 0]}>
                    {strengthData.map((_, i) => (
                      <Cell key={i} fill={`color-mix(in oklab, var(--color-primary) ${40 + i * 15}%, var(--color-primary-soft))`} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="p-5">
            <SectionHeader title="VIP vs Standard" subtitle="Share of the network flagged VIP" />
            <div className="flex items-center gap-4">
              <div className="w-40 h-40 shrink-0 relative">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={vipData} innerRadius={48} outerRadius={72} paddingAngle={2} dataKey="value" stroke="none">
                      {vipData.map((_, i) => <Cell key={i} fill={VIP_COLORS[i % VIP_COLORS.length]} />)}
                    </Pie>
                    <Tooltip contentStyle={tooltipStyle} formatter={(v: number) => [v.toLocaleString(), "Contacts"]} />
                  </PieChart>
                </ResponsiveContainer>
                <div className="absolute inset-0 grid place-items-center pointer-events-none">
                  <div className="text-center">
                    <div className="text-2xl font-bold leading-none">{vipPct}%</div>
                    <div className="text-[10px] text-muted-foreground">VIP</div>
                  </div>
                </div>
              </div>
              <ul className="flex-1 min-w-0 space-y-2 text-sm">
                {vipData.map((v, i) => (
                  <li key={v.name} className="flex items-center gap-2">
                    <span className="w-2.5 h-2.5 rounded-full shrink-0" style={{ background: VIP_COLORS[i % VIP_COLORS.length] }} />
                    <span className="flex-1 truncate">{v.name}</span>
                    <span className="text-muted-foreground tabular-nums">{v.value.toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            </div>
          </Card>

          <Card className="p-5">
            <SectionHeader title="Top Specialties in Network" subtitle="Most common contact specialties across the database" />
            <ul className="space-y-2.5">
              {(skills.data ?? []).map((sk, i) => (
                <li key={sk.name} className="flex items-center gap-3">
                  <div className="w-6 text-xs text-muted-foreground tabular-nums">{i + 1}.</div>
                  <div className="flex-1 min-w-0">
                    <div className="flex justify-between text-sm">
                      <span className="font-medium truncate">{sk.name}</span>
                      <span className="text-muted-foreground tabular-nums">{sk.count}</span>
                    </div>
                    <div className="mt-1 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div className="h-full rounded-full bg-primary-soft" style={{ width: `${(sk.count / maxSkill) * 100}%` }} />
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </section>
    </div>
  );
}
