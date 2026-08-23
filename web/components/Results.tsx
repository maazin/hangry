"use client";

import { useState } from "react";

import { metres } from "@/lib/constraints";
import type { SessionState } from "@/lib/types";
import { Masthead } from "./Logo";
import { Alert, ArrowRight } from "./icons";
import { Caution, Note } from "./ui";

/*
 * A flat ranked list brings back the paralysis this product exists to end, so
 * the winner gets a panel of its own and everything under it carries what it
 * costs and whom. Three by default, with the tail available and out of the way.
 */
export function Results({ state }: { state: SessionState }) {
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
      <Masthead context="Settled." />

      <section className="surface mb-4 p-6" style={{ borderColor: "var(--brand)" }}>
        <p className="eyebrow" style={{ color: "var(--brand)" }}>
          Go here
        </p>
        <h1 className="font-serif text-title-1 leading-[1.06]">{winner.name}</h1>
        <p className="mt-2 text-subhead" style={{ color: "var(--ink-3)" }}>
          {[winner.cuisine.slice(0, 3).join(", "), metres(winner.distance_m)].filter(Boolean).join(", ")}
        </p>

        <div className="rule my-5" />

        <p className="leading-relaxed">{winner.annotation}</p>

        {/* The winner can be a place the data could not verify. Saying so on
            the headline panel is what separates a tool an allergic person
            trusts from one they abandon. */}
        {winnerUnverified ? (
          <div className="mt-5">
            <Caution title="Not verified, call ahead">
              <ul className="space-y-1">
                {winnerCandidate?.cut_reasons.map((reason, index) => (
                  <li key={index}>{reason.detail}</li>
                ))}
              </ul>
            </Caution>
          </div>
        ) : null}

        <a
          className="btn btn-primary mt-6"
          href={mapsUrl(winner.lat ?? 0, winner.lon ?? 0, winner.name)}
          target="_blank"
          rel="noreferrer"
        >
          Open in maps
          <ArrowRight size={18} />
        </a>
      </section>

      {runnersUp.length > 0 ? (
        <section className="mb-4 space-y-2">
          {[...runnersUp, ...(showRest ? tail : [])].map((option, index) => (
            <article key={option.candidate_id} className="surface p-4">
              <div className="flex items-baseline gap-3">
                <span className="font-serif text-title-3 tabular-nums" style={{ color: "var(--ink-3)" }}>
                  {index + 2}
                </span>
                <h2 className="font-medium">{option.name}</h2>
              </div>
              <p className="mt-1 pl-8 text-subhead leading-relaxed" style={{ color: "var(--ink-2)" }}>
                {option.annotation}
              </p>
            </article>
          ))}

          {tail.length > 0 && !showRest ? (
            <button className="btn btn-quiet" onClick={() => setShowRest(true)}>
              Show the other {tail.length}
            </button>
          ) : null}
        </section>
      ) : null}

      {/* Showing the group what the popular answer would have cost is the
          fairness argument and the shareable moment at once. */}
      {comparison ? (
        <section className="surface mb-4 p-5">
          <p className="font-serif text-title-3 leading-snug">{comparison.headline}</p>

          <dl className="mt-5">
            <Rule
              label="Straight majority vote"
              value={comparison.utilitarian?.name}
              note={
                comparison.utilitarian?.excludes?.length
                  ? `Leaves out ${comparison.utilitarian.excludes.join(", ")}`
                  : "Nobody left out"
              }
              tone={comparison.utilitarian?.excludes?.length ? "danger" : "muted"}
            />
            <Rule
              label="Safest for everyone"
              value={comparison.maximin?.name}
              note="Nobody's last choice, nobody's first either"
            />
            <Rule
              label="Hangry's answer"
              value={comparison.minimax_regret?.name}
              note="The least anyone gives up"
              tone="brand"
            />
          </dl>

          <div className="mt-5">
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
            <Caution key={index}>{advisory.detail}</Caution>
          ))}
        </div>
      ) : null}

      {eliminated.length + unverified.length > 0 ? (
        <section className="mb-8">
          <button className="btn btn-secondary" onClick={() => setShowCuts((v) => !v)} aria-expanded={showCuts}>
            {showCuts ? "Hide" : `Why ${eliminated.length + unverified.length} places did not make it`}
          </button>

          {showCuts ? (
            <ul className="mt-3 space-y-2">
              {[...unverified, ...eliminated].map((candidate) => (
                <li key={candidate.id} className="surface p-4">
                  <div className="flex items-baseline justify-between gap-3">
                    <p className="font-medium">{candidate.name}</p>
                    <span
                      className={`tag shrink-0 ${candidate.tier === "unverified" ? "tag-caution" : ""}`}
                      style={
                        candidate.tier === "unverified"
                          ? undefined
                          : { background: "var(--surface-2)", color: "var(--ink-3)" }
                      }
                    >
                      {candidate.tier === "unverified" ? "Unverified" : "Ruled out"}
                    </span>
                  </div>
                  {candidate.cut_reasons.map((reason, index) => (
                    <p
                      key={index}
                      className="mt-1 text-footnote"
                      style={{ color: reason.kind === "unknown" ? "var(--caution)" : "var(--ink-3)" }}
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

      <footer className="space-y-5">
        <div className="rule" />
        <Note>
          Ranked by {result.alternates?.voters?.length ?? state.participants.length} of {state.participants.length}.
          {result.alternates?.non_voters?.length
            ? ` ${result.alternates.non_voters.join(", ")} did not rank, so nothing was assumed on their behalf.`
            : ""}
        </Note>
        <div className="flex items-start gap-3">
          <Alert size={17} className="mt-0.5 shrink-0" style={{ color: "var(--ink-3)" }} />
          <Note>
            Hangry never calls a place safe. It reports only that nothing in the listed data conflicts. Ask the
            restaurant if it matters.
          </Note>
        </div>
        {state.group_slug ? (
          <a className="btn btn-secondary" href={`/g/${state.group_slug}`}>
            Back to the group
          </a>
        ) : (
          <a className="btn btn-secondary" href="/">
            Start another
          </a>
        )}
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
  const colour = { muted: "var(--ink-3)", danger: "var(--danger)", brand: "var(--brand)" }[tone];
  return (
    <div
      className="flex items-start justify-between gap-4 py-3"
      style={{ borderTop: "1px solid var(--hairline)" }}
    >
      <dt className="shrink-0 pt-0.5 text-footnote" style={{ color: "var(--ink-3)" }}>
        {label}
      </dt>
      <dd className="min-w-0 text-right">
        <span className="block font-medium">{value}</span>
        {note ? (
          <span className="mt-0.5 block text-footnote" style={{ color: colour }}>
            {note}
          </span>
        ) : null}
      </dd>
    </div>
  );
}
