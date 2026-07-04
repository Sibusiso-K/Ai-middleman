import { Children, useEffect, useRef, useState, type ReactNode } from "react";

/**
 * A two-pane split whose divider the user can drag to favor one pane over the
 * other. Lays the panes out side-by-side on wide screens and stacked on narrow
 * ones (below the `lg` breakpoint), flipping the drag axis to match. The chosen
 * ratio is remembered per `storageKey` across reloads.
 *
 * Expects exactly two children — the first and second panes.
 */
export function ResizableSplit({
  children,
  storageKey,
  defaultFirst = 35,
  minFirst = 18,
  minSecond = 28,
}: {
  children: ReactNode;
  storageKey?: string;
  /** Initial size of the first pane, as a percentage of the container. */
  defaultFirst?: number;
  /** Smallest the first pane may shrink to (%). */
  minFirst?: number;
  /** Smallest the second pane may shrink to (%). */
  minSecond?: number;
}) {
  const [first, second] = Children.toArray(children);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingRef = useRef(false);

  // Start from the default so server and first client render agree (localStorage
  // isn't available during SSR), then restore any saved ratio after mount.
  const [pct, setPct] = useState<number>(defaultFirst);
  useEffect(() => {
    if (!storageKey) return;
    const saved = Number(window.localStorage.getItem(storageKey));
    if (saved >= minFirst && saved <= 100 - minSecond) setPct(saved);
  }, [storageKey, minFirst, minSecond]);

  // Side-by-side at lg and up, stacked below. Drives the drag axis + cursor.
  const [horizontal, setHorizontal] = useState(true);
  useEffect(() => {
    const mq = window.matchMedia("(min-width: 1024px)");
    const sync = () => setHorizontal(mq.matches);
    sync();
    mq.addEventListener("change", sync);
    return () => mq.removeEventListener("change", sync);
  }, []);

  function onPointerDown(e: React.PointerEvent) {
    draggingRef.current = true;
    e.currentTarget.setPointerCapture(e.pointerId);
  }
  function onPointerMove(e: React.PointerEvent) {
    if (!draggingRef.current || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const raw = horizontal
      ? ((e.clientX - rect.left) / rect.width) * 100
      : ((e.clientY - rect.top) / rect.height) * 100;
    setPct(Math.min(100 - minSecond, Math.max(minFirst, raw)));
  }
  function onPointerUp(e: React.PointerEvent) {
    if (!draggingRef.current) return;
    draggingRef.current = false;
    e.currentTarget.releasePointerCapture(e.pointerId);
    if (storageKey) window.localStorage.setItem(storageKey, String(Math.round(pct)));
  }

  return (
    <div
      ref={containerRef}
      className={`flex h-full min-h-0 ${horizontal ? "flex-row" : "flex-col"}`}
    >
      <div style={{ flexGrow: pct, flexBasis: 0 }} className="flex min-h-0 min-w-0">
        {first}
      </div>

      <div
        role="separator"
        aria-orientation={horizontal ? "vertical" : "horizontal"}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onDoubleClick={() => setPct(defaultFirst)}
        title="Drag to resize · double-click to reset"
        className={`group shrink-0 flex items-center justify-center touch-none ${
          horizontal ? "w-3 cursor-col-resize" : "h-3 cursor-row-resize"
        }`}
      >
        <div
          className={`rounded-full bg-border transition-colors group-hover:bg-primary-soft ${
            horizontal ? "w-1 h-10" : "h-1 w-10"
          }`}
        />
      </div>

      <div style={{ flexGrow: 100 - pct, flexBasis: 0 }} className="flex min-h-0 min-w-0">
        {second}
      </div>
    </div>
  );
}
