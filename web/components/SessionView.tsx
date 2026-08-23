"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, readToken, writeToken, type JoinPayload } from "@/lib/api";
import { ApiError, type SessionState } from "@/lib/types";
import { ConstraintForm } from "./ConstraintForm";
import { Lobby } from "./Lobby";
import { Masthead } from "./Logo";
import { RankingList } from "./RankingList";
import { Results } from "./Results";
import { ErrorNote, Note, Progress, Stopped, Waiting } from "./ui";

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

  /*
   * Polling, which a later phase replaces with WebSockets. Watching other
   * people land is what creates the urgency to finish, and polling gets most
   * of that for none of the infrastructure.
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
      setError(e instanceof ApiError ? e.message : "Could not join. Try again.");
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
        setError(e instanceof ApiError ? e.message : "Could not start. Try again.");
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
      setError(e instanceof ApiError ? e.message : "Could not send your ranking. Try again.");
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
      setError(e instanceof ApiError ? e.message : "Could not get a result yet.");
    } finally {
      setBusy(false);
    }
  }

  if (fatal?.status === 410) {
    return (
      <main>
        <Masthead />
        <Stopped
          title="This one has expired"
          action={
            <a className="btn btn-primary" href="/">
              Start a new one
            </a>
          }
        >
          Rounds last 24 hours and then delete themselves. Nothing to recover.
        </Stopped>
      </main>
    );
  }

  if (fatal?.status === 404) {
    return (
      <main>
        <Masthead />
        <Stopped
          title="Nothing here"
          action={
            <a className="btn btn-secondary" href="/">
              Start your own
            </a>
          }
        >
          That link does not match anything. Check you copied all of it.
        </Stopped>
      </main>
    );
  }

  if (!state) {
    return (
      <main>
        <Masthead />
        <Waiting label="Loading the round" />
      </main>
    );
  }

  // The server resolves identity from the token, so the client never guesses.
  const me = state.you;
  const joined = Boolean(me);
  const isCreator = Boolean(me?.is_creator);

  if (state.status === "decided" && state.result) {
    return <Results state={state} />;
  }

  if (!joined) {
    if (state.status !== "collecting") {
      // A round belongs to a group, so the fix is almost always to open the
      // group link on this device.
      if (state.group_slug) {
        return (
          <main>
            <Masthead />
            <Stopped
              title="You are not in this round"
              action={
                <a className="btn btn-primary" href={`/g/${state.group_slug}`}>
                  Open the group
                </a>
              }
            >
              This round is already going. If you are in the group, open the group link on this device and you will be
              able to rank. If you are new, that is where you join.
            </Stopped>
          </main>
        );
      }

      return (
        <main>
          <Masthead />
          <Stopped
            title="They have already started"
            action={
              <a className="btn btn-secondary" href="/">
                Start one
              </a>
            }
          >
            This group locked in their options before you opened the link. Joining now would change what everyone else
            already ranked, so you will need a new session.
          </Stopped>
        </main>
      );
    }

    return (
      <main>
        <Masthead
          context={
            state.participants.length === 1
              ? "One person is waiting on you. About thirty seconds."
              : `${state.participants.length} already in. About thirty seconds.`
          }
        />
        <ConstraintForm mode="join" busy={busy} error={error} onSubmit={(payload) => join(payload)} />
      </main>
    );
  }

  if (state.status === "collecting") {
    return <Lobby slug={slug} state={state} busy={busy} error={error} canStart={isCreator} onStart={start} />;
  }

  const rankable = state.candidates.filter((c) => c.locked);

  // Comes from the server, so a reload does not ask for a ranking twice.
  if (me?.has_ranked) {
    const waiting = state.participants.length - state.submitted;
    return (
      <main>
        <Masthead context="Sent. Waiting on the rest." />
        <section className="surface p-5">
          <p className="font-serif text-title-2 tabular-nums">
            {state.submitted} of {state.participants.length} have ranked
          </p>
          <div className="mt-5">
            <Progress value={state.submitted} max={state.participants.length} label="Rankings submitted" />
          </div>
          <div className="mt-5">
            <Note>
              {waiting > 0
                ? "The result appears here the moment the last person finishes."
                : "Working out the fairest option."}
            </Note>
          </div>

          {isCreator && state.submitted > 0 && waiting > 0 ? (
            <button className="btn btn-secondary mt-6" onClick={forceSolve} disabled={busy}>
              Decide without the stragglers
            </button>
          ) : null}

          {error ? (
            <div className="mt-5">
              <ErrorNote>{error}</ErrorNote>
            </div>
          ) : null}
        </section>
      </main>
    );
  }

  return <RankingList state={state} candidates={rankable} busy={busy} error={error} onSubmit={submitRanking} />;
}
