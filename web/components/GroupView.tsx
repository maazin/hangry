"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { adoptTokenForRound, api, readToken, rememberGroup, writeToken, type JoinPayload } from "@/lib/api";
import { DIET_CHIPS, RADIUS_OPTIONS } from "@/lib/constraints";
import { ApiError, type GroupState } from "@/lib/types";
import { ConstraintForm } from "./ConstraintForm";
import { Logo } from "./Logo";
import { ArrowRight, Check, Share, Users } from "./icons";
import { Callout, ErrorNote, Note, Skeleton, Stopped } from "./ui";

const POLL_MS = 4000;

const dietLabel = (key: string) => DIET_CHIPS.find((c) => c.key === key)?.label ?? key;

const initials = (name: string) =>
  name
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();

/**
 * The group page: a roster, an invite link, and a button that starts dinner.
 *
 * This is where the product stops being a one-shot demo. Members and their
 * dietary constraints live here between meals, so round two costs two taps
 * instead of six people re-typing everything.
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

  // Watching people arrive is what makes a group feel live enough to start.
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
      setError(e instanceof ApiError ? e.message : "Couldn't join. Try again.");
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
          text: "Join the group — we use this to pick where to eat:",
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

  async function startRound() {
    const token = tokenRef.current;
    if (!token || !state) return;

    setBusy(true);
    setError(null);
    try {
      const everyone = state.members.length === coming.length || !picking;
      const round = await api.startRound(slug, token, everyone ? null : coming, radius);
      writeToken(round.slug, token);
      router.push(`/s/${round.slug}`);
    } catch (e) {
      if (e instanceof ApiError && e.code === "round_in_progress") {
        await refresh();
        setError("A round is already going — jump into it below.");
      } else if (e instanceof ApiError && e.code === "no_feasible_candidates") {
        setError(e.message);
      } else {
        setError(e instanceof ApiError ? e.message : "Couldn't start a round. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  if (fatal?.status === 404) {
    return (
      <main>
        <Logo />
        <Stopped
          title="No group here"
          action={
            <a className="btn btn-secondary" href="/">
              Start your own
            </a>
          }
        >
          That link doesn&apos;t match any group. Check you copied all of it.
        </Stopped>
      </main>
    );
  }

  if (!state) {
    return (
      <main>
        <Logo />
        <Skeleton rows={3} />
      </main>
    );
  }

  // ---- not a member yet ------------------------------------------------

  if (!state.you) {
    return (
      <main>
        <Logo tagline={`${state.name} · ${state.members.length} ${state.members.length === 1 ? "person" : "people"} so far`} />
        <div className="mb-6">
          <Note>
            Tell them what you can&apos;t eat once, and you won&apos;t be asked again — every meal this group picks
            will already know.
          </Note>
        </div>
        <ConstraintForm mode="join" busy={busy} error={error} onSubmit={(payload) => join(payload)} />
      </main>
    );
  }

  // ---- a member ---------------------------------------------------------

  const active = state.active_round;
  const past = state.rounds.filter((r) => r.slug !== active?.slug && r.status === "decided");
  const selected = picking ? coming : state.members.map((m) => m.id);

  return (
    <main>
      <Logo tagline={state.name} />

      {active ? (
        <section className="card mb-4 p-5" style={{ borderColor: "var(--brand)" }}>
          <p className="badge badge-brand mb-2">Round in progress</p>
          <p className="text-[17px] font-semibold">
            {active.submitted} of {active.participants} have ranked
          </p>
          <a className="btn btn-primary mt-4" href={`/s/${active.slug}`}>
            {active.submitted > 0 ? "Go to the round" : "Rank yours"}
            <ArrowRight size={18} />
          </a>
        </section>
      ) : (
        <section className="card mb-4 p-5">
          <p className="text-[17px] font-semibold">Hungry?</p>
          <div className="mt-1">
            <Note>
              Everyone&apos;s requirements are already saved. Starting a round goes straight to ranking — nobody has to
              fill anything in.
            </Note>
          </div>

          {picking ? (
            <div className="mt-4">
              <span className="label">Who&apos;s eating?</span>
              <div className="flex flex-wrap gap-2">
                {state.members.map((member) => {
                  const on = coming.includes(member.id);
                  return (
                    <button
                      key={member.id}
                      type="button"
                      aria-pressed={on}
                      className={`chip ${on ? "chip-on" : ""}`}
                      onClick={() =>
                        setComing((c) => (on ? c.filter((id) => id !== member.id) : [...c, member.id]))
                      }
                    >
                      {on ? <Check size={16} className="-ml-0.5 mr-1.5" /> : null}
                      {member.display_name}
                    </button>
                  );
                })}
              </div>
              <div className="mt-3">
                <Note>
                  Anyone left out won&apos;t have their dietary needs applied — which is right if they aren&apos;t
                  coming, and wrong if they are.
                </Note>
              </div>

              <label className="label mt-4" htmlFor="radius">
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
            className="btn btn-primary mt-4"
            onClick={startRound}
            disabled={busy || (picking && selected.length === 0)}
          >
            {busy ? "Finding places…" : picking ? `Start with ${selected.length}` : "Start a round"}
          </button>

          {!picking ? (
            <button className="btn btn-quiet mt-1" onClick={() => { setPicking(true); setComing(state.members.map((m) => m.id)); }}>
              Not everyone&apos;s coming
            </button>
          ) : (
            <button className="btn btn-quiet mt-1" onClick={() => setPicking(false)}>
              Never mind, everyone&apos;s in
            </button>
          )}

          {error ? (
            <div className="mt-4">
              <ErrorNote>{error}</ErrorNote>
            </div>
          ) : null}
        </section>
      )}

      <section className="card mb-4 overflow-hidden">
        <div className="flex items-center justify-between px-4 py-3.5">
          <span className="label !mb-0">The group</span>
          <span className="flex items-center gap-1.5 text-[14px] font-semibold" style={{ color: "var(--text-2)" }}>
            <Users size={17} />
            {state.members.length}
          </span>
        </div>

        <ul>
          {state.members.map((member) => {
            const diets = member.hard_constraints?.diets ?? [];
            const isMe = member.id === state.you?.member_id;
            return (
              <li key={member.id} className="flex items-center gap-3 border-t px-4 py-3" style={{ borderColor: "var(--border)" }}>
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-[13px] font-bold"
                  style={{ background: "var(--brand-tint)", color: "var(--brand)" }}
                >
                  {initials(member.display_name)}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[15px] font-semibold">
                    {member.display_name}
                    {isMe ? (
                      <span className="ml-2 text-[12px] font-medium" style={{ color: "var(--text-3)" }}>
                        you
                      </span>
                    ) : null}
                  </span>
                  <span
                    className="block truncate text-[13px]"
                    style={{ color: diets.length ? "var(--warn)" : "var(--text-3)" }}
                  >
                    {diets.length ? diets.map(dietLabel).join(" · ") : "No restrictions"}
                  </span>
                </span>
              </li>
            );
          })}
        </ul>

        <div className="border-t p-4" style={{ borderColor: "var(--border)" }}>
          <button className="btn btn-secondary" onClick={share}>
            {copied ? <Check size={19} /> : <Share size={19} />}
            {copied ? "Link copied" : "Invite someone"}
          </button>
          <div className="mt-3">
            <Note>Anyone with the link can join — you don&apos;t have to be the one who started it.</Note>
          </div>
        </div>
      </section>

      {state.advisories.length > 0 ? (
        <div className="mb-4 space-y-3">
          {state.advisories.map((advisory, index) => (
            <Callout key={index} title="Worth knowing">
              {advisory.detail}
            </Callout>
          ))}
        </div>
      ) : null}

      {past.length > 0 ? (
        <section className="mb-6">
          <h2 className="label">Where you&apos;ve been</h2>
          <ul className="card divide-y overflow-hidden">
            {past.map((round) => (
              <li key={round.slug} style={{ borderColor: "var(--border)" }}>
                <a className="flex items-center gap-3 px-4 py-3" href={`/s/${round.slug}`}>
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[15px] font-semibold">{round.winner ?? "Decided"}</span>
                    <span className="block text-[13px]" style={{ color: "var(--text-3)" }}>
                      {new Date(round.created_at).toLocaleDateString(undefined, { month: "short", day: "numeric" })} ·{" "}
                      {round.participants} eating
                    </span>
                  </span>
                  <ArrowRight size={17} style={{ color: "var(--text-3)" }} />
                </a>
              </li>
            ))}
          </ul>
          <div className="mt-2">
            <Note>Past rounds stay readable for 24 hours, then the round expires. The group doesn&apos;t.</Note>
          </div>
        </section>
      ) : null}
    </main>
  );
}
