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

import { distanceLabel } from "@/lib/constraints";
import type { Candidate, SessionState } from "@/lib/types";
import { Masthead } from "./Logo";
import { ChevronDown, ChevronUp, DragHandle } from "./icons";
import { Caution, ErrorNote, Note } from "./ui";

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
  /** Only when the list is mixed. See the call site. */
  showTier: boolean;
  onMove: (from: number, to: number) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: candidate.id });
  const meta = [candidate.cuisine.slice(0, 2).join(", "), distanceLabel(candidate.distance_m)].filter(Boolean).join(", ");

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`surface flex touch-none items-center gap-3 py-2 pl-4 pr-1 ${isDragging ? "is-dragging" : ""}`}
    >
      <span
        className="w-6 shrink-0 text-center font-serif text-title-3 tabular-nums"
        style={{ color: index === 0 ? "var(--brand)" : "var(--ink-3)" }}
      >
        {index + 1}
      </span>

      <div className="min-w-0 flex-1 py-1">
        {/* The tag sits outside the truncating span so a long restaurant name
            can never clip the safety label. */}
        <div className="flex items-center gap-2">
          <span className="truncate font-medium">{candidate.name}</span>
          {showTier ? <span className="tag tag-caution shrink-0">Unverified</span> : null}
        </div>
        {meta ? (
          <p className="truncate text-footnote" style={{ color: "var(--ink-3)" }}>
            {meta}
          </p>
        ) : null}
      </div>

      {/* Arrows give a second way through. Dragging is hard with one
          thumb and impossible with a screen reader. Both clear 44pt. */}
      <div className="flex shrink-0 flex-col">
        <button
          type="button"
          aria-label={`Move ${candidate.name} up`}
          className="flex items-center justify-center rounded-s disabled:opacity-25"
          style={{ minWidth: "var(--tap)", minHeight: "1.375rem", color: "var(--ink-2)" }}
          disabled={index === 0}
          onClick={() => onMove(index, index - 1)}
        >
          <ChevronUp size={18} />
        </button>
        <button
          type="button"
          aria-label={`Move ${candidate.name} down`}
          className="flex items-center justify-center rounded-s disabled:opacity-25"
          style={{ minWidth: "var(--tap)", minHeight: "1.375rem", color: "var(--ink-2)" }}
          disabled={index === total - 1}
          onClick={() => onMove(index, index + 1)}
        >
          <ChevronDown size={18} />
        </button>
      </div>

      <button
        type="button"
        className="flex shrink-0 cursor-grab touch-none items-center justify-center active:cursor-grabbing"
        style={{ minWidth: "var(--tap)", minHeight: "var(--tap)", color: "var(--ink-3)" }}
        aria-label={`Reorder ${candidate.name}`}
        {...attributes}
        {...listeners}
      >
        <DragHandle size={20} />
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
  const flagged = order.some((c) => c.tier === "unverified");
  // When everything in the vote is unverified, which is the usual case on real
  // map data, a tag on every row repeats the banner and eats the restaurant
  // name. It earns its place only when the list is mixed.
  const mixedTiers = flagged && order.some((c) => c.tier === "feasible");

  return (
    <main>
      <Masthead context="Drag your favourite to the top." />

      {flagged ? (
        <div className="mb-6">
          <Caution title="Read this before you rank">
            The map data could not confirm everyone&apos;s dietary requirements at these places, so they are marked
            unverified rather than left out. None of them is confirmed safe. Whoever has the restriction should call
            ahead.
          </Caution>
        </div>
      ) : (
        <div className="mb-6">
          <Note>
            These all work for everyone&apos;s requirements. You are ranking rather than rating, so nobody can shout
            louder by scoring everything one.
          </Note>
        </div>
      )}

      {/* Allergies cannot be filtered on, because the map data holds nothing
          about them, so they arrive as an advisory instead. This screen used
          to drop them, which meant the one person the warning was written for
          never saw it at the moment they were choosing. */}
      {state.advisories.length > 0 ? (
        <div className="mb-6 space-y-3">
          {state.advisories.map((advisory, index) => (
            <Caution key={index} title="Nobody can check this for you">
              {advisory.detail}
            </Caution>
          ))}
        </div>
      ) : null}

      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragEnd={onDragEnd}
        modifiers={[restrictToVerticalAxis, restrictToParentElement]}
      >
        <SortableContext items={order.map((c) => c.id)} strategy={verticalListSortingStrategy}>
          <ul className="mb-7 space-y-2">
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

      <div className="space-y-4">
        <ErrorNote>{error}</ErrorNote>
        <button className="btn btn-primary" onClick={() => onSubmit(order.map((c) => c.id))} disabled={busy}>
          {busy ? "Sending" : "Lock it in"}
        </button>
        <Note>
          {state.submitted} of {state.participants.length} have ranked so far.
        </Note>
      </div>

      {unverified.length > 0 ? (
        <section className="mt-12">
          <h2 className="eyebrow">Could not verify</h2>
          <div className="mb-3">
            <Note>The data says nothing either way for these, so they are out of the vote rather than assumed fine.</Note>
          </div>
          <ul className="space-y-2">
            {unverified.map((candidate) => (
              <li key={candidate.id} className="panel-caution p-4">
                <p className="font-medium" style={{ color: "var(--caution)" }}>
                  {candidate.name}
                </p>
                {candidate.cut_reasons.map((reason, index) => (
                  <p key={index} className="mt-1 text-footnote" style={{ color: "var(--caution)" }}>
                    {reason.detail}
                  </p>
                ))}
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      {eliminated.length > 0 ? (
        <section className="mt-12">
          <h2 className="eyebrow">{eliminated.length} ruled out</h2>
          <ul className="surface overflow-hidden">
            {eliminated.slice(0, 8).map((candidate, index) => {
              const cut = candidate.cut_reasons.find((r) => r.kind === "eliminated");
              return (
                <li
                  key={candidate.id}
                  className="px-4 py-3"
                  style={index > 0 ? { borderTop: "1px solid var(--hairline)" } : undefined}
                >
                  <p className="text-subhead font-medium" style={{ color: "var(--ink-2)" }}>
                    {candidate.name}
                  </p>
                  <p className="text-footnote" style={{ color: "var(--ink-3)" }}>
                    {cut?.detail ?? "Ruled out"}
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
