import { createFileRoute } from "@tanstack/react-router";
import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Card, SectionHeader } from "@/components/ui-bits";
import { api, type ThreadEvent } from "@/lib/api";
import { ACTIVITY_ICONS, activityText, timeAgo } from "@/lib/activity";
import { usePipelineFeed, PipelineFlowCompact, PipelineFeed } from "@/components/pipeline-viz";
import { Sparkles, History, Send, Paperclip, Mic, Square } from "lucide-react";

export const Route = createFileRoute("/inbox")({
  head: () => ({ meta: [{ title: "Inbox · AI Middleman" }] }),
  component: InboxPage,
});

function lastDraft(events: ThreadEvent[]) {
  return [...events].reverse().find((e) => e.event_type === "draft_suggested");
}

function isPending(events: ThreadEvent[]) {
  const draft = lastDraft(events);
  if (!draft) return false;
  return !events.some((e) => e.created_at > draft.created_at && ["draft_sent", "draft_skipped"].includes(e.event_type));
}

function InboxPage() {
  const [tab, setTab] = useState<"threads" | "audit">("threads");
  const [text, setText] = useState("");
  const [isRecording, setIsRecording] = useState(false);
  const [mediaError, setMediaError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const recordedChunksRef = useRef<Blob[]>([]);
  const queryClient = useQueryClient();

  const threadQuery = useQuery({
    queryKey: ["friend-thread"],
    queryFn: api.friendThread,
    refetchInterval: 2000,
    retry: 2,
  });
  const sendMutation = useMutation({
    mutationFn: (t: string) => api.friendSend(t),
    onSuccess: () => {
      setText("");
      queryClient.invalidateQueries({ queryKey: ["friend-thread"] });
    },
  });
  const sendMediaMutation = useMutation({
    mutationFn: ({ file, filename }: { file: File | Blob; filename: string }) => api.friendSendMedia(file, filename),
    onSuccess: (result) => {
      if ("error" in result) setMediaError(result.error);
      else setMediaError(null);
      queryClient.invalidateQueries({ queryKey: ["friend-thread"] });
    },
    onError: (e: Error) => setMediaError(e.message),
  });
  // Real audit trail — the most recent thread events, only fetched when the
  // Audit tab is open. (Replaces the old hardcoded mock AUDIT_LOG.)
  const activityQuery = useQuery({
    queryKey: ["activity"],
    queryFn: () => api.activity(25),
    enabled: tab === "audit",
  });

  const events = threadQuery.data?.events ?? [];
  const draft = lastDraft(events);
  const pending = isPending(events);
  const pipeline = usePipelineFeed();

  function handleFileChosen(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (file) sendMediaMutation.mutate({ file, filename: file.name });
    e.target.value = "";
  }

  async function toggleRecording() {
    if (isRecording) {
      mediaRecorderRef.current?.stop();
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      recordedChunksRef.current = [];
      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (e) => recordedChunksRef.current.push(e.data);
      recorder.onstop = () => {
        stream.getTracks().forEach((t) => t.stop());
        setIsRecording(false);
        const blob = new Blob(recordedChunksRef.current, { type: "audio/webm" });
        sendMediaMutation.mutate({ file: blob, filename: "voice.webm" });
      };
      recorder.start();
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
      setMediaError(null);
    } catch (e) {
      setMediaError(e instanceof Error ? e.message : "Mic access denied or unavailable");
    }
  }

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
            {activityQuery.isLoading ? (
              <div className="py-6 text-sm text-muted-foreground">Loading activity…</div>
            ) : activityQuery.isError ? (
              <div className="py-6 text-sm text-destructive">Couldn't load the audit trail. Is the backend running?</div>
            ) : !activityQuery.data?.length ? (
              <div className="py-6 text-sm text-muted-foreground">No activity yet — send a request below to get started.</div>
            ) : (
              <ul className="divide-y divide-border">
                {activityQuery.data.map((a, i) => {
                  const Icon = ACTIVITY_ICONS[a.event_type] ?? Sparkles;
                  return (
                    <li key={i} className="py-3 flex items-center gap-3 text-sm">
                      <div className="w-8 h-8 rounded-full bg-accent grid place-items-center text-accent-foreground shrink-0">
                        <Icon className="w-4 h-4" />
                      </div>
                      <div className="flex-1 min-w-0 truncate">{activityText(a)}</div>
                      <div className="text-xs text-muted-foreground shrink-0">{timeAgo(a.created_at)}</div>
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>
        </div>
      ) : (
        <div className="flex-1 min-h-0 px-6 pb-6 grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4">
          {/* Live pipeline — shown side-by-side with the conversation for demos */}
          <Card className="flex flex-col min-h-0 overflow-hidden">
            <div className="p-3 border-b border-border">
              <SectionHeader title="Live Pipeline" subtitle="What the server is doing right now" />
            </div>
            <div className="flex-1 overflow-y-auto">
              <PipelineFlowCompact active={pipeline.active} />
              <div className="px-3 pb-3">
                <PipelineFeed events={pipeline.events} compact />
              </div>
            </div>
          </Card>

          {/* Conversation */}
          <Card className="flex flex-col min-h-0 overflow-hidden">
            <div className="h-14 px-4 border-b border-border flex items-center gap-3">
              <div className="w-9 h-9 rounded-xl bg-primary-soft text-primary-soft-foreground grid place-items-center text-xs font-semibold">SA</div>
              <div className="min-w-0">
                <div className="font-medium text-sm truncate">Sam → Alex</div>
                <div className="text-xs text-muted-foreground">Relayed live over WhatsApp</div>
              </div>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-3 bg-surface-2/40">
              {threadQuery.isLoading ? (
                <div className="text-sm text-muted-foreground text-center py-8">Loading conversation…</div>
              ) : threadQuery.isError ? (
                <div className="text-sm text-destructive text-center py-8">
                  Could not reach the API ({(threadQuery.error as Error)?.message ?? "unknown error"}).
                  <button onClick={() => threadQuery.refetch()} className="block mx-auto mt-2 underline">Retry</button>
                </div>
              ) : events.length === 0 ? (
                <div className="text-sm text-muted-foreground text-center py-8">No messages yet — send one below to kick off the pipeline.</div>
              ) : (
                events.map((e, i) => {
                  const bubble = (fromUs: boolean, content: string) => (
                    <div key={e.id} className={`flex ${fromUs ? "justify-end" : "justify-start"}`}>
                      <div className={`max-w-[70%] rounded-2xl px-3.5 py-2 text-sm whitespace-pre-wrap ${fromUs ? "bg-primary-soft text-primary-soft-foreground rounded-br-md" : "bg-surface rounded-bl-md shadow-soft"}`}>
                        {content}
                        <div className="text-[10px] opacity-60 mt-1 text-right">{new Date(e.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</div>
                      </div>
                    </div>
                  );
                  if (e.event_type === "friend_message") return bubble(true, e.payload.text ?? "");
                  if (e.event_type === "alex_reply") return bubble(false, e.payload.text ?? "");
                  if (e.event_type === "draft_sent") return bubble(false, e.payload.final_text ?? "");
                  if (e.event_type === "draft_skipped")
                    return <div key={e.id} className="text-xs text-muted-foreground text-center italic">— Alex skipped a suggested reply —</div>;
                  if (e.event_type === "draft_suggested" && !events.some((ev, j) => j > i && ["draft_sent", "draft_edited", "draft_skipped"].includes(ev.event_type)))
                    return <div key={e.id} className="text-xs text-muted-foreground text-center">⏳ Alex has a suggested reply pending on his WhatsApp…</div>;
                  return null;
                })
              )}
            </div>

            {mediaError && (
              <div className="px-4 py-2 text-xs text-destructive bg-destructive/10 border-t border-border">{mediaError}</div>
            )}

            {draft && pending ? (
              <div className="p-4 border-t border-border">
                <div className="rounded-2xl border border-primary-soft bg-primary-soft/40 p-3 flex items-center gap-2 text-xs text-primary-soft-foreground">
                  <Sparkles className="w-3.5 h-3.5 shrink-0" />
                  AI drafted a reply — waiting on Alex's Send / Edit / Skip decision on his WhatsApp.
                </div>
              </div>
            ) : null}

            <div className="p-3 border-t border-border flex gap-2">
              <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handleFileChosen} />
              <button
                type="button"
                title="Send an image"
                onClick={() => fileInputRef.current?.click()}
                disabled={sendMediaMutation.isPending}
                className="inline-flex items-center justify-center w-10 h-10 rounded-xl bg-muted text-foreground disabled:opacity-60 shrink-0"
              >
                <Paperclip className="w-4 h-4" />
              </button>
              <button
                type="button"
                title={isRecording ? "Stop recording" : "Record a voice note"}
                onClick={toggleRecording}
                disabled={sendMediaMutation.isPending}
                className={`inline-flex items-center justify-center w-10 h-10 rounded-xl shrink-0 disabled:opacity-60 ${isRecording ? "bg-destructive text-destructive-foreground" : "bg-muted text-foreground"}`}
              >
                {isRecording ? <Square className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
              </button>
              <input
                value={text}
                onChange={(e) => setText(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && text.trim()) sendMutation.mutate(text); }}
                placeholder="Message as Sam…"
                className="flex-1 h-10 px-3 rounded-xl bg-muted text-sm focus:outline-none"
              />
              <button
                onClick={() => text.trim() && sendMutation.mutate(text)}
                disabled={sendMutation.isPending || !text.trim()}
                className="inline-flex items-center gap-1.5 h-10 px-4 rounded-xl bg-primary-soft text-primary-soft-foreground text-sm font-medium disabled:opacity-60"
              >
                <Send className="w-4 h-4" /> Send
              </button>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
