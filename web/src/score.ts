/** Home Risk Score classes (SPEC §8). Mirrors pipeline/lsh/score.py CLASSES — keep the two in step. */

export type ClassKey = "low" | "moderate" | "high" | "severe";

export const CLASSES: { key: ClassKey; min: number; colour: string }[] = [
  { key: "low", min: 0, colour: "#1a9850" },
  { key: "moderate", min: 25, colour: "#fee08b" },
  { key: "high", min: 50, colour: "#f46d43" },
  { key: "severe", min: 75, colour: "#a50026" },
];

export const CLASS_KEYS: ClassKey[] = CLASSES.map((c) => c.key);

/** Class for a 0–100 score; null for missing / NaN. */
export function scoreClass(score: number | null | undefined): ClassKey | null {
  if (score == null || !Number.isFinite(score)) return null;
  let key: ClassKey = "low";
  for (const c of CLASSES) if (score >= c.min) key = c.key;
  return key;
}

export function classColour(key: ClassKey): string {
  return CLASSES.find((c) => c.key === key)!.colour;
}

/** Dark text on the light (moderate) chip, white on the others. */
export function classTextColour(key: ClassKey): string {
  return key === "moderate" ? "#1f2937" : "#ffffff";
}
