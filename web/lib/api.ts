import {
  ApiError,
  type BindingConstraint,
  type GroupState,
  type HardConstraints,
  type Member,
  type RoundCreated,
  type SessionResult,
  type SessionState,
} from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

/**
 * There are no accounts. A participant is an opaque token in localStorage,
 * scoped to the session slug, so the same phone can be in two groups at
 * once and neither knows about the other.
 */
const tokenKey = (slug: string) => `hangry:token:${slug}`;

export function readToken(slug: string): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(tokenKey(slug));
}

export function writeToken(slug: string, token: string) {
  window.localStorage.setItem(tokenKey(slug), token);
}

export function clearToken(slug: string) {
  window.localStorage.removeItem(tokenKey(slug));
}

/**
 * A member's group token *is* their token in every round, so copying it onto
 * the round slug lets the round page authenticate with no extra concept,
 * one string per group on the phone, not one per meal.
 */
export function adoptTokenForRound(groupSlug: string, roundSlug: string) {
  const token = readToken(groupSlug);
  if (token && readToken(roundSlug) !== token) writeToken(roundSlug, token);
}

/** Groups the phone has joined, newest first. Powers the groups list. */
const GROUPS_KEY = "hangry:groups";

export function rememberGroup(slug: string, name: string) {
  if (typeof window === "undefined") return;
  const existing = listGroups().filter((g) => g.slug !== slug);
  window.localStorage.setItem(GROUPS_KEY, JSON.stringify([{ slug, name }, ...existing].slice(0, 12)));
}

export function listGroups(): { slug: string; name: string }[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(GROUPS_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

export function forgetGroup(slug: string) {
  window.localStorage.setItem(GROUPS_KEY, JSON.stringify(listGroups().filter((g) => g.slug !== slug)));
}

async function request<T>(path: string, init: RequestInit = {}, token?: string | null): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { "X-Participant-Token": token } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError(0, "offline", "Can't reach Hangry. Check your connection.");
  }

  if (!response.ok) {
    let code = "error";
    let message = `Something went wrong (${response.status}).`;
    let binding: BindingConstraint[] = [];

    try {
      const body = await response.json();
      const detail = body?.detail;
      if (typeof detail === "string") {
        message = detail;
      } else if (detail) {
        code = detail.code ?? code;
        message = detail.message ?? message;
        binding = detail.binding_constraints ?? [];
      } else if (Array.isArray(body?.detail)) {
        message = "That didn't look right. Check the form and try again.";
      }
    } catch {
      /* keep the default message */
    }
    throw new ApiError(response.status, code, message, binding);
  }

  // 204 carries no body, so parsing one would throw on success.
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export interface JoinPayload {
  name: string;
  lat: number;
  lon: number;
  hard_constraints: HardConstraints;
}

export const api = {
  createSession: (creator: JoinPayload, radius_m: number) =>
    request<{ slug: string; participant_id: string; token: string; status: string }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ creator, radius_m }),
    }),

  /** Token is optional: someone who hasn't joined still needs to see the lobby. */
  getSession: (slug: string, token?: string | null) => request<SessionState>(`/api/sessions/${slug}`, {}, token),

  join: (slug: string, body: JoinPayload) =>
    request<{ participant_id: string; token: string }>(`/api/sessions/${slug}/participants`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  start: (slug: string, token: string) =>
    request<{ status: string; candidates: unknown[]; advisories: unknown[] }>(
      `/api/sessions/${slug}/start`,
      { method: "POST" },
      token,
    ),

  submitRanking: (slug: string, token: string, ordered_candidate_ids: string[]) =>
    request<{ submitted: number; total: number; status: string }>(
      `/api/sessions/${slug}/rankings`,
      { method: "POST", body: JSON.stringify({ ordered_candidate_ids }) },
      token,
    ),

  solve: (slug: string, token: string) =>
    request<SessionResult>(`/api/sessions/${slug}/solve`, { method: "POST" }, token),

  // ---- groups -----------------------------------------------------------

  createGroup: (name: string, founder: JoinPayload) =>
    request<{ slug: string; member_id: string; token: string }>("/api/groups", {
      method: "POST",
      body: JSON.stringify({ name, founder }),
    }),

  getGroup: (slug: string, token?: string | null) => request<GroupState>(`/api/groups/${slug}`, {}, token),

  joinGroup: (slug: string, body: JoinPayload) =>
    request<{ slug: string; member_id: string; token: string }>(`/api/groups/${slug}/members`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  updateMember: (slug: string, token: string, body: Partial<JoinPayload>) =>
    request<Member>(`/api/groups/${slug}/members/me`, { method: "PATCH", body: JSON.stringify(body) }, token),

  leaveGroup: (slug: string, token: string) =>
    request<void>(`/api/groups/${slug}/members/me`, { method: "DELETE" }, token),

  startRound: (slug: string, token: string, memberIds: string[] | null, radiusM: number) =>
    request<RoundCreated>(
      `/api/groups/${slug}/rounds`,
      { method: "POST", body: JSON.stringify({ member_ids: memberIds, radius_m: radiusM }) },
      token,
    ),
};

/** Browser geolocation, wrapped so the caller gets a plain promise. */
export function locate(): Promise<{ lat: number; lon: number }> {
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("This browser can't share your location."));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => resolve({ lat: position.coords.latitude, lon: position.coords.longitude }),
      () => reject(new Error("Couldn't get your location. Type an address instead.")),
      { enableHighAccuracy: false, timeout: 10_000, maximumAge: 300_000 },
    );
  });
}

/**
 * Manual address fallback, via OSM's own geocoder.
 *
 * Nominatim is keyless and same-family as the Overpass data behind the rest
 * of the app. It is rate-limited and asks for light use, which suits a
 * fallback nobody hits unless they declined the location prompt.
 */
export async function geocode(query: string): Promise<{ lat: number; lon: number; label: string }> {
  const url = new URL("https://nominatim.openstreetmap.org/search");
  url.searchParams.set("q", query);
  url.searchParams.set("format", "json");
  url.searchParams.set("limit", "1");

  const response = await fetch(url, { headers: { Accept: "application/json" } });
  if (!response.ok) throw new Error("Address lookup failed. Try again.");

  const [hit] = await response.json();
  if (!hit) throw new Error("Couldn't find that address.");
  return { lat: Number(hit.lat), lon: Number(hit.lon), label: hit.display_name };
}
