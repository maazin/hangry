"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, readToken, writeToken, type JoinPayload } from "@/lib/api";
import { ApiError, type SessionState } from "@/lib/types";
import { ConstraintForm } from "./ConstraintForm";
import { Lobby } from "./Lobby";
import { Logo } from "./Logo";
import { RankingList } from "./RankingList";
import { Results } from "./Results";
import { ErrorNote, Note, Progress, Skeleton, Stopped } from "./ui";

const POLL_MS = 3000;

export function SessionView({ slug }: { slug: string }) {
  const [state, setState] = useState<SessionState | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [fatal, setFatal] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const tokenRef = useRef<string | null>(null);

  useEffect(() => {
    const stored = readToken(slug);
    tokenRef.current = stored;
    setToken(stored);
  }, [slug]);

  const refresh = useCallback(async () => {
    try {
      setState(await api.getSession(slug, tokenRef.current));
      setFatal(null);
    } catch (e) {
      if (e instanceof ApiError && (e.status === 404 || e.status === 410)) setFatal(e);
    }
  }, [slug]);

  useEffect(() => {
    void refresh();
  }, [refresh, token]);

  /**
   * Polling, replaced by WebSockets in a later phase. Watching other people
   * land is what creates the urgency to finish, and polling gets most of
   * that for none of the infrastructure.
   */
  useEffect(() => {
    if (fatal || state?.status === "decided") return;
    const id = setInterval(() => void refresh(), POLL_MS);
    return () => clearInterval(id);
  }, [fatal, refresh, state?.status]);

  async function join(payload: JoinPayload) {
    setBusy(true);
    setError(null);
    try {
      const joined = await api.join(slug, payload);
      writeToken(slug, joined.token);
      tokenRef.current = joined.token;
      setToken(joined.token);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't join. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await api.start(slug, token);
      await refresh();
    } catch (e) {
      if (e instanceof ApiError && e.code === "no_feasible_candidates") {
        const who = e.bindingConstraints
          .slice(0, 2)
          .map((b) => `${b.participant}'s ${b.label}`)
          .join(" and ");
        setError(who ? `Nothing nearby works for ${who}. Try a wider search.` : e.message);
      } else {
        setError(e instanceof ApiError ? e.message : "Couldn't start. Try again.");
      }
    } finally {
      setBusy(false);
    }
  }

  async function submitRanking(orderedIds: string[]) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await api.submitRanking(slug, token, orderedIds);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't send your ranking. Try again.");
    } finally {
      setBusy(false);
    }
  }

  async function forceSolve() {
    if (!token) return;
    setBusy(true);
    try {
      await api.solve(slug, token);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't get a result yet.");
    } finally {
      setBusy(false);
    }
  }

  // ---- terminal states -----------------------------------------------

  if (fatal?.status === 410) {
    return (
      <main>
        <Logo />
        <Stopped
          title="This one's expired"
          action={
            <a className="btn btn-primary" href="/">
              Start a new session
            </a>
          }
        >
          Sessions last 24 hours and then delete themselves. Nothing to recover — start a fresh one.
        </Stopped>
      </main>
    );
  }

  if (fatal?.status === 404) {
    return (
      <main>
        <Logo />
        <Stopped
          title="No session here"
          action={
            <a className="btn btn-secondary" href="/">
              Start your own
            </a>
          }
        >
          That link doesn&apos;t match anything. Check you copied all of it.
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

  // ---- the flow ------------------------------------------------------

  // The server resolves identity from the token; the client never guesses.
  const me = state.you;
  const joined = Boolean(me);
  const isCreator = Boolean(me?.is_creator);

  if (state.status === "decided" && state.result) {
    return <Results slug={slug} state={state} />;
  }

  if (!joined) {
    if (state.status !== "collecting") {
      // A round belongs to a group, so the fix is almost always "open the
      // group link on this device", not "start over".
      if (state.group_slug) {
        return (
          <main>
            <Logo />
            <Stopped
              title="You're not in this round"
              action={
                <a className="btn btn-primary" href={`/g/${state.group_slug}`}>
                  Open the group
                </a>
              }
            >
              This round is already going. If you&apos;re in the group, open the group link on this device and
              you&apos;ll be able to rank — if you&apos;re not, that&apos;s where you join.
            </Stopped>
          </main>
        );
      }

      return (
        <main>
          <Logo />
          <Stopped
            title="They've already started"
            action={
              <a className="btn btn-secondary" href="/">
                Start one
              </a>
            }
          >
            This group locked in their options before you opened the link. Joining now would change what everyone else
            already ranked, so you&apos;ll need a new session.
          </Stopped>
        </main>
      );
    }

    return (
      <main>
        <Logo
          tagline={
            state.participants.length === 1
              ? "One person's waiting on you. Takes about 30 seconds."
              : `${state.participants.length} already in. Takes about 30 seconds.`
          }
        />
        <ConstraintForm mode="join" busy={busy} error={error} onSubmit={(payload) => join(payload)} />
      </main>
    );
  }

  if (state.status === "collecting") {
    return (
      <Lobby
        slug={slug}
        state={state}
        busy={busy}
        error={error}
        canStart={isCreator}
        onStart={start}
      />
    );
  }

  const rankable = state.candidates.filter((c) => c.locked);

  // Comes from the server, so a reload doesn't ask for a ranking twice.
  if (me?.has_ranked) {
    const waiting = state.participants.length - state.submitted;
    return (
      <main>
        <Logo tagline="Sent. Waiting on the rest." />
        <div className="card p-5">
          <p className="text-[22px] font-bold tabular-nums">
            {state.submitted} of {state.participants.length} have ranked
          </p>
          <div className="mt-4">
            <Progress value={state.submitted} max={state.participants.length} />
          </div>
          <div className="mt-4">
            <Note>
              {waiting > 0
                ? "The result appears here the moment the last person finishes."
                : "Working out the fairest option…"}
            </Note>
          </div>

          {isCreator && state.submitted > 0 && waiting > 0 ? (
            <button className="btn btn-secondary mt-5" onClick={forceSolve} disabled={busy}>
              Decide without the stragglers
            </button>
          ) : null}

          {error ? (
            <div className="mt-4">
              <ErrorNote>{error}</ErrorNote>
            </div>
          ) : null}
        </div>
      </main>
    );
  }

  return (
    <RankingList
      state={state}
      candidates={rankable}
      busy={busy}
      error={error}
      onSubmit={submitRanking}
    />
  );
}
