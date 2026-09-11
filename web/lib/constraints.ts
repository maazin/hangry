/**
 * The dietary vocabulary, mirroring `api/app/constraints.py`.
 *
 * `filterable` marks the constraints OpenStreetMap actually has tags for. The
 * rest are shown with an honest warning rather than a control that quietly
 * does nothing.
 */
export interface DietChip {
  key: string;
  label: string;
  filterable: boolean;
}

export const DIET_CHIPS: DietChip[] = [
  { key: "vegetarian", label: "Vegetarian", filterable: true },
  { key: "vegan", label: "Vegan", filterable: true },
  { key: "gluten_free", label: "Gluten-free", filterable: true },
  { key: "halal", label: "Halal", filterable: true },
  { key: "kosher", label: "Kosher", filterable: true },
  { key: "nut_allergy", label: "Nut allergy", filterable: false },
  { key: "shellfish_allergy", label: "Shellfish allergy", filterable: false },
];

/*
 * Distances are chosen and shown in miles, and sent to the API in metres,
 * which is what the geo maths uses throughout.
 *
 * The old options topped out at 10 km and were labelled in kilometres, which
 * made a US user pick a search area smaller than they meant and then find
 * nothing.
 */
const MILE_M = 1609.344;
export const miles = (mi: number) => Math.round(mi * MILE_M);

export const DISTANCE_OPTIONS = [
  { value: miles(1), label: "1 mile" },
  { value: miles(3), label: "3 miles" },
  { value: miles(5), label: "5 miles" },
  { value: miles(10), label: "10 miles" },
  { value: miles(20), label: "20 miles" },
];

export const RADIUS_OPTIONS = [
  { value: miles(1), label: "1 mile, walking" },
  { value: miles(3), label: "3 miles, nearby" },
  { value: miles(5), label: "5 miles, wider" },
  { value: miles(10), label: "10 miles, the whole area" },
];

/** Distance as a reader sees it. Under a quarter mile reads better in feet. */
export const distanceLabel = (m: number) => {
  const mi = m / MILE_M;
  if (mi < 0.25) return `${Math.round(m * 3.28084 / 10) * 10} ft`;
  if (mi < 10) return `${mi.toFixed(1)} mi`;
  return `${Math.round(mi)} mi`;
};
