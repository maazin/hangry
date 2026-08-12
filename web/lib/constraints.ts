/**
 * The dietary vocabulary, mirroring `api/app/constraints.py`.
 *
 * `filterable` marks the constraints OpenStreetMap actually has tags for.
 * The rest are shown with an honest warning rather than a checkbox that
 * quietly does nothing.
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

export const DISTANCE_OPTIONS = [
  { value: 2000, label: "2 km" },
  { value: 5000, label: "5 km" },
  { value: 10000, label: "10 km" },
  { value: 20000, label: "20 km" },
];

export const RADIUS_OPTIONS = [
  { value: 2000, label: "Walking distance" },
  { value: 5000, label: "Around here" },
  { value: 10000, label: "Wider net" },
];

export const metres = (m: number) => (m < 1000 ? `${Math.round(m)} m` : `${(m / 1000).toFixed(1)} km`);
