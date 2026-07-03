import { createFileRoute } from "@tanstack/react-router";
import { Card, SectionHeader } from "@/components/ui-bits";
import { usePipelineFeed, PipelineFlow, PipelineFeed } from "@/components/pipeline-viz";

export const Route = createFileRoute("/pipeline")({
  head: () => ({ meta: [{ title: "Pipeline · AI Middleman" }] }),
  component: PipelinePage,
});

function PipelinePage() {
  const { events, active, isError, error } = usePipelineFeed();

  return (
    <div className="px-6 py-6 space-y-6">
      <SectionHeader
        title="Live Pipeline"
        subtitle="What the server is doing right now, translated from the terminal into plain English."
      />

      {isError && (
        <div className="text-sm text-destructive">
          Could not reach the API ({error?.message ?? "unknown error"}).
        </div>
      )}

      <PipelineFlow active={active} />

      <Card className="p-5">
        <div className="text-sm font-semibold mb-3">Activity feed</div>
        <PipelineFeed events={events} />
      </Card>
    </div>
  );
}
