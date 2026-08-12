"use client";

import { useState } from "react";

import { DIET_CHIPS } from "@/lib/constraints";
import type { SessionState } from "@/lib/types";
import { Logo } from "./Logo";
import { Check, Share, Users } from "./icons";
import { Callout, ErrorNote, Note } from "./ui";

const dietLabel = (key: string) => DIET_CHIPS.find((c) => c.key === key)?.label ?? key;

const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

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
        await navigator.share({
          title: "Where are we eating?",
          text: "Rank a few places and Hangry settles it:",
          url: link,
        });
        return;
      } catch {
        /* dismissed — fall through to copy */
      }
    }
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const host = state.participants.find((p) => p.is_creator);

  return (
    <main>
      <Logo tagline="Get everyone in, then start." />

      <section className="card mb-4 p-4">
        <span className="label">Share this link</span>
        <div
          className="mb-3 truncate px-4 py-3 text-[14px] font-medium"
          style={{ background: "var(--surface-2)", borderRadius: "var(--r-sm)", color: "var(--brand)" }}
        >
          {link || `/s/${slug}`}
        </div>
        <button className="btn btn-primary" onClick={share}>
          {copied ? <Check size={19} /> : <Share size={19} />}
          {copied ? "Copied" : "Send to the group"}
        </button>
      </section>

      <section className="card mb-4 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="label !mb-0">In so far</span>
          <span className="flex items-center gap-1.5 text-[14px] font-semibold" style={{ color: "var(--text-2)" }}>
            <Users size={17} />
            {state.participants.length}
          </span>
        </div>

        <ul>
          {state.participants.map((person) => {
            const diets = person.hard_constraints?.diets ?? [];
            return (
              <li key={person.id} className="flex items-center gap-3 border-t px-4 py-3" style={{ borderColor: "var(--border)" }}>
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[13px] font-bold"
                  style={{ background: "var(--brand-tint)", color: "var(--brand)" }}
                >
                  {initials(person.display_name)}
                </span>

                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[15px] font-semibold">
                    {person.display_name}
                    {person.is_creator ? (
                      <span className="ml-2 text-[12px] font-medium" style={{ color: "var(--text-3)" }}>
                        host
                      </span>
                    ) : null}
                  </span>
                  <span className="block truncate text-[13px]" style={{ color: diets.length ? "var(--warn)" : "var(--text-3)" }}>
                    {diets.length ? diets.map(dietLabel).join(" · ") : "No restrictions"}
                  </span>
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
            <Callout key={index} title="Worth knowing">
              {advisory.detail}
            </Callout>
          ))}
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
          <div className="card p-4">
            <Note>You&apos;re in. Waiting for {host?.display_name ?? "the host"} to start.</Note>
          </div>
        )}
      </div>
    </main>
  );
}
