"use client";

import { useState } from "react";

import { geocode, locate, type JoinPayload } from "@/lib/api";
import { DIET_CHIPS, DISTANCE_OPTIONS, RADIUS_OPTIONS } from "@/lib/constraints";
import { ErrorNote, Note } from "./ui";

/**
 * The joiner's entire flow. Every control here has to earn its tap — five of
 * the six people using this didn't start the session and have near-zero
 * patience for a form.
 */
export function ConstraintForm({
  mode,
  busy,
  error,
  onSubmit,
}: {
  mode: "create" | "join";
  busy: boolean;
  error: string | null;
  onSubmit: (payload: JoinPayload, radiusM: number) => void;
}) {
  const [name, setName] = useState("");
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const [placeLabel, setPlaceLabel] = useState<string | null>(null);
  const [address, setAddress] = useState("");
  const [showAddress, setShowAddress] = useState(false);
  const [locating, setLocating] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);

  const [diets, setDiets] = useState<string[]>([]);
  const [maxDistance, setMaxDistance] = useState<number>(10000);
  const [radius, setRadius] = useState<number>(5000);
  const [openNow, setOpenNow] = useState(true);

  const advisorySelected = DIET_CHIPS.filter((c) => !c.filterable && diets.includes(c.key));

  async function useMyLocation() {
    setLocating(true);
    setLocalError(null);
    try {
      const position = await locate();
      setCoords(position);
      setPlaceLabel("Using your current location");
      setShowAddress(false);
    } catch (e) {
      setLocalError((e as Error).message);
      setShowAddress(true);
    } finally {
      setLocating(false);
    }
  }

  async function useAddress() {
    if (!address.trim()) return;
    setLocating(true);
    setLocalError(null);
    try {
      const hit = await geocode(address);
      setCoords({ lat: hit.lat, lon: hit.lon });
      setPlaceLabel(hit.label);
    } catch (e) {
      setLocalError((e as Error).message);
    } finally {
      setLocating(false);
    }
  }

  function toggleDiet(key: string) {
    setDiets((current) => (current.includes(key) ? current.filter((d) => d !== key) : [...current, key]));
  }

  function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim() || !coords) return;
    onSubmit(
      {
        name: name.trim(),
        lat: coords.lat,
        lon: coords.lon,
        hard_constraints: { diets, max_distance_m: maxDistance, open_now: openNow },
      },
      radius,
    );
  }

  return (
    <form onSubmit={submit} className="space-y-5">
      <div>
        <label className="label" htmlFor="name">
          Your name
        </label>
        <input
          id="name"
          className="field"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Sam"
          maxLength={40}
          autoComplete="given-name"
          required
        />
      </div>

      <div>
        <span className="label">Where are you?</span>
        {coords ? (
          <div className="flex items-center justify-between gap-3 rounded-xl px-4 py-3" style={{ background: "var(--surface-2)" }}>
            <span className="truncate text-sm" style={{ color: "var(--ok)" }}>
              {placeLabel}
            </span>
            <button
              type="button"
              className="shrink-0 text-sm underline"
              style={{ color: "var(--muted)" }}
              onClick={() => {
                setCoords(null);
                setPlaceLabel(null);
              }}
            >
              change
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <button type="button" className="btn btn-ghost" onClick={useMyLocation} disabled={locating}>
              {locating ? "Finding you…" : "Use my location"}
            </button>

            {showAddress ? (
              <div className="flex gap-2">
                <input
                  className="field"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  placeholder="Street, city"
                  autoComplete="street-address"
                />
                <button type="button" className="btn btn-ghost !w-auto px-4" onClick={useAddress} disabled={locating}>
                  Find
                </button>
              </div>
            ) : (
              <button
                type="button"
                className="text-sm underline"
                style={{ color: "var(--muted)" }}
                onClick={() => setShowAddress(true)}
              >
                or type an address
              </button>
            )}
          </div>
        )}
      </div>

      <div>
        <span className="label">Anything you can&apos;t eat?</span>
        <div className="flex flex-wrap gap-2">
          {DIET_CHIPS.map((chip) => (
            <button
              key={chip.key}
              type="button"
              aria-pressed={diets.includes(chip.key)}
              className={`chip ${diets.includes(chip.key) ? "chip-on" : ""}`}
              onClick={() => toggleDiet(chip.key)}
            >
              {chip.label}
            </button>
          ))}
        </div>

        {advisorySelected.length > 0 ? (
          <div className="mt-3">
            <Note tone="warn">
              Heads up — the map data behind Hangry has no allergen information at all, so we can&apos;t filter on{" "}
              {advisorySelected.map((c) => c.label.toLowerCase()).join(" or ")}. Everyone will see a reminder to check
              with the restaurant. We won&apos;t tell you somewhere is safe.
            </Note>
          </div>
        ) : null}
      </div>

      <div>
        <label className="label" htmlFor="distance">
          How far will you go?
        </label>
        <select id="distance" className="field" value={maxDistance} onChange={(e) => setMaxDistance(Number(e.target.value))}>
          {DISTANCE_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <label className="flex items-center gap-3 text-sm">
        <input type="checkbox" className="h-5 w-5 accent-amber-400" checked={openNow} onChange={(e) => setOpenNow(e.target.checked)} />
        Only somewhere open right now
      </label>

      {mode === "create" ? (
        <div>
          <label className="label" htmlFor="radius">
            How far should we search?
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

      <ErrorNote>{localError ?? error}</ErrorNote>

      <button className="btn btn-primary" disabled={busy || !name.trim() || !coords}>
        {busy ? "One sec…" : mode === "create" ? "Get the link" : "I'm in"}
      </button>

      {!coords ? <Note>We need a rough location to find places near everyone. It isn&apos;t stored after the session expires.</Note> : null}
    </form>
  );
}
