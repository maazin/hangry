"use client";

import { useState } from "react";

import { metres } from "@/lib/constraints";
import type { SessionState } from "@/lib/types";
import { Logo } from "./Logo";
import { Alert, ArrowRight, Check } from "./icons";
import { Callout, Note } from "./ui";

/**
 * A flat ranked list recreates the paralysis this product exists to end, so
 * #1 gets a card of its own and everything below it carries what it costs
 * and whom. Three by default; the tail is available but out of the way.
 */
export function Results({ slug, state }: { slug: string; state: SessionState }) {
  const [showCuts, setShowCuts] = useState(false);
  const [showRest, setShowRest] = useState(false);

  const result = state.result!;
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
      <Logo tagline="Settled." />

      <section
        className="mb-4 overflow-hidden"
        style={{ borderRadius: "var(--r-lg)", boxShadow: "var(--shadow-md)", border: "1px solid var(--border)" }}
      >
        <div className="px-5 pb-5 pt-5" style={{ background: "var(--brand-tint)" }}>
          <p className="mb-2 flex items-center gap-1.5 text-[12px] font-bold uppercase" style={{ color: "var(--brand)", letterSpacing: "0.07em" }}>
            <Check size={15} />
            Go here
          </p>
          <h2 className="text-[30px] font-bold leading-[1.1]">{winner.name}</h2>
          <p className="mt-1.5 text-[14px]" style={{ color: "var(--text-2)" }}>
            {[winner.cuisine.slice(0, 3).join(", "), metres(winner.distance_m)].filter(Boolean).join(" · ")}
          </p>
        </div>

        <div className="px-5 py-5" style={{ background: "var(--surface)" }}>
          <p className="text-[16px] leading-relaxed">{winner.annotation}</p>

          {/* The winner can be a place the data couldn't verify. Saying so on
              the headline card is the difference between a tool an allergic
              person trusts and one they abandon. */}
          {winnerUnverified ? (
            <div className="mt-4">
              <Callout title="Not verified — call ahead">
                <ul className="space-y-1">
                  {winnerCandidate?.cut_reasons.map((reason, index) => (
                    <li key={index}>{reason.detail}</li>
                  ))}
                </ul>
              </Callout>
            </div>
          ) : null}

          <a
            className="btn btn-primary mt-5"
            href={mapsUrl(winner.lat ?? 0, winner.lon ?? 0, winner.name)}
            target="_blank"
            rel="noreferrer"
          >
            Open in maps
            <ArrowRight size={18} />
          </a>
        </div>
      </section>

      {runnersUp.length > 0 ? (
        <section className="mb-4 space-y-2">
          {runnersUp.map((option, index) => (
            <article key={option.candidate_id} className="card p-4">
              <div className="flex items-baseline gap-2.5">
                <span className="text-[13px] font-bold tabular-nums" style={{ color: "var(--text-3)" }}>
                  {index + 2}
                </span>
                <h3 className="text-[16px] font-semibold">{option.name}</h3>
              </div>
              <p className="mt-1 pl-[22px] text-[14px] leading-relaxed" style={{ color: "var(--text-2)" }}>
                {option.annotation}
              </p>
            </article>
          ))}

          {tail.length > 0 ? (
            showRest ? (
              tail.map((option, index) => (
                <article key={option.candidate_id} className="card p-4">
                  <div className="flex items-baseline gap-2.5">
                    <span className="text-[13px] font-bold tabular-nums" style={{ color: "var(--text-3)" }}>
                      {index + 4}
                    </span>
                    <h3 className="text-[16px] font-semibold">{option.name}</h3>
                  </div>
                  <p className="mt-1 pl-[22px] text-[14px] leading-relaxed" style={{ color: "var(--text-2)" }}>
                    {option.annotation}
                  </p>
                </article>
              ))
            ) : (
              <button className="btn btn-quiet" onClick={() => setShowRest(true)}>
                Show the other {tail.length}
              </button>
            )
          ) : null}
        </section>
      ) : null}

      {/* Showing the group what the popular answer would have cost is the
          fairness argument and the shareable bit at once. */}
      {comparison ? (
        <section className="card mb-4 p-5">
          <p className="text-[17px] font-semibold leading-snug">{comparison.headline}</p>

          <dl className="mt-4">
            <Rule
              label="Straight majority vote"
              value={comparison.utilitarian?.name}
              note={
                comparison.utilitarian?.excludes?.length
                  ? `leaves out ${comparison.utilitarian.excludes.join(", ")}`
                  : "nobody left out"
              }
              tone={comparison.utilitarian?.excludes?.length ? "danger" : "muted"}
            />
            <Rule label="Safest for everyone" value={comparison.maximin?.name} note="nobody's last choice, nobody's first either" />
            <Rule label="Hangry's answer" value={comparison.minimax_regret?.name} note="the least anyone gives up" tone="brand" />
          </dl>

          <div className="mt-4">
            <Note>
              Hangry minimises the worst individual regret rather than maximising the average, which is why the answer
              can differ from what most people wanted.
            </Note>
          </div>
        </section>
      ) : null}

      {state.advisories.length > 0 ? (
        <div className="mb-4 space-y-3">
          {state.advisories.map((advisory, index) => (
            <Callout key={index}>{advisory.detail}</Callout>
          ))}
        </div>
      ) : null}

      {eliminated.length + unverified.length > 0 ? (
        <section className="mb-6">
          <button className="btn btn-secondary" onClick={() => setShowCuts((v) => !v)} aria-expanded={showCuts}>
            {showCuts ? "Hide" : `Why ${eliminated.length + unverified.length} places didn't make it`}
          </button>

          {showCuts ? (
            <ul className="mt-3 space-y-2">
              {[...unverified, ...eliminated].map((candidate) => (
                <li key={candidate.id} className="card p-4">
                  <div className="flex items-baseline justify-between gap-2">
                    <p className="text-[15px] font-semibold">{candidate.name}</p>
                    <span className={`badge shrink-0 ${candidate.tier === "unverified" ? "badge-warn" : ""}`}
                      style={candidate.tier === "unverified" ? undefined : { background: "var(--surface-2)", color: "var(--text-3)" }}>
                      {candidate.tier === "unverified" ? "unverified" : "ruled out"}
                    </span>
                  </div>
                  {candidate.cut_reasons.map((reason, index) => (
                    <p
                      key={index}
                      className="mt-1 text-[13px]"
                      style={{ color: reason.kind === "unknown" ? "var(--warn)" : "var(--text-3)" }}
                    >
                      {reason.detail}
                    </p>
                  ))}
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      ) : null}

      <footer className="space-y-4">
        <div className="divider" />
        <Note>
          Ranked by {result.alternates?.voters?.length ?? state.participants.length} of {state.participants.length}.
          {result.alternates?.non_voters?.length
            ? ` ${result.alternates.non_voters.join(", ")} didn't rank, so nothing was assumed on their behalf.`
            : ""}
        </Note>
        <div className="flex items-start gap-2.5">
          <Alert size={17} className="mt-0.5 shrink-0" style={{ color: "var(--text-3)" }} />
          <Note>
            Hangry never says a place is safe — only that nothing in the listed data conflicts. Check with the
            restaurant if it matters.
          </Note>
        </div>
        <a className="btn btn-secondary" href="/">
          Start another
        </a>
      </footer>
    </main>
  );
}

function Rule({
  label,
  value,
  note,
  tone = "muted",
}: {
  label: string;
  value?: string;
  note?: string;
  tone?: "muted" | "danger" | "brand";
}) {
  if (!value) return null;
  const colour = { muted: "var(--text-3)", danger: "var(--danger)", brand: "var(--brand)" }[tone];
  return (
    <div className="flex items-start justify-between gap-4 border-t py-3" style={{ borderColor: "var(--border)" }}>
      <dt className="shrink-0 pt-0.5 text-[13px]" style={{ color: "var(--text-3)" }}>
        {label}
      </dt>
      <dd className="min-w-0 text-right">
        <span className="block text-[15px] font-semibold">{value}</span>
        {note ? (
          <span className="mt-0.5 block text-[13px]" style={{ color: colour }}>
            {note}
          </span>
        ) : null}
      </dd>
    </div>
  );
}
