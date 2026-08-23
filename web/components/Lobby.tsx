"use client";

import { useState } from "react";

import { DIET_CHIPS } from "@/lib/constraints";
import type { SessionState } from "@/lib/types";
import { Masthead } from "./Logo";
import { People, Share } from "./icons";
import { Caution, ErrorNote, Note } from "./ui";

const dietLabel = (key: string) => DIET_CHIPS.find((c) => c.key === key)?.label ?? key;

/**
 * The waiting room for a standalone session, meaning one started outside a
 * group. Groups reach ranking without passing through here.
 */
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
    if (navigator.share) {
      try {
        await navigator.share({ title: "Where are we eating?", text: "Rank a few places and Hangry settles it.", url: link });
        return;
      } catch {
        /* dismissed, fall through to copy */
      }
    }
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const host = state.participants.find((p) => p.is_creator);

  return (
    <main>
      <Masthead context="Get everyone in, then start." />

      <section className="surface mb-4 p-5">
        <span className="eyebrow">Share this link</span>
        <p
          className="mb-4 truncate rounded-m px-4 py-3 text-subhead"
          style={{ background: "var(--surface-2)", color: "var(--brand)" }}
        >
          {link || `/s/${slug}`}
        </p>
        <button className="btn btn-primary" onClick={share}>
          <Share size={18} />
          {copied ? "Link copied" : "Send to the group"}
        </button>
      </section>

      <section className="surface mb-4 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="eyebrow !mb-0">In so far</span>
          <span className="flex items-center gap-1.5 text-subhead font-medium" style={{ color: "var(--ink-2)" }}>
            <People size={17} />
            {state.participants.length}
          </span>
        </div>

        <ul>
          {state.participants.map((person) => {
            const diets = person.hard_constraints?.diets ?? [];
            return (
              <li
                key={person.id}
                className="flex items-start justify-between gap-3 px-4 py-3"
                style={{ borderTop: "1px solid var(--hairline)" }}
              >
                <span className="min-w-0 font-medium">
                  {person.display_name}
                  {person.is_creator ? (
                    <span className="ml-2 text-footnote font-normal" style={{ color: "var(--ink-3)" }}>
                      host
                    </span>
                  ) : null}
                </span>
                <span
                  className="shrink-0 text-right text-footnote"
                  style={{ color: diets.length ? "var(--caution)" : "var(--ink-3)" }}
                >
                  {diets.length ? diets.map(dietLabel).join(", ") : "No restrictions"}
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      {state.participants.length < 2 ? (
        <div className="mb-4">
          <Note>Hangry needs at least a couple of people to be worth anything. Send the link.</Note>
        </div>
      ) : null}

      {state.advisories.length > 0 ? (
        <div className="mb-4 space-y-3">
          {state.advisories.map((advisory, index) => (
            <Caution key={index} title="Worth knowing">
              {advisory.detail}
            </Caution>
          ))}
        </div>
      ) : null}

      <div className="space-y-4">
        <ErrorNote>{error}</ErrorNote>

        {canStart ? (
          <>
            <button className="btn btn-primary" onClick={onStart} disabled={busy}>
              {busy ? "Finding places" : "Find us somewhere"}
            </button>
            <Note>Once you start, nobody else can join. It would change what everyone already ranked.</Note>
          </>
        ) : (
          <section className="surface p-4">
            <Note>You are in. Waiting for {host?.display_name ?? "the host"} to start.</Note>
          </section>
        )}
      </div>
    </main>
  );
}
