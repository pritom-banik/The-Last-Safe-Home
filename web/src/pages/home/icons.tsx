/** Small line icons for the home page (decorative: aria-hidden). */

import type { ReactNode } from "react";

function Icon({ children, className = "h-8 w-8" }: { children: ReactNode; className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} fill="none" stroke="currentColor" strokeWidth="2.4"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      {children}
    </svg>
  );
}

/** The app's mark: a house on a wave, inside the red sun. */
export function Logo({ className = "h-9 w-9" }: { className?: string }) {
  return (
    <svg viewBox="0 0 48 48" className={className} aria-hidden>
      <circle cx="24" cy="24" r="23" fill="#006a4e" />
      <circle cx="24" cy="22" r="13" fill="#f42a41" />
      <path d="M16 25 L24 18 L32 25 V32 H16 Z" fill="#fff" />
      <path d="M6 35 q4.5 -4 9 0 t9 0 t9 0 t9 0" stroke="#7cc4f0" strokeWidth="3" fill="none" strokeLinecap="round" />
    </svg>
  );
}

/** Fish and rice: what the river gives. */
export const GivesIcon = () => (
  <Icon>
    <path d="M6 22 C12 14 24 14 30 22 C24 30 12 30 6 22 Z" />
    <path d="M30 22 L37 17 V27 Z" />
    <circle cx="13" cy="21" r="1.2" fill="currentColor" />
    <path d="M38 42 V30 M38 30 q-4 -2 -5 -7 M38 33 q4 -2 5 -7 M38 37 q-4 -2 -5 -6" />
    <path d="M4 42 h40" />
  </Icon>
);

/** A house tipping into the water: what the river takes. */
export const TakesIcon = () => (
  <Icon>
    <path d="M8 26 L18 18 L28 26 V36 H8 Z" />
    <path d="M28 30 L34 36 L30 40 L36 44" />
    <path d="M4 44 q5 -4 10 0 t10 0 t10 0 t10 0" />
    <path d="M38 22 l4 -4 M40 28 l5 -1" />
  </Icon>
);

/** A cloud hiding the land: nobody can say when. */
export const UnknownIcon = () => (
  <Icon>
    <path d="M14 30 a7 7 0 0 1 1 -14 a10 10 0 0 1 19 3 a6 6 0 0 1 0 11 Z" />
    <path d="M22 36 q0 -3 3 -4 q3 -1 3 -4 a3 3 0 0 0 -6 0" />
    <circle cx="25" cy="41" r="1.2" fill="currentColor" />
  </Icon>
);

/** Satellite sending radar waves down. */
export const RadarIcon = () => (
  <Icon>
    <rect x="18" y="6" width="12" height="9" rx="1.5" />
    <path d="M6 8 h10 M32 8 h10 M6 13 h10 M32 13 h10" />
    <path d="M17 22 q7 5 14 0 M13 28 q11 8 22 0 M9 34 q15 11 30 0" />
  </Icon>
);

/** A stack of years: Landsat since 1988. */
export const YearsIcon = () => (
  <Icon>
    <rect x="8" y="10" width="26" height="20" rx="2" />
    <rect x="14" y="18" width="26" height="20" rx="2" fill="#fff" />
    <path d="M18 31 q5 -6 10 -2 t9 -3" />
  </Icon>
);

/** Lines across a bank, with a ruler. */
export const SpeedIcon = () => (
  <Icon>
    <path d="M6 30 C14 22 24 34 42 24" />
    <path d="M12 14 V40 M22 14 V40 M32 14 V40" strokeDasharray="3 3" />
    <path d="M36 12 l6 6 M42 12 l-6 6" />
  </Icon>
);

/** A house with a score badge. */
export const ScoreIcon = () => (
  <Icon>
    <path d="M6 26 L18 16 L30 26 V40 H6 Z" />
    <circle cx="35" cy="14" r="8" />
    <path d="M32 14 h6 M35 11 v6" />
  </Icon>
);
