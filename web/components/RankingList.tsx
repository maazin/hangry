"use client";

import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import { restrictToParentElement, restrictToVerticalAxis } from "@dnd-kit/modifiers";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";

import { metres } from "@/lib/constraints";
import type { Candidate, SessionState } from "@/lib/types";
import { ErrorNote, Note, Wordmark } from "./ui";

function Row({
  candidate,
  index,
  total,
  onMove,
}: {
  candidate: Candidate;
  index: number;
  total: number;
  onMove: (from: number, to: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: candidate.id });

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`card flex touch-none items-center gap-3 ${isDragging ? "dragging" : ""}`}
    >
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-sm font-bold"
        style={{ background: "var(--accent)", color: "var(--accent-ink)" }}
      >
        {index + 1}
      </span>

      <div className="min-w-0 flex-1">
        {/* The badge sits outside the truncating span on purpose — a long
            restaurant name must never be able to clip the safety label. */}
        <div className="flex items-baseline gap-2">
          <span className="truncate font-semibold">{candidate.name}</span>
          {candidate.tier === "unverified" ? (
            <span className="shrink-0 text-[10px] font-bold uppercase" style={{ color: "var(--warn)" }}>
              unverified
            </span>
          ) : null}
        </div>
        <p className="truncate text-xs" style={{ color: "var(--muted)" }}>
          {[candidate.cuisine.slice(0, 2).join(", "), metres(candidate.distance_m)].filter(Boolean).join(" · ")}
        </p>
      </div>

      {/* Arrows are not a fallback — dragging is genuinely hard one-handed on
          a phone, and impossible with a screen reader. */}
      <div className="flex shrink-0 flex-col gap-1">
        <button
          type="button"
          aria-label={`Move ${candidate.name} up`}
          className="rounded-lg px-2 py-0.5 text-xs disabled:opacity-25"
          style={{ background: "var(--surface-2)" }}
          disabled={index === 0}
          onClick={() => onMove(index, index - 1)}
        >
          ▲
        </button>
        <button
          type="button"
          aria-label={`Move ${candidate.name} down`}
          className="rounded-lg px-2 py-0.5 text-xs disabled:opacity-25"
          style={{ background: "var(--surface-2)" }}
          disabled={index === total - 1}
          onClick={() => onMove(index, index + 1)}
        >
          ▼
        </button>
      </div>

      <button
        type="button"
        className="shrink-0 cursor-grab px-1 text-lg active:cursor-grabbing"
        style={{ color: "var(--muted)" }}
        aria-label={`Reorder ${candidate.name}`}
        {...attributes}
        {...listeners}
      >
        ⠿
      </button>
    </li>
  );
}

export function RankingList({
  state,
  candidates,
  busy,
  error,
  onSubmit,
}: {
  state: SessionState;
  candidates: Candidate[];
  busy: boolean;
  error: string | null;
  onSubmit: (orderedIds: string[]) => void;
}) {
  const [order, setOrder] = useState<Candidate[]>(candidates);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    // A short hold before dragging, so the page still scrolls under a thumb.
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 8 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function move(from: number, to: number) {
    setOrder((current) => arrayMove(current, from, to));
  }

  function onDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    setOrder((current) => {
      const from = current.findIndex((c) => c.id === active.id);
      const to = current.findIndex((c) => c.id === over.id);
      return arrayMove(current, from, to);
    });
  }

  const unverified = state.candidates.filter((c) => c.tier === "unverified" && !c.locked);
  const eliminated = state.candidates.filter((c) => c.tier === "eliminated");
  const flaggedInVote = order.some((c) => c.tier === "unverified");

  return (
    <main>
      <Wordmark tagline="Best at the top. That's the whole job." />

      {flaggedInVote ? (
        <div className="card mb-4" style={{ borderColor: "var(--warn)" }}>
          <p className="text-sm font-bold" style={{ color: "var(--warn)" }}>
            Read this before you rank
          </p>
          <div className="mt-1">
            <Note tone="warn">
              The map data couldn&apos;t confirm everyone&apos;s dietary requirements at these places, so they&apos;re
              marked <strong>unverified</strong> rather than left out. None of them is confirmed safe — whoever has the
              restriction should call ahead.
            </Note>
          </div>
        </div>
      ) : (
        <div className="mb-4">
          <Note>
            These are the only places that work for everyone&apos;s requirements. Drag them into your order —
            you&apos;re ranking, not rating, so nobody can shout louder by scoring everything 1.
          </Note>
        </div>
      )}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={onDragEnd}
        modifiers={[restrictToVerticalAxis, restrictToParentElement]}
      >
        <SortableContext items={order.map((c) => c.id)} strategy={verticalListSortingStrategy}>
          <ul className="mb-5 space-y-2">
            {order.map((candidate, index) => (
              <Row key={candidate.id} candidate={candidate} index={index} total={order.length} onMove={move} />
            ))}
          </ul>
        </SortableContext>
      </DndContext>

      <div className="space-y-3">
        <ErrorNote>{error}</ErrorNote>
        <button className="btn btn-primary" onClick={() => onSubmit(order.map((c) => c.id))} disabled={busy}>
          {busy ? "Sending…" : "Lock it in"}
        </button>
        <Note>
          {state.submitted} of {state.participants.length} have ranked so far.
        </Note>
      </div>

      {unverified.length > 0 ? (
        <section className="mt-8">
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide" style={{ color: "var(--warn)" }}>
            Couldn&apos;t verify
          </h2>
          <Note tone="warn">
            The map data doesn&apos;t say either way for these, so they&apos;re out of the vote rather than assumed fine.
          </Note>
          <ul className="mt-3 space-y-2">
            {unverified.map((candidate) => (
              <li key={candidate.id} className="card" style={{ borderColor: "var(--warn)" }}>
                <p className="font-semibold">{candidate.name}</p>
                {candidate.cut_reasons.map((reason, index) => (
                  <p key={index} className="mt-1 text-xs" style={{ color: "var(--warn)" }}>
                    {reason.detail}
                  </p>
                ))}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {eliminated.length > 0 ? (
        <section className="mt-8">
          <h2 className="mb-2 text-sm font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
            {eliminated.length} ruled out
          </h2>
          <ul className="space-y-2">
            {eliminated.slice(0, 8).map((candidate) => {
              const cut = candidate.cut_reasons.find((r) => r.kind === "eliminated");
              return (
                <li key={candidate.id} className="flex items-baseline justify-between gap-3 rounded-xl px-3 py-2 text-sm" style={{ background: "var(--surface)" }}>
                  <span style={{ color: "var(--muted)" }}>{candidate.name}</span>
                  <span className="text-right text-xs" style={{ color: "var(--muted)" }}>
                    {cut?.detail ?? "ruled out"}
                  </span>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
