"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ConstraintForm } from "@/components/ConstraintForm";
import { Wordmark } from "@/components/ui";
import { api, writeToken, type JoinPayload } from "@/lib/api";
import { ApiError } from "@/lib/types";

export default function CreatePage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function create(payload: JoinPayload, radiusM: number) {
    setBusy(true);
    setError(null);
    try {
      const session = await api.createSession(payload, radiusM);
      writeToken(session.slug, session.token);
      router.push(`/s/${session.slug}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't start a session. Try again.");
      setBusy(false);
    }
  }

  return (
    <main>
      <Wordmark tagline="Six people, one link, dinner sorted." />

      <div className="card mb-6">
        <p className="text-sm leading-relaxed" style={{ color: "var(--muted)" }}>
          Most group apps pick whatever the most people vaguely wanted, which is how the one person who can&apos;t eat
          gluten ends up ordering a side salad. Hangry picks the option that costs the group the least — and shows you
          what the popular answer would have cost instead.
        </p>
      </div>

      <ConstraintForm mode="create" busy={busy} error={error} onSubmit={create} />
    </main>
  );
}
