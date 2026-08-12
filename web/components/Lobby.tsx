"use client";

import { useState } from "react";

import { DIET_CHIPS } from "@/lib/constraints";
import type { SessionState } from "@/lib/types";
import { ErrorNote, Note, Wordmark } from "./ui";

const dietLabel = (key: string) => DIET_CHIPS.find((c) => c.key === key)?.label ?? key;

export function Lobby({
  slug,
  state,
  busy,
  error,
  canStart,
  onStart,
}: {
  slug: string;
  state: SessionState;
  busy: boolean;
  error: string | null;
  canStart: boolean;
  onStart: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const link = typeof window === "undefined" ? "" : `${window.location.origin}/s/${slug}`;

  async function share() {
    // The native sheet drops it straight into the group chat, which is the
    // only distribution channel this product has.
    if (navigator.share) {
      try {
        await navigator.share({ title: "Where are we eating?", text: "Rank a few places and Hangry settles it:", url: link });
        return;
      } catch {
        /* user dismissed; fall through to copy */
      }
    }
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <main>
      <Wordmark tagline="Get everyone in, then start." />

      <div className="card mb-4">
        <span className="label">Share this link</span>
        <div className="mb-3 truncate rounded-xl px-4 py-3 font-mono text-sm" style={{ background: "var(--surface-2)", color: "var(--accent)" }}>
          {link || `/s/${slug}`}
        </div>
        <button className="btn btn-primary" onClick={share}>
          {copied ? "Copied" : "Send to the group"}
        </button>
      </div>

      <div className="card mb-4">
        <div className="mb-3 flex items-baseline justify-between">
          <span className="label !mb-0">In so far</span>
          <span className="text-sm font-semibold" style={{ color: "var(--muted)" }}>
            {state.participants.length}
          </span>
        </div>

        <ul className="space-y-2">
          {state.participants.map((person) => {
            const diets = person.hard_constraints?.diets ?? [];
            return (
              <li key={person.id} className="flex items-start justify-between gap-3 rounded-xl px-3 py-2.5" style={{ background: "var(--surface-2)" }}>
                <span className="font-semibold">
                  {person.display_name}
                  {person.is_creator ? <span className="ml-2 text-xs font-normal" style={{ color: "var(--muted)" }}>host</span> : null}
                </span>
                <span className="text-right text-xs" style={{ color: diets.length ? "var(--warn)" : "var(--muted)" }}>
                  {diets.length ? diets.map(dietLabel).join(", ") : "no restrictions"}
                </span>
              </li>
            );
          })}
        </ul>

        {state.participants.length < 2 ? (
          <div className="mt-3">
            <Note>Hangry needs at least a couple of people to be worth anything. Send the link.</Note>
          </div>
        ) : null}
      </div>

      {state.advisories.length > 0 ? (
        <div className="card mb-4" style={{ borderColor: "var(--warn)" }}>
          <span className="label" style={{ color: "var(--warn)" }}>
            Worth knowing
          </span>
          <ul className="space-y-2">
            {state.advisories.map((advisory, index) => (
              <li key={index}>
                <Note tone="warn">{advisory.detail}</Note>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="space-y-3">
        <ErrorNote>{error}</ErrorNote>

        {canStart ? (
          <>
            <button className="btn btn-primary" onClick={onStart} disabled={busy}>
              {busy ? "Finding places…" : "Find us somewhere"}
            </button>
            <Note>Once you start, nobody else can join — it would change what everyone already ranked.</Note>
          </>
        ) : (
          <Note>You&apos;re in. Waiting for {state.participants.find((p) => p.is_creator)?.display_name ?? "the host"} to start.</Note>
        )}
      </div>
    </main>
  );
}
