"use client";

import { useState } from "react";

import { geocode, locate, type JoinPayload } from "@/lib/api";
import { DIET_CHIPS, DISTANCE_OPTIONS, RADIUS_OPTIONS, miles } from "@/lib/constraints";
import { Pin } from "./icons";
import { Caution, ErrorNote, Note } from "./ui";

/*
 * The joiner's whole flow. Five of the six people who use this did not start
 * the group and have very little patience for a form, so every control has to
 * earn its tap.
 *
 * Selected chips are shown by fill and weight rather than by a tick, which
 * keeps the state readable for anyone who cannot separate the two colours.
 */
export function ConstraintForm({
  mode,
  busy,
  error,
  prelude,
  submitLabel,
  onSubmit,
}: {
  mode: "create" | "join";
  busy: boolean;
  error: string | null;
  /** Sits inside the form, above the name. The group name uses this. */
  prelude?: React.ReactNode;
  submitLabel?: string;
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
  const [maxDistance, setMaxDistance] = useState<number>(miles(5));
  const [radius, setRadius] = useState<number>(miles(3));
  const [openNow, setOpenNow] = useState(true);

  const unfilterable = DIET_CHIPS.filter((c) => !c.filterable && diets.includes(c.key));

  async function useMyLocation() {
    setLocating(true);
    setLocalError(null);
    try {
      const position = await locate();
      setCoords(position);
      setPlaceLabel("Your current location");
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
    <form onSubmit={submit} className="space-y-8">
      {prelude}

      <div>
        <label className="eyebrow" htmlFor="name">
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
        <span className="eyebrow">Where are you?</span>
        {coords ? (
          <div
            className="flex items-center gap-3 rounded-m px-4 py-3"
            style={{ background: "var(--brand-wash)", border: "1px solid var(--hairline)" }}
          >
            <Pin size={18} className="shrink-0" style={{ color: "var(--brand)" }} />
            <span className="min-w-0 flex-1 truncate text-subhead">{placeLabel}</span>
            <button
              type="button"
              className="shrink-0 text-subhead font-semibold"
              style={{ color: "var(--brand)", minHeight: "var(--tap)" }}
              onClick={() => {
                setCoords(null);
                setPlaceLabel(null);
              }}
            >
              Change
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            <button type="button" className="btn btn-secondary" onClick={useMyLocation} disabled={locating}>
              <Pin size={18} style={{ color: "var(--brand)" }} />
              {locating ? "Finding you" : "Use my location"}
            </button>

            {showAddress ? (
              <div className="flex gap-2">
                <input
                  className="field"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  onKeyDown={(e) => {
                    // Enter looks up the address rather than submitting a form
                    // that still has no location.
                    if (e.key === "Enter") {
                      e.preventDefault();
                      void useAddress();
                    }
                  }}
                  placeholder="Street, city"
                  autoComplete="street-address"
                />
                <button
                  type="button"
                  className="btn btn-secondary !w-auto px-5"
                  onClick={useAddress}
                  disabled={locating || !address.trim()}
                >
                  Find
                </button>
              </div>
            ) : (
              <button type="button" className="btn btn-quiet" onClick={() => setShowAddress(true)}>
                Or type an address
              </button>
            )}
          </div>
        )}
      </div>

      <div>
        <span className="eyebrow">Anything you cannot eat?</span>
        <div className="flex flex-wrap gap-2">
          {DIET_CHIPS.map((chip) => (
            <button
              key={chip.key}
              type="button"
              aria-pressed={diets.includes(chip.key)}
              className="chip"
              onClick={() => toggleDiet(chip.key)}
            >
              {chip.label}
            </button>
          ))}
        </div>

        {unfilterable.length > 0 ? (
          <div className="mt-4">
            <Caution title="This one cannot be checked">
              The map data behind Hangry holds no allergen information at all, so{" "}
              {unfilterable.map((c) => c.label.toLowerCase()).join(" and ")} cannot be filtered on. Everyone will see a
              reminder to ask the restaurant. Hangry will never tell you somewhere is safe.
            </Caution>
          </div>
        ) : null}
      </div>

      <div className={mode === "create" ? "grid grid-cols-2 gap-3" : ""}>
        <div>
          <label className="eyebrow" htmlFor="distance">
            You will travel
          </label>
          <select
            id="distance"
            className="field"
            value={maxDistance}
            onChange={(e) => setMaxDistance(Number(e.target.value))}
          >
            {DISTANCE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {mode === "create" ? (
          <div>
            <label className="eyebrow" htmlFor="radius">
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
      </div>

      <label
        className="flex cursor-pointer items-center gap-3 rounded-m px-4"
        style={{
          minHeight: "var(--tap)",
          background: "var(--surface)",
          border: "1px solid var(--hairline)",
        }}
      >
        <input
          type="checkbox"
          className="h-5 w-5 shrink-0"
          style={{ accentColor: "var(--brand)" }}
          checked={openNow}
          onChange={(e) => setOpenNow(e.target.checked)}
        />
        <span className="text-subhead">Only somewhere open right now</span>
      </label>

      <div className="space-y-4">
        <ErrorNote>{localError ?? error}</ErrorNote>

        <button className="btn btn-primary" disabled={busy || !name.trim() || !coords}>
          {busy ? "One moment" : (submitLabel ?? (mode === "create" ? "Get the link" : "Join"))}
        </button>

        {!coords ? (
          <Note>A rough location is enough to find places near everyone. It goes when the session expires.</Note>
        ) : null}
      </div>
    </form>
  );
}
