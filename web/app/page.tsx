"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { ConstraintForm } from "@/components/ConstraintForm";
import { Logo } from "@/components/Logo";
import { Check } from "@/components/icons";
import { api, writeToken, type JoinPayload } from "@/lib/api";
import { ApiError } from "@/lib/types";

const PROMISES = ["No signup", "No download", "One link"];

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
      <Logo />

      <section className="mb-8">
        <h1 className="text-[34px] font-bold leading-[1.08]">
          Settle where
          <br />
          the group eats.
        </h1>
        <p className="mt-3.5 text-[16px] leading-relaxed" style={{ color: "var(--text-2)" }}>
          Most apps pick whatever the most people vaguely wanted — which is how the one person who can&apos;t eat
          gluten ends up with a side salad. Hangry picks what costs the group the least, and shows you what the
          popular answer would have cost instead.
        </p>

        <ul className="mt-5 flex flex-wrap gap-x-5 gap-y-2">
          {PROMISES.map((promise) => (
            <li key={promise} className="flex items-center gap-1.5 text-[14px] font-medium">
              <Check size={17} style={{ color: "var(--brand)" }} />
              {promise}
            </li>
          ))}
        </ul>
      </section>

      <div className="divider mb-8" />

      <ConstraintForm mode="create" busy={busy} error={error} onSubmit={create} />
    </main>
  );
}
