"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, readToken, writeToken, type JoinPayload } from "@/lib/api";
import { ApiError, type SessionState } from "@/lib/types";
import { ConstraintForm } from "./ConstraintForm";
import { Lobby } from "./Lobby";
import { RankingList } from "./RankingList";
import { Results } from "./Results";
import { ErrorNote, Note, Skeleton, Wordmark } from "./ui";

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
        <Wordmark />
        <div className="card space-y-3">
          <h2 className="text-xl font-bold">This one&apos;s expired</h2>
          <Note>Sessions last 24 hours and then delete themselves. Nothing to recover — start a fresh one.</Note>
          <a className="btn btn-primary block text-center" href="/">
            Start a new session
          </a>
        </div>
      </main>
    );
  }

  if (fatal?.status === 404) {
    return (
      <main>
        <Wordmark />
        <div className="card space-y-3">
          <h2 className="text-xl font-bold">No session here</h2>
          <Note>That link doesn&apos;t match anything. Check you copied all of it.</Note>
          <a className="btn btn-ghost block text-center" href="/">
            Start your own
          </a>
        </div>
      </main>
    );
  }

  if (!state) {
    return (
      <main>
        <Wordmark />
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
      return (
        <main>
          <Wordmark />
          <div className="card space-y-3">
            <h2 className="text-xl font-bold">They&apos;ve already started</h2>
            <Note>
              This group locked in their options before you opened the link. Joining now would change what everyone else
              already ranked, so you&apos;ll need a new session.
            </Note>
            <a className="btn btn-ghost block text-center" href="/">
              Start one
            </a>
          </div>
        </main>
      );
    }

    return (
      <main>
        <Wordmark tagline={`${state.participants.length} already in. Takes about 30 seconds.`} />
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
    return (
      <main>
        <Wordmark tagline="Sent. Waiting on the rest." />
        <div className="card space-y-3">
          <p className="text-lg font-bold">
            {state.submitted} of {state.participants.length} have ranked
          </p>
          <div className="h-2 w-full overflow-hidden rounded-full" style={{ background: "var(--surface-2)" }}>
            <div
              className="h-full rounded-full transition-all"
              style={{
                width: `${(state.submitted / Math.max(state.participants.length, 1)) * 100}%`,
                background: "var(--accent)",
              }}
            />
          </div>
          <Note>The result appears here the moment the last person finishes.</Note>
          {isCreator && state.submitted > 0 ? (
            <button className="btn btn-ghost" onClick={forceSolve} disabled={busy}>
              Decide now without the stragglers
            </button>
          ) : null}
          <ErrorNote>{error}</ErrorNote>
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
