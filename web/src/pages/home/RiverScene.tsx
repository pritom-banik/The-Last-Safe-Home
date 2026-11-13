/**
 * Hero illustration for the home page: sunrise over a Bangladeshi river. The red sun over green land echoes
 * the national flag; a family's house stands on a crumbling bank, a child flies a kite, a nouka passes, and a
 * dashed line out in the water marks where the bank was in 1988 (the app's own bank-line idea).
 * The story sits on the right so the page text can use the dark sky on the left; on phones the picture is
 * anchored to the right (xMax) and shown under the text. Pure SVG, no downloads; the gentle motion stops
 * under prefers-reduced-motion (index.css).
 */

type Props = { oldBank: string; todayBank: string; title: string };

export default function RiverScene({ oldBank, todayBank, title }: Props) {
  return (
    <svg
      viewBox="0 0 1440 800"
      preserveAspectRatio="xMaxYMax slice"
      className="h-full w-full"
      role="img"
      aria-label={title}
    >
      <defs>
        <linearGradient id="hs-sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#0a1730" />
          <stop offset="0.45" stopColor="#173a63" />
          <stop offset="0.6" stopColor="#7c4a6b" />
          <stop offset="0.69" stopColor="#e9845a" />
          <stop offset="0.74" stopColor="#f8c27a" />
        </linearGradient>
        <radialGradient id="hs-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="#ff8a5c" stopOpacity="0.75" />
          <stop offset="1" stopColor="#ff8a5c" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="hs-river" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#5a8fb8" />
          <stop offset="0.35" stopColor="#2b7bb0" />
          <stop offset="1" stopColor="#185a86" />
        </linearGradient>
        <linearGradient id="hs-land" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#1f8a5b" />
          <stop offset="1" stopColor="#005a41" />
        </linearGradient>
        <linearGradient id="hs-soil" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#9a6a3c" />
          <stop offset="1" stopColor="#5e3d20" />
        </linearGradient>
      </defs>

      {/* sky, stars, sun */}
      <rect width="1440" height="800" fill="url(#hs-sky)" />
      <g fill="#fff" opacity="0.6">
        <circle cx="840" cy="70" r="1.6" />
        <circle cx="1020" cy="40" r="1.2" />
        <circle cx="1210" cy="130" r="1.4" />
        <circle cx="1330" cy="55" r="1.1" />
        <circle cx="940" cy="190" r="1.5" />
        <circle cx="620" cy="30" r="1.1" />
        <circle cx="1400" cy="210" r="1" />
      </g>
      <circle cx="870" cy="560" r="200" fill="url(#hs-glow)" />
      <circle cx="870" cy="560" r="72" fill="#f42a41" />

      {/* birds */}
      <g fill="none" stroke="#1e293b" strokeWidth="2.4" strokeLinecap="round" opacity="0.75">
        <path d="M960 400 q10 -10 20 0 q10 -10 20 0" />
        <path d="M1010 372 q7 -7 14 0 q7 -7 14 0" />
        <path d="M925 430 q6 -6 12 0 q6 -6 12 0" />
      </g>

      {/* the child's kite */}
      <g className="lsh-kite">
        <path d="M1226 300 L1250 272 L1274 300 L1250 336 Z" fill="#f42a41" />
        <path d="M1226 300 L1274 300 M1250 272 L1250 336" stroke="#fff" strokeWidth="1.5" opacity="0.8" />
        <path d="M1250 336 q-8 14 4 24 q-10 10 2 22" fill="none" stroke="#fde68a" strokeWidth="2" />
      </g>
      <path d="M1250 336 Q 1236 490 1192 618" fill="none" stroke="#e2e8f0" strokeWidth="1" opacity="0.7" />

      {/* far bank: tree line and village roofs */}
      <path
        d="M0 572 C60 552 90 562 130 554 C170 534 210 550 250 544 C300 530 330 548 380 540 C430 532 470 552 520 544
           C580 532 620 552 680 546 C740 536 780 556 840 550 C900 544 950 556 1010 552 C1080 546 1130 558 1200 552
           C1270 542 1320 556 1380 550 L1440 548 L1440 592 L0 592 Z"
        fill="#0b3d2c"
      />
      <g fill="#0b3d2c">
        <path d="M290 548 l18 -14 l18 14 z" />
        <path d="M700 546 l16 -12 l16 12 z" />
        <path d="M1290 550 l18 -14 l18 14 z" />
      </g>

      {/* river */}
      <path d="M0 588 L1440 588 L1440 800 L0 800 Z" fill="url(#hs-river)" />
      <g fill="#ff7a59" opacity="0.8">
        <rect x="820" y="600" width="100" height="5" rx="2.5" />
        <rect x="835" y="614" width="70" height="4" rx="2" opacity="0.8" />
        <rect x="810" y="628" width="120" height="4" rx="2" opacity="0.6" />
      </g>
      <g className="lsh-waves" fill="none" stroke="#e0f2fe" strokeWidth="2" strokeLinecap="round" opacity="0.35">
        <path d="M60 620 q20 -8 40 0 t40 0" />
        <path d="M300 660 q20 -8 40 0 t40 0" />
        <path d="M520 612 q20 -8 40 0 t40 0" />
        <path d="M420 740 q20 -8 40 0 t40 0" />
        <path d="M880 610 q20 -8 40 0 t40 0" />
        <path d="M620 760 q20 -8 40 0 t40 0" />
        <path d="M1500 640 q20 -8 40 0 t40 0" />
      </g>

      {/* where the bank was in 1988 — out in today's river */}
      <path
        d="M968 600 C890 610 800 650 738 700 C698 732 668 770 650 812"
        fill="none"
        stroke="#fde68a"
        strokeWidth="2.5"
        strokeDasharray="9 9"
        opacity="0.9"
      />
      <text x="680" y="730" textAnchor="end" fill="#fde68a" fontSize="20" fontWeight="600">
        {oldBank}
      </text>

      {/* boat (nouka) with its boatman */}
      <g className="lsh-boat">
        <path d="M640 650 Q700 676 770 650 Q760 668 706 672 Q652 670 640 650 Z" fill="#3b2412" />
        <path d="M670 652 Q706 616 742 652 Z" fill="#8a5a2b" />
        <path d="M676 652 Q706 624 736 652" fill="none" stroke="#c08a4b" strokeWidth="2" />
        <circle cx="758" cy="612" r="6" fill="#1e293b" />
        <path d="M758 618 L756 648" stroke="#1e293b" strokeWidth="5" strokeLinecap="round" />
        <path d="M756 626 L744 638" stroke="#1e293b" strokeWidth="3.5" strokeLinecap="round" />
        <path d="M748 584 L718 704" stroke="#3b2412" strokeWidth="3" />
      </g>

      {/* near bank on the right, its edge breaking into the river */}
      <path
        d="M1440 648 L968 648 L948 660 L938 654 L918 676 L898 670 L880 698 L860 694 L844 724 L826 720 L812 756
           L798 754 L788 800 L1440 800 Z"
        fill="url(#hs-soil)"
      />
      <path
        d="M1440 640 L976 640 L956 652 L946 646 L926 668 L906 662 L888 690 L868 686 L852 716 L834 712 L820 748
           L806 746 L796 800 L1440 800 Z"
        fill="url(#hs-land)"
      />
      <g fill="#6b4423">
        <path d="M880 712 l14 -6 l10 8 l-8 8 z" />
        <path d="M808 776 l12 -6 l9 9 l-9 6 z" />
        <path d="M914 690 l10 -4 l6 7 l-8 5 z" />
      </g>
      <path d="M1440 641 L976 641 L956 653" fill="none" stroke="#4fbf80" strokeWidth="5" strokeLinejoin="round" />
      <text x="960" y="704" fill="#ffffff" fontSize="18" fontWeight="600" opacity="0.95">
        {todayBank}
      </text>

      {/* paddy rows */}
      <g stroke="#7bc47f" strokeWidth="2" opacity="0.45">
        <path d="M1010 690 L1440 682" />
        <path d="M960 722 L1440 712" />
        <path d="M920 754 L1440 742" />
        <path d="M880 786 L1440 772" />
      </g>

      {/* coconut palms */}
      <g>
        <path d="M1300 644 Q1292 572 1314 512" fill="none" stroke="#4a2f1a" strokeWidth="9" strokeLinecap="round" />
        <g fill="#0f5132">
          <path d="M1314 512 q-60 -6 -86 30 q40 -20 86 -30 z" />
          <path d="M1314 512 q-30 -46 -84 -46 q46 10 84 46 z" />
          <path d="M1314 512 q10 -56 60 -70 q-36 26 -60 70 z" />
          <path d="M1314 512 q56 -16 90 18 q-44 -12 -90 -18 z" />
          <path d="M1314 512 q40 22 52 66 q-20 -36 -52 -66 z" />
        </g>
        <path d="M1396 642 Q1390 594 1406 556" fill="none" stroke="#4a2f1a" strokeWidth="7" strokeLinecap="round" />
        <g fill="#13643f">
          <path d="M1406 556 q-44 -4 -64 22 q30 -16 64 -22 z" />
          <path d="M1406 556 q-22 -34 -62 -34 q34 8 62 34 z" />
          <path d="M1406 556 q8 -42 46 -52 q-28 20 -46 52 z" />
          <path d="M1406 556 q42 -12 66 14 q-32 -10 -66 -14 z" />
        </g>
      </g>

      {/* the family's house near the edge: bamboo walls, tin roof */}
      <g transform="translate(0 14)">
        <rect x="1000" y="594" width="104" height="48" fill="#c9955a" />
        <g stroke="#a6743f" strokeWidth="2">
          <path d="M1016 594 v48 M1032 594 v48 M1048 594 v48 M1080 594 v48 M1096 594 v48" />
        </g>
        <rect x="1056" y="610" width="20" height="32" fill="#3b2412" />
        <path d="M988 598 L1052 556 L1116 598 Z" fill="#a3b1c2" />
        <path d="M988 598 L1052 556 L1116 598" fill="none" stroke="#64748b" strokeWidth="3" />
        <path d="M1012 584 L1052 560 M1028 590 L1064 566 M1076 590 L1092 580" stroke="#cbd5e1" strokeWidth="1.5" opacity="0.7" />
      </g>

      {/* a parent at the edge looking at the river; a child flying the kite */}
      <g fill="#1e293b" transform="translate(0 14)">
        <circle cx="972" cy="600" r="8" />
        <path d="M962 610 h20 l4 30 h-28 z" />
        <circle cx="1186" cy="608" r="6" />
        <path d="M1179 616 h14 l3 24 h-20 z" />
        <path d="M1190 618 L1194 602" stroke="#1e293b" strokeWidth="3" strokeLinecap="round" />
      </g>
    </svg>
  );
}
