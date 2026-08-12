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
import { Logo } from "./Logo";
import { ChevronDown, ChevronUp, Grip } from "./icons";
import { Callout, ErrorNote, Note } from "./ui";

function Row({
  candidate,
  index,
  total,
  showTier,
  onMove,
}: {
  candidate: Candidate;
  index: number;
  total: number;
  /** Only when the list is mixed — see the call site. */
  showTier: boolean;
  onMove: (from: number, to: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: candidate.id });

  const meta = [candidate.cuisine.slice(0, 2).join(", "), metres(candidate.distance_m)].filter(Boolean).join(" · ");

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`row touch-none py-3 ${isDragging ? "dragging" : ""}`}
    >
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-[13px] font-bold tabular-nums"
        style={
          index === 0
            ? { background: "var(--brand)", color: "var(--on-brand)" }
            : { background: "var(--surface-2)", color: "var(--text-2)" }
        }
      >
        {index + 1}
      </span>

      <div className="min-w-0 flex-1">
        {/* The badge sits outside the truncating span on purpose — a long
            restaurant name must never be able to clip the safety label. */}
        <div className="flex items-center gap-2">
          <span className="truncate text-[15px] font-semibold">{candidate.name}</span>
          {showTier ? <span className="badge badge-warn shrink-0">unverified</span> : null}
        </div>
        {meta ? (
          <p className="truncate text-[13px]" style={{ color: "var(--text-3)" }}>
            {meta}
          </p>
        ) : null}
      </div>

      {/* Arrows aren't a fallback — dragging is genuinely hard one-handed on a
          phone and impossible with a screen reader. */}
      <div className="flex shrink-0 flex-col">
        <button
          type="button"
          aria-label={`Move ${candidate.name} up`}
          className="flex h-7 w-8 items-center justify-center rounded-sm disabled:opacity-20"
          style={{ color: "var(--text-2)" }}
          disabled={index === 0}
          onClick={() => onMove(index, index - 1)}
        >
          <ChevronUp size={18} />
        </button>
        <button
          type="button"
          aria-label={`Move ${candidate.name} down`}
          className="flex h-7 w-8 items-center justify-center rounded-sm disabled:opacity-20"
          style={{ color: "var(--text-2)" }}
          disabled={index === total - 1}
          onClick={() => onMove(index, index + 1)}
        >
          <ChevronDown size={18} />
        </button>
      </div>

      <button
        type="button"
        className="-mr-1 shrink-0 cursor-grab touch-none px-1 active:cursor-grabbing"
        style={{ color: "var(--text-3)" }}
        aria-label={`Reorder ${candidate.name}`}
        {...attributes}
        {...listeners}
      >
        <Grip size={20} />
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
  // When everything in the vote is unverified — the usual case on real OSM
  // data — a badge on every row says nothing the banner hasn't, and eats the
  // restaurant name, which is the one thing people need to read to rank.
  // It earns its place only when the list is actually mixed.
  const mixedTiers = flaggedInVote && order.some((c) => c.tier === "feasible");

  return (
    <main>
      <Logo tagline="Drag your favourite to the top. That's the whole job." />

      {flaggedInVote ? (
        <div className="mb-5">
          <Callout title="Read this before you rank">
            The map data couldn&apos;t confirm everyone&apos;s dietary requirements at these places, so they&apos;re
            marked <strong>unverified</strong> rather than left out. None of them is confirmed safe — whoever has the
            restriction should call ahead.
          </Callout>
        </div>
      ) : (
        <div className="mb-5">
          <Note>
            These all work for everyone&apos;s requirements. You&apos;re ranking, not rating — so nobody can shout
            louder by scoring everything 1.
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
          <ul className="mb-6 space-y-2">
            {order.map((candidate, index) => (
              <Row
                key={candidate.id}
                candidate={candidate}
                index={index}
                total={order.length}
                showTier={mixedTiers && candidate.tier === "unverified"}
                onMove={move}
              />
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
        <section className="mt-10">
          <h2 className="label">Couldn&apos;t verify</h2>
          <div className="mb-3">
            <Note>The data doesn&apos;t say either way for these, so they&apos;re out of the vote rather than assumed fine.</Note>
          </div>
          <ul className="space-y-2">
            {unverified.map((candidate) => (
              <li key={candidate.id} className="panel-warn p-4">
                <p className="text-[15px] font-semibold" style={{ color: "var(--warn)" }}>
                  {candidate.name}
                </p>
                {candidate.cut_reasons.map((reason, index) => (
                  <p key={index} className="mt-1 text-[13px]" style={{ color: "var(--warn)" }}>
                    {reason.detail}
                  </p>
                ))}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {eliminated.length > 0 ? (
        <section className="mt-10">
          <h2 className="label">{eliminated.length} ruled out</h2>
          <ul className="card divide-y overflow-hidden" style={{ borderColor: "var(--border)" }}>
            {eliminated.slice(0, 8).map((candidate) => {
              const cut = candidate.cut_reasons.find((r) => r.kind === "eliminated");
              return (
                <li key={candidate.id} className="px-4 py-3" style={{ borderColor: "var(--border)" }}>
                  <p className="text-[14px] font-medium" style={{ color: "var(--text-2)" }}>
                    {candidate.name}
                  </p>
                  <p className="text-[13px]" style={{ color: "var(--text-3)" }}>
                    {cut?.detail ?? "ruled out"}
                  </p>
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}
    </main>
  );
}
