// activity.ts — shared helpers for rendering thread_events activity feeds.
// Used by both the Home "Today" feed and the Inbox "Audit" tab so the two
// stay consistent and there's a single place to update event copy/icons.
import { CheckCircle2, X, Sparkles, MessageSquareText, UserPlus } from "lucide-react";

export const ACTIVITY_ICONS: Record<string, typeof Sparkles> = {
  draft_suggested: MessageSquareText,
  friend_message: UserPlus,
  alex_reply: Sparkles,
  draft_sent: CheckCircle2,
  draft_skipped: X,
};

export function activityText(e: { event_type: string; payload: Record<string, any> }): string {
  switch (e.event_type) {
    case "friend_message":
      return `Sam asked: "${e.payload.text}"`;
    case "draft_suggested":
      return `AI drafted a reply — "${(e.payload.original_message ?? "").toString().slice(0, 60)}"`;
    case "draft_sent":
      return "Draft sent to the requester";
    case "draft_skipped":
      return "Draft skipped by Alex";
    case "alex_reply":
      return `Alex replied: "${e.payload.text}"`;
    default:
      return e.event_type;
  }
}

export function timeAgo(iso: string): string {
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}
