import { Link, useRouterState } from "@tanstack/react-router";
import { useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Home, Inbox, Sparkles, Users, BarChart3, ChevronsLeft, ChevronsRight, Handshake,
} from "lucide-react";
import { useTheme, type Theme } from "@/lib/theme";
import { api } from "@/lib/api";

const NAV = [
  { to: "/", label: "Home", icon: Home, exact: true },
  { to: "/inbox", label: "Inbox", icon: Inbox },
  { to: "/matching", label: "Matching", icon: Sparkles },
  { to: "/contacts", label: "Contacts", icon: Users },
  { to: "/analytics", label: "Analytics", icon: BarChart3 },
];

const THEMES: { id: Theme; label: string }[] = [
  { id: "daylight", label: "Daylight" },
  { id: "midnight", label: "Midnight" },
  { id: "slate", label: "Slate" },
  { id: "warm", label: "Warm" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false);
  const { theme, setTheme } = useTheme();
  const path = useRouterState({ select: (s) => s.location.pathname });
  const threadQuery = useQuery({ queryKey: ["friend-thread"], queryFn: api.friendThread, refetchInterval: 10000 });
  const events = threadQuery.data?.events ?? [];
  const lastDraftAt = [...events].reverse().find((e) => e.event_type === "draft_suggested")?.created_at;
  const pendingCount = lastDraftAt && !events.some((e) => e.created_at > lastDraftAt && ["draft_sent", "draft_skipped"].includes(e.event_type)) ? 1 : 0;
  const healthQuery = useQuery({ queryKey: ["health"], queryFn: api.health, refetchInterval: 15000, retry: false });
  const isOnline = healthQuery.data?.status === "ok";

  return (
    <div className="min-h-screen w-full flex bg-background text-foreground">
      {/* Sidebar (desktop) */}
      <aside
        className={`hidden md:flex flex-col shrink-0 bg-sidebar border-r border-sidebar-border transition-[width] duration-200 ${
          collapsed ? "w-16" : "w-60"
        }`}
      >
        <div className="h-14 flex items-center gap-2 px-4 border-b border-sidebar-border">
          <div className="w-8 h-8 rounded-xl bg-primary-soft grid place-items-center text-primary-soft-foreground shrink-0">
            <Handshake className="w-4 h-4" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="text-sm font-semibold truncate">AI Middleman</div>
              <div className="text-[11px] text-muted-foreground truncate">Relationship Intelligence</div>
            </div>
          )}
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {NAV.map((item) => {
            const active = item.exact ? path === item.to : path.startsWith(item.to);
            const Icon = item.icon;
            const badge = item.to === "/inbox" && pendingCount > 0;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`group flex items-center gap-3 rounded-xl px-3 h-10 text-sm transition-colors relative ${
                  active
                    ? "bg-sidebar-accent text-sidebar-accent-foreground font-medium"
                    : "text-sidebar-foreground hover:bg-sidebar-accent/60"
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                {!collapsed && <span className="truncate">{item.label}</span>}
                {badge && (
                  <span className={`ml-auto text-[10px] font-semibold rounded-full bg-primary-soft text-primary-soft-foreground ${collapsed ? "absolute top-1 right-1 w-4 h-4 grid place-items-center" : "px-1.5 py-0.5"}`}>
                    {pendingCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
        <button
          onClick={() => setCollapsed((v) => !v)}
          className="m-2 h-9 rounded-xl flex items-center justify-center gap-2 text-xs text-muted-foreground hover:bg-sidebar-accent/60"
        >
          {collapsed ? <ChevronsRight className="w-4 h-4" /> : (<><ChevronsLeft className="w-4 h-4" /><span>Collapse</span></>)}
        </button>
      </aside>

      {/* Main */}
      <div className="flex-1 min-w-0 flex flex-col pb-16 md:pb-0">
        {/* Top bar */}
        <header className="h-14 shrink-0 flex items-center gap-3 px-4 md:px-6 border-b border-border bg-surface/60 backdrop-blur">
          <div className="flex-1" />
          <div className="hidden lg:flex items-center gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><span className={`w-2 h-2 rounded-full ${isOnline ? "bg-success" : "bg-destructive"}`} />API {isOnline ? "Online" : "Offline"}</span>
            <span className="flex items-center gap-1.5"><span className={`w-2 h-2 rounded-full ${isOnline ? "bg-success" : "bg-destructive"}`} />Database {isOnline ? "Online" : "Offline"}</span>
          </div>
          <div className="hidden sm:flex items-center rounded-xl bg-muted p-0.5">
            {THEMES.map((t) => (
              <button
                key={t.id}
                onClick={() => setTheme(t.id)}
                className={`px-2.5 h-7 text-xs rounded-lg transition-colors ${
                  theme === t.id ? "bg-surface text-foreground shadow-soft" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </header>

        <main className="flex-1 min-w-0 overflow-x-hidden">{children}</main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 inset-x-0 h-16 bg-sidebar border-t border-sidebar-border flex items-center justify-around px-2 z-40">
        {NAV.map((item) => {
          const active = item.exact ? path === item.to : path.startsWith(item.to);
          const Icon = item.icon;
          return (
            <Link key={item.to} to={item.to} className={`flex flex-col items-center gap-0.5 text-[10px] px-2 py-1 rounded-lg ${active ? "text-primary-soft-foreground" : "text-muted-foreground"}`}>
              <Icon className="w-5 h-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </div>
  );
}
