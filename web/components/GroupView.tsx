"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { adoptTokenForRound, api, readToken, rememberGroup, writeToken, type JoinPayload } from "@/lib/api";
import { DIET_CHIPS, RADIUS_OPTIONS } from "@/lib/constraints";
import { ApiError, type GroupState } from "@/lib/types";
import { ConstraintForm } from "./ConstraintForm";
import { Masthead } from "./Logo";
import { ArrowRight, People, Share } from "./icons";
import { Caution, ErrorNote, Note, Stopped, Waiting } from "./ui";

const POLL_MS = 4000;

const dietLabel = (key: string) => DIET_CHIPS.find((c) => c.key === key)?.label ?? key;

const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

/*
 * The group page. A roster, an invite link, and a button that starts dinner.
 *
 * Everything the group knows about its members lives here between meals,
 * which is what makes the fifth dinner cost two taps.
 */
export function GroupView({ slug }: { slug: string }) {
  const router = useRouter();
  const [state, setState] = useState<GroupState | null>(null);
  const [fatal, setFatal] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [picking, setPicking] = useState(false);
  const [coming, setComing] = useState<string[]>([]);
  const [radius, setRadius] = useState(5000);
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    tokenRef.current = readToken(slug);
  }, [slug]);

  const refresh = useCallback(async () => {
    try {
      const next = await api.getGroup(slug, tokenRef.current);
      setState(next);
      setFatal(null);
      if (next.you) rememberGroup(next.slug, next.name);
      // A member's group token is their round token, so hand it forward.
      if (next.active_round) adoptTokenForRound(slug, next.active_round.slug);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setFatal(e);
    }
  }, [slug]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  // Watching people arrive is what makes a group feel worth starting.
  useEffect(() => {
    if (fatal) return;
    const id = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(id);
  }, [fatal, refresh]);

  async function join(payload: JoinPayload) {
    setBusy(true);
    setError(null);
    try {
      const joined = await api.joinGroup(slug, payload);
      writeToken(slug, joined.token);
      tokenRef.current = joined.token;
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not join. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function share() {
    const link = `${window.location.origin}/g/${slug}`;
    if (navigator.share) {
      try {
        await navigator.share({
          title: state?.name ?? "Hangry",
          text: "Join the group. We use this to pick where to eat.",
          url: link,
        });
        return;
      } catch {
        /* dismissed, fall through to copy */
      }
    }
    await navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  async function startRound() {
    const token = tokenRef.current;
    if (!token || !state) return;

    setBusy(true);
    setError(null);
    try {
      const everyone = !picking || state.members.length === coming.length;
      const round = await api.startRound(slug, token, everyone ? null : coming, radius);
      writeToken(round.slug, token);
      router.push(`/s/${round.slug}`);
    } catch (e) {
      if (e instanceof ApiError && e.code === "round_in_progress") {
        await refresh();
        setError("A round is already going. Jump into it above.");
      } else {
        setError(e instanceof ApiError ? e.message : "Could not start a round. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (fatal?.status === 404) {
    return (
      <main>
        <Masthead />
        <Stopped
          title="No group here"
          action={
            <a className="btn btn-secondary" href="/">
              Start your own
            </a>
          }
        >
          That link does not match any group. Check you copied all of it.
        </Stopped>
      </main>
    );
  }

  if (!state) {
    return (
      <main>
        <Masthead />
        <Waiting label="Loading the group" />
      </main>
    );
  }

  if (!state.you) {
    return (
      <main>
        <Masthead
          context={`${state.name}. ${state.members.length} ${state.members.length === 1 ? "person" : "people"} so far.`}
        />
        <div className="mb-8">
          <Note>
            Say what you cannot eat once. Every meal this group picks from now on will already know.
          </Note>
        </div>
        <ConstraintForm mode="join" busy={busy} error={error} submitLabel="Join the group" onSubmit={(p) => join(p)} />
      </main>
    );
  }

  const active = state.active_round;
  const past = state.rounds.filter((r) => r.slug !== active?.slug && r.status === "decided");
  const selected = picking ? coming : state.members.map((m) => m.id);

  return (
    <main>
      <Masthead context={state.name} />

      {active ? (
        <section className="surface mb-4 p-5" style={{ borderColor: "var(--brand)" }}>
          <p className="tag tag-brand mb-3">Round in progress</p>
          <p className="text-title-3 font-semibold">
            {active.submitted} of {active.participants} have ranked
          </p>
          <a className="btn btn-primary mt-5" href={`/s/${active.slug}`}>
            {active.submitted > 0 ? "Go to the round" : "Rank yours"}
            <ArrowRight size={18} />
          </a>
        </section>
      ) : (
        <section className="surface mb-4 p-5">
          <h2 className="font-serif text-title-2">Hungry?</h2>
          <div className="mt-2">
            <Note>
              Everyone&apos;s requirements are already saved. Starting a round goes straight to ranking, with nothing
              for anyone to fill in.
            </Note>
          </div>

          {picking ? (
            <div className="mt-6">
              <span className="eyebrow">Who is eating?</span>
              <div className="flex flex-wrap gap-2">
                {state.members.map((member) => (
                  <button
                    key={member.id}
                    type="button"
                    aria-pressed={coming.includes(member.id)}
                    className="chip"
                    onClick={() =>
                      setComing((c) =>
                        c.includes(member.id) ? c.filter((id) => id !== member.id) : [...c, member.id],
                      )
                    }
                  >
                    {member.display_name}
                  </button>
                ))}
              </div>
              <div className="mt-3">
                <Note>
                  Anyone left out will not have their dietary needs applied, which is right if they are staying home
                  and wrong if they are coming.
                </Note>
              </div>

              <label className="eyebrow mt-6" htmlFor="radius">
                Search area
              </label>
              <select id="radius" className="field" value={radius} onChange={(e) => setRadius(Number(e.target.value))}>
                {RADIUS_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          ) : null}

          <button
            className="btn btn-primary mt-5"
            onClick={startRound}
            disabled={busy || (picking && selected.length === 0)}
          >
            {busy ? "Finding places" : picking ? `Start with ${selected.length}` : "Start a round"}
          </button>

          <button
            className="btn btn-quiet mt-1"
            onClick={() => {
              if (picking) setPicking(false);
              else {
                setPicking(true);
                setComing(state.members.map((m) => m.id));
              }
            }}
          >
            {picking ? "Everyone is coming after all" : "Not everyone is coming"}
          </button>

          {error ? (
            <div className="mt-4">
              <ErrorNote>{error}</ErrorNote>
            </div>
          ) : null}
        </section>
      )}

      <section className="surface mb-4 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="eyebrow !mb-0">The group</span>
          <span className="flex items-center gap-1.5 text-subhead font-medium" style={{ color: "var(--ink-2)" }}>
            <People size={17} />
            {state.members.length}
          </span>
        </div>

        <ul>
          {state.members.map((member) => {
            const diets = member.hard_constraints?.diets ?? [];
            const isMe = member.id === state.you?.member_id;
            return (
              <li
                key={member.id}
                className="flex items-center gap-3 px-4 py-3"
                style={{ borderTop: "1px solid var(--hairline)" }}
              >
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-s text-footnote font-semibold"
                  style={{ background: "var(--brand-wash)", color: "var(--brand)" }}
                >
                  {initials(member.display_name)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">
                    {member.display_name}
                    {isMe ? (
                      <span className="ml-2 text-footnote font-normal" style={{ color: "var(--ink-3)" }}>
                        you
                      </span>
                    ) : null}
                  </span>
                  <span
                    className="block truncate text-footnote"
                    style={{ color: diets.length ? "var(--caution)" : "var(--ink-3)" }}
                  >
                    {diets.length ? diets.map(dietLabel).join(", ") : "No restrictions"}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>

        <div className="p-4" style={{ borderTop: "1px solid var(--hairline)" }}>
          <button className="btn btn-secondary" onClick={share}>
            <Share size={18} />
            {copied ? "Link copied" : "Invite someone"}
          </button>
          <div className="mt-3">
            <Note>Anyone with the link can join. You do not have to be the person who started it.</Note>
          </div>
        </div>
      </section>

      {state.advisories.length > 0 ? (
        <div className="mb-4 space-y-3">
          {state.advisories.map((advisory, index) => (
            <Caution key={index} title="Worth knowing">
              {advisory.detail}
            </Caution>
          ))}
        </div>
      ) : null}

      {past.length > 0 ? (
        <section className="mb-6">
          <h2 className="eyebrow">Where you have been</h2>
          <ul className="surface overflow-hidden">
            {past.map((round, index) => (
              <li key={round.slug} style={index > 0 ? { borderTop: "1px solid var(--hairline)" } : undefined}>
                <a className="flex items-center gap-3 px-4 py-3.5" href={`/s/${round.slug}`}>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{round.winner ?? "Decided"}</span>
                    <span className="block text-footnote" style={{ color: "var(--ink-3)" }}>
                      {new Date(round.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })},{" "}
                      {round.participants} eating
                    </span>
                  </span>
                  <ArrowRight size={17} style={{ color: "var(--ink-3)" }} />
                </a>
              </li>
            ))}
          </ul>
          <div className="mt-3">
            <Note>A round stays readable for 24 hours, then expires. The group stays.</Note>
          </div>
        </section>
      ) : null}
    </main>
  );
}
