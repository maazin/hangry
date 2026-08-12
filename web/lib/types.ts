export type Tier = "feasible" | "unverified" | "eliminated";

export type SessionStatus = "collecting" | "ranking" | "decided" | "expired";

export interface CutReason {
  participant: string;
  participant_id: string;
  constraint: string;
  /** "eliminated" means provably violated; "unknown" means the data can't say. */
  kind: "eliminated" | "unknown";
  detail: string;
}

export interface Candidate {
  id: string;
  place_id: string;
  name: string;
  lat: number;
  lon: number;
  cuisine: string[];
  tier: Tier;
  /** In the vote. Not implied by tier — sparse data puts unverified places in. */
  locked: boolean;
  distance_m: number;
  cut_reasons: CutReason[];
}

export interface Participant {
  id: string;
  display_name: string;
  is_creator: boolean;
  hard_constraints: HardConstraints;
  joined_at: string;
}

export interface HardConstraints {
  diets?: string[];
  max_distance_m?: number | null;
  max_price_tier?: number | null;
  open_now?: boolean;
}

export interface Advisory {
  participant?: string;
  constraint: string;
  detail: string;
}

export interface RankedOption {
  candidate_id: string;
  option: string;
  name: string;
  cuisine: string[];
  lat: number;
  lon: number;
  distance_m: number;
  max_regret: number;
  mean: number;
  minimum: number;
  worst_for: string[];
  best_for: string[];
  annotation: string;
}

export interface Comparison {
  headline: string;
  utilitarian: { option: string; name: string; excludes: string[]; mean: number };
  maximin: { option: string; name: string; minimum: number };
  minimax_regret: { option: string; name: string; max_regret: number };
}

export interface SessionResult {
  ranked: RankedOption[];
  alternates: { voters: string[]; non_voters: string[]; comparison: Comparison };
  comparison: Comparison;
  rule: string;
  computed_at: string;
}

/** Who the caller is, resolved server-side from the participant token. */
export interface You {
  participant_id: string;
  display_name: string;
  is_creator: boolean;
  has_ranked: boolean;
}

/** Someone in a group. Their constraints persist between meals. */
export interface Member {
  id: string;
  display_name: string;
  is_founder: boolean;
  hard_constraints: HardConstraints;
  joined_at: string;
}

export interface RoundSummary {
  slug: string;
  status: SessionStatus;
  created_at: string;
  expires_at: string;
  participants: number;
  submitted: number;
  winner: string | null;
}

export interface GroupState {
  slug: string;
  name: string;
  created_at: string;
  members: Member[];
  rounds: RoundSummary[];
  /** The round still being decided. Null means the group page is a launcher. */
  active_round: RoundSummary | null;
  advisories: Advisory[];
  you: { member_id: string; display_name: string; is_founder: boolean } | null;
}

export interface RoundCreated {
  slug: string;
  status: SessionStatus;
  candidates: Candidate[];
  advisories: Advisory[];
  unverified_used: boolean;
}

export interface SessionState {
  slug: string;
  status: SessionStatus;
  /** Set when this session is a round in a group. */
  group_slug: string | null;
  radius_m: number;
  center_lat: number | null;
  center_lon: number | null;
  created_at: string;
  expires_at: string;
  participants: Participant[];
  candidates: Candidate[];
  advisories: Advisory[];
  submitted: number;
  result: SessionResult | null;
  you: You | null;
}

export interface BindingConstraint {
  participant: string;
  constraint: string;
  label: string;
  eliminated: number;
}

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly bindingConstraints: BindingConstraint[] = [],
  ) {
    super(message);
  }
}
