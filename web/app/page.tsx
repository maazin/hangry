"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ConstraintForm } from "@/components/ConstraintForm";
import { Logo } from "@/components/Logo";
import { ArrowRight, Check, Users } from "@/components/icons";
import { api, listGroups, rememberGroup, writeToken, type JoinPayload } from "@/lib/api";
import { ApiError } from "@/lib/types";

const PROMISES = ["No signup", "No download", "One link"];

export default function CreatePage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [groupName, setGroupName] = useState("");
  const [mine, setMine] = useState<{ slug: string; name: string }[]>([]);

  // localStorage is client-only, so this can't be initial state without
  // tripping hydration.
  useEffect(() => setMine(listGroups()), []);

  async function create(payload: JoinPayload) {
    setBusy(true);
    setError(null);
    try {
      const group = await api.createGroup(groupName.trim() || "Dinner", payload);
      writeToken(group.slug, group.token);
      rememberGroup(group.slug, groupName.trim() || "Dinner");
      router.push(`/g/${group.slug}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Couldn't start a group. Try again.");
      setBusy(false);
    }
  }

  return (
    <main>
      <Logo />

      {mine.length > 0 ? (
        <section className="mb-8">
          <h2 className="label">Your groups</h2>
          <ul className="card divide-y overflow-hidden">
            {mine.map((group) => (
              <li key={group.slug} style={{ borderColor: "var(--border)" }}>
                <a className="flex items-center gap-3 px-4 py-3.5" href={`/g/${group.slug}`}>
                  <Users size={18} style={{ color: "var(--brand)" }} />
                  <span className="min-w-0 flex-1 truncate text-[15px] font-semibold">{group.name}</span>
                  <ArrowRight size={17} style={{ color: "var(--text-3)" }} />
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

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

      <ConstraintForm
        mode="join"
        busy={busy}
        error={error}
        submitLabel="Create the group"
        onSubmit={create}
        prelude={
          <div>
            <label className="label" htmlFor="group-name">
              What&apos;s the group?
            </label>
            <input
              id="group-name"
              className="field"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              placeholder="Thursday dinner"
              maxLength={60}
            />
            <p className="mt-2 text-[13px]" style={{ color: "var(--text-3)" }}>
              You&apos;ll get one link to share. Everyone says what they can&apos;t eat once, and it&apos;s remembered
              for every meal after.
            </p>
          </div>
        }
      />
    </main>
  );
}
