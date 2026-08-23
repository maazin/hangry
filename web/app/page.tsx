"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { ConstraintForm } from "@/components/ConstraintForm";
import { Masthead } from "@/components/Logo";
import { ArrowRight, People } from "@/components/icons";
import { api, listGroups, rememberGroup, writeToken, type JoinPayload } from "@/lib/api";
import { ApiError } from "@/lib/types";

export default function CreatePage() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [groupName, setGroupName] = useState("");
  const [mine, setMine] = useState<{ slug: string; name: string }[]>([]);

  // localStorage is client only, so reading it during render would break
  // hydration.
  useEffect(() => setMine(listGroups()), []);

  async function create(payload: JoinPayload) {
    setBusy(true);
    setError(null);
    try {
      const name = groupName.trim() || "Dinner";
      const group = await api.createGroup(name, payload);
      writeToken(group.slug, group.token);
      rememberGroup(group.slug, name);
      router.push(`/g/${group.slug}`);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not start a group. Try again.");
      setBusy(false);
    }
  }

  return (
    <main>
      <Masthead />

      {mine.length > 0 ? (
        <section className="mb-10">
          <h2 className="eyebrow">Your groups</h2>
          <ul className="surface overflow-hidden">
            {mine.map((group, index) => (
              <li key={group.slug} style={index > 0 ? { borderTop: "1px solid var(--hairline)" } : undefined}>
                <a className="flex items-center gap-3 px-4 py-4" href={`/g/${group.slug}`}>
                  <People size={18} style={{ color: "var(--brand)" }} />
                  <span className="min-w-0 flex-1 truncate font-medium">{group.name}</span>
                  <ArrowRight size={17} style={{ color: "var(--ink-3)" }} />
                </a>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section className="mb-9">
        <h1 className="font-serif text-display leading-[1.04]">
          Settle where the group eats.
        </h1>
        <p className="mt-5 leading-relaxed" style={{ color: "var(--ink-2)" }}>
          Most apps pick whatever the most people vaguely wanted, which is how the one person who cannot eat gluten
          ends up with a side salad. Hangry picks the option that costs the group least, then shows you what the
          popular answer would have cost.
        </p>
        <p className="mt-4 text-subhead" style={{ color: "var(--ink-3)" }}>
          No signup. No download. One link that keeps working.
        </p>
      </section>

      <div className="rule mb-9" />

      <ConstraintForm
        mode="join"
        busy={busy}
        error={error}
        submitLabel="Create the group"
        onSubmit={create}
        prelude={
          <div>
            <label className="eyebrow" htmlFor="group-name">
              What is the group?
            </label>
            <input
              id="group-name"
              className="field"
              value={groupName}
              onChange={(e) => setGroupName(e.target.value)}
              placeholder="Thursday dinner"
              maxLength={60}
            />
            <p className="mt-2 text-footnote" style={{ color: "var(--ink-3)" }}>
              You get one link to share. Everyone says what they cannot eat once, and it is remembered for every
              meal after.
            </p>
          </div>
        }
      />
    </main>
  );
}
