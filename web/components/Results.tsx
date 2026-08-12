"use client";

import { useState } from "react";

import { metres } from "@/lib/constraints";
import type { SessionState } from "@/lib/types";
import { Note, Wordmark } from "./ui";

/**
 * A flat ranked list recreates the paralysis this product exists to end, so
 * #1 is visually dominant and every runner-up carries what it costs and whom.
 */
export function Results({ slug, state }: { slug: string; state: SessionState }) {
  const [showCuts, setShowCuts] = useState(false);
  const [showRest, setShowRest] = useState(false);
  const result = state.result!;
  // Three, not eight. A long ranked list recreates exactly the paralysis this
  // product exists to end, so the tail is available but not in the way.
  const [winner, ...rest] = result.ranked;
  const runnersUp = rest.slice(0, 2);
  const tail = rest.slice(2);
  const comparison = result.comparison;
  const eliminated = state.candidates.filter((c) => c.tier === "eliminated");
  const unverified = state.candidates.filter((c) => c.tier === "unverified" && !c.locked);
  const winnerCandidate = state.candidates.find((c) => c.id === winner.candidate_id);
  const winnerUnverified = winnerCandidate?.tier === "unverified";

  const mapsUrl = (lat: number, lon: number, name: string) =>
    `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=18/${lat}/${lon}&query=${encodeURIComponent(name)}`;

  return (
    <main>
      <Wordmark tagline="Settled." />

      <section className="card mb-4" style={{ borderColor: "var(--accent)", background: "var(--surface-2)" }}>
        <p className="mb-1 text-xs font-bold uppercase tracking-widest" style={{ color: "var(--accent)" }}>
          Go here
        </p>
        <h2 className="text-3xl font-black leading-tight">{winner.name}</h2>
        <p className="mt-1 text-sm" style={{ color: "var(--muted)" }}>
          {[winner.cuisine.slice(0, 3).join(", "), metres(winner.distance_m)].filter(Boolean).join(" · ")}
        </p>
        <p className="mt-3 text-base leading-relaxed">{winner.annotation}</p>

        {/* The winner can be a place the data couldn't verify. Saying so on
            the headline card is the difference between a tool an allergic
            person trusts and one they abandon. */}
        {winnerUnverified ? (
          <div className="mt-3 rounded-xl px-3 py-2.5" style={{ background: "rgb(232 176 70 / 0.12)" }}>
            <p className="text-sm font-semibold" style={{ color: "var(--warn)" }}>
              Not verified — call ahead
            </p>
            {winnerCandidate?.cut_reasons.map((reason, index) => (
              <p key={index} className="mt-1 text-xs" style={{ color: "var(--warn)" }}>
                {reason.detail}
              </p>
            ))}
          </div>
        ) : null}

        <a
          className="btn btn-primary mt-4 block text-center"
          href={mapsUrl(winner.lat ?? 0, winner.lon ?? 0, winner.name)}
          target="_blank"
          rel="noreferrer"
        >
          Open in maps
        </a>
      </section>

      {runnersUp.length > 0 ? (
        <section className="mb-4 space-y-2">
          {runnersUp.map((option, index) => (
            <article key={option.candidate_id} className="card">
              <div className="flex items-baseline gap-2">
                <span className="text-sm font-bold" style={{ color: "var(--muted)" }}>
                  {index + 2}
                </span>
                <h3 className="font-bold">{option.name}</h3>
              </div>
              <p className="mt-1 text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
                {option.annotation}
              </p>
            </article>
          ))}

          {tail.length > 0 ? (
            showRest ? (
              tail.map((option, index) => (
                <article key={option.candidate_id} className="card">
                  <div className="flex items-baseline gap-2">
                    <span className="text-sm font-bold" style={{ color: "var(--muted)" }}>
                      {index + 4}
                    </span>
                    <h3 className="font-bold">{option.name}</h3>
                  </div>
                  <p className="mt-1 text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
                    {option.annotation}
                  </p>
                </article>
              ))
            ) : (
              <button className="btn btn-ghost" onClick={() => setShowRest(true)}>
                Show the other {tail.length}
              </button>
            )
          ) : null}
        </section>
      ) : null}

      {/* The screenshot. Showing the group what the popular answer would have
          cost is the fairness argument and the shareable bit at once. */}
      {comparison ? (
        <section className="card mb-4">
          <p className="mb-3 text-base font-bold leading-snug">{comparison.headline}</p>
          <dl className="space-y-2 text-sm">
            <Row label="Straight majority vote" value={comparison.utilitarian?.name} note={comparison.utilitarian?.excludes?.length ? `leaves out ${comparison.utilitarian.excludes.join(", ")}` : "nobody left out"} tone={comparison.utilitarian?.excludes?.length ? "danger" : "muted"} />
            <Row label="Safest for everyone" value={comparison.maximin?.name} note="nobody's last choice, nobody's first either" />
            <Row label="Hangry's answer" value={comparison.minimax_regret?.name} note="the least anyone gives up" tone="ok" />
          </dl>
          <div className="mt-3">
            <Note>
              Hangry minimises the worst individual regret rather than maximising the average, which is why the answer
              can differ from what most people wanted.
            </Note>
          </div>
        </section>
      ) : null}

      {state.advisories.length > 0 ? (
        <section className="card mb-4" style={{ borderColor: "var(--warn)" }}>
          {state.advisories.map((advisory, index) => (
            <p key={index} className="text-sm leading-relaxed" style={{ color: "var(--warn)" }}>
              {advisory.detail}
            </p>
          ))}
        </section>
      ) : null}

      {eliminated.length + unverified.length > 0 ? (
        <section className="mb-6">
          <button
            className="btn btn-ghost"
            onClick={() => setShowCuts((v) => !v)}
            aria-expanded={showCuts}
          >
            {showCuts ? "Hide" : `Why ${eliminated.length + unverified.length} places didn't make it`}
          </button>

          {showCuts ? (
            <ul className="mt-3 space-y-2">
              {[...unverified, ...eliminated].map((candidate) => (
                <li key={candidate.id} className="card">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="font-semibold">{candidate.name}</p>
                    <span
                      className="shrink-0 rounded-full px-2 py-0.5 text-[11px] font-bold uppercase"
                      style={{
                        color: candidate.tier === "unverified" ? "var(--warn)" : "var(--muted)",
                        background: "var(--surface-2)",
                      }}
                    >
                      {candidate.tier === "unverified" ? "unverified" : "ruled out"}
                    </span>
                  </div>
                  {candidate.cut_reasons.map((reason, index) => (
                    <p key={index} className="mt-1 text-xs" style={{ color: reason.kind === "unknown" ? "var(--warn)" : "var(--muted)" }}>
                      {reason.detail}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      <footer className="space-y-3">
        <Note>
          Ranked by {result.alternates?.voters?.length ?? state.participants.length} of {state.participants.length}.
          {result.alternates?.non_voters?.length
            ? ` ${result.alternates.non_voters.join(", ")} didn't rank, so nothing was assumed on their behalf.`
            : ""}
        </Note>
        <Note>
          Hangry never says a place is safe — only that nothing in the listed data conflicts. Check with the restaurant
          if it matters.
        </Note>
        <a className="btn btn-ghost block text-center" href="/">
          Start another
        </a>
      </footer>
    </main>
  );
}

function Row({
  label,
  value,
  note,
  tone = "muted",
}: {
  label: string;
  value?: string;
  note?: string;
  tone?: "muted" | "danger" | "ok";
}) {
  if (!value) return null;
  const colour = { muted: "var(--muted)", danger: "var(--danger)", ok: "var(--ok)" }[tone];
  return (
    <div className="flex items-baseline justify-between gap-3 border-t pt-2" style={{ borderColor: "var(--border)" }}>
      <dt className="shrink-0 text-xs uppercase tracking-wide" style={{ color: "var(--muted)" }}>
        {label}
      </dt>
      <dd className="text-right">
        <span className="font-semibold">{value}</span>
        {note ? (
          <span className="block text-xs" style={{ color: colour }}>
            {note}
          </span>
        ) : null}
      </dd>
    </div>
  );
}
