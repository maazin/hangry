"use client";

import { useState } from "react";

import { geocode, locate, type JoinPayload } from "@/lib/api";
import { DIET_CHIPS, DISTANCE_OPTIONS, RADIUS_OPTIONS } from "@/lib/constraints";
import { Check, Pin } from "./icons";
import { Callout, ErrorNote, Note } from "./ui";

/**
 * The joiner's entire flow. Every control here has to earn its tap — five of
 * the six people using this didn't start the session and have near-zero
 * patience for a form. Four questions, one screen, no scrolling on a phone
 * until the diet chips.
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
    <form onSubmit={submit} className="space-y-7">
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
          <div
            className="flex items-center gap-3 px-4"
            style={{
              minHeight: 52,
              background: "var(--brand-tint)",
              borderRadius: "var(--r)",
              border: "1px solid transparent",
            }}
          >
            <Check size={19} className="shrink-0" style={{ color: "var(--brand)" }} />
            <span className="min-w-0 flex-1 truncate text-[14px]" style={{ color: "var(--text)" }}>
              {placeLabel}
            </span>
            <button
              type="button"
              className="shrink-0 text-[14px] font-semibold"
              style={{ color: "var(--brand)" }}
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
              <Pin size={19} style={{ color: "var(--brand)" }} />
              {locating ? "Finding you…" : "Use my location"}
            </button>

            {showAddress ? (
              <div className="flex gap-2">
                <input
                  className="field"
                  value={address}
                  onChange={(e) => setAddress(e.target.value)}
                  onKeyDown={(e) => {
                    // Enter here should look up the address, not submit a form
                    // that has no location yet.
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
                or type an address
              </button>
            )}
          </div>
        )}
      </div>

      <div>
        <span className="label">Anything you can&apos;t eat?</span>
        <div className="flex flex-wrap gap-2">
          {DIET_CHIPS.map((chip) => {
            const on = diets.includes(chip.key);
            return (
              <button
                key={chip.key}
                type="button"
                aria-pressed={on}
                className={`chip ${on ? "chip-on" : ""}`}
                onClick={() => toggleDiet(chip.key)}
              >
                {on ? <Check size={16} className="-ml-0.5 mr-1.5" /> : null}
                {chip.label}
              </button>
            );
          })}
        </div>

        {advisorySelected.length > 0 ? (
          <div className="mt-4">
            <Callout title="We can't check that one">
              The map data behind Hangry has no allergen information at all, so{" "}
              {advisorySelected.map((c) => c.label.toLowerCase()).join(" and ")} can&apos;t be filtered on. Everyone
              will see a reminder to check with the restaurant. We won&apos;t tell you somewhere is safe.
            </Callout>
          </div>
        ) : null}
      </div>

      <div className={mode === "create" ? "grid grid-cols-2 gap-3" : ""}>
        <div>
          <label className="label" htmlFor="distance">
            You&apos;ll travel
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
            <label className="label" htmlFor="radius">
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
        className="flex cursor-pointer items-center gap-3 px-4 text-[15px]"
        style={{ minHeight: 52, background: "var(--surface)", border: "1px solid var(--border)", borderRadius: "var(--r)" }}
      >
        <input
          type="checkbox"
          className="h-[20px] w-[20px] shrink-0 rounded"
          style={{ accentColor: "var(--brand)" }}
          checked={openNow}
          onChange={(e) => setOpenNow(e.target.checked)}
        />
        Only somewhere open right now
      </label>

      <div className="space-y-3">
        <ErrorNote>{localError ?? error}</ErrorNote>

        <button className="btn btn-primary" disabled={busy || !name.trim() || !coords}>
          {busy ? "One sec…" : mode === "create" ? "Get the link" : "I'm in"}
        </button>

        {!coords ? (
          <Note>We need a rough location to find places near everyone. It&apos;s gone when the session expires.</Note>
        ) : null}
      </div>
    </form>
  );
}
