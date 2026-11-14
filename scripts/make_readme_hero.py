"""Generate the README hero banner (light and dark) from the app's theme palettes.

Usage: python3 scripts/make_readme_hero.py   # writes docs/assets/hero.svg
Colours match the Azulejo theme in base.html (used in light and dark mode).
"""

import math
import sys
from pathlib import Path

AZULEJO = {
    "bg": "#FBF8F4",
    "bg2": "#F0EDE7",
    "tile": "#1D4ED8",
    "tile_op": "0.07",
    "text": "#1E293B",
    "muted": "#4B5563",
    "accent": "#1D4ED8",
    "accent_text": "#FFFFFF",
    "ai": "#FFFFFF",
    "ai_border": "#D4CFC6",
    "ai_text": "#1E293B",
    "user": "#2563EB",
    "user_text": "#FFFFFF",
    "chip": "rgba(29,78,216,0.10)",
    "chip_text": "#1D4ED8",
    "rule": "#D4CFC6",
}
FONT = "'Plus Jakarta Sans', -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"
CHAT_ICON = (
    "M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949"
    "L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
)


def chip(x, y, label, t):
    w = 14 + len(label) * 8.2
    return (
        f'<rect x="{x}" y="{y}" width="{w:.0f}" height="28" rx="14" fill="{t["chip"]}"/>'
        f'<text x="{x + w / 2:.0f}" y="{y + 19}" text-anchor="middle" font-size="14" font-weight="600" '
        f'fill="{t["chip_text"]}">{label}</text>'
    ), w


# Argentine motifs: flag celeste and the gold of the Sol de Mayo.
CELESTE = "#74ACDF"
SOL = "#F6B40E"


def sol_de_mayo(cx, cy, r, opacity):
    """The Sol de Mayo: a disc with 32 rays, straight and wavy in turn (no face, kept abstract)."""
    parts = []
    for n in range(32):
        a = 2 * math.pi * n / 32
        ux, uy = math.cos(a), math.sin(a)
        px, py = -uy, ux
        if n % 2 == 0:  # straight ray: a thin triangle
            w, r1, r2 = 0.13 * r, 1.15 * r, 2.15 * r
            pts = [
                (cx + ux * r1 + px * w, cy + uy * r1 + py * w),
                (cx + ux * r2, cy + uy * r2),
                (cx + ux * r1 - px * w, cy + uy * r1 - py * w),
            ]
            parts.append('<path d="M' + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts) + ' Z"/>')
        else:  # wavy ray: a sine wave along the ray, drawn as a stroke
            r1, r2, amp = 1.15 * r, 1.95 * r, 0.09 * r
            pts = []
            for i in range(13):
                d = r1 + (r2 - r1) * i / 12
                off = amp * math.sin(i / 12 * 3 * math.pi)
                pts.append((cx + ux * d + px * off, cy + uy * d + py * off))
            parts.append(
                '<path fill="none" stroke-width="2.4" stroke-linecap="round" d="M'
                + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
                + '"/>'
            )
    rays = "".join(parts)
    return (
        f'<g opacity="{opacity}" fill="{SOL}" stroke="{SOL}">{rays}'
        f'<circle cx="{cx}" cy="{cy}" r="{r}" stroke="none"/></g>'
    )


def filete(x, y, flip=False):
    """A fileteado porteno volute: a curling scroll with a leaf, as on Buenos Aires signs."""
    t = f"translate({x} {y}) scale({-1.5 if flip else 1.5} 1.5)"
    return (
        f'<g transform="{t}" fill="none" stroke-linecap="round" opacity="0.7">'
        f'<path stroke="{CELESTE}" stroke-width="3" d="M0 0 C 40 0, 70 -26, 104 -18 '
        f'C 132 -11, 128 18, 104 16 C 88 15, 88 -2, 101 -1"/>'
        f'<path stroke="{SOL}" stroke-width="2" d="M14 9 C 46 10, 64 -8, 90 -6"/>'
        f'<path fill="{SOL}" stroke="none" d="M40 -2 C 46 -16, 62 -20, 70 -14 C 60 -12, 50 -8, 40 -2 Z"/>'
        f'<circle cx="101" cy="-1" r="3.2" fill="{SOL}" stroke="none"/>'
        "</g>"
    )


def mate(x, y, scale=1.0):
    """A mate gourd with its bombilla, in line art."""
    return (
        f'<g transform="translate({x} {y}) scale({scale})" opacity="0.75" stroke-linecap="round" '
        'stroke-linejoin="round">'
        f'<path d="M30 22 L44 -2" stroke="{SOL}" stroke-width="3" fill="none"/>'
        f'<rect x="40" y="-6" width="9" height="5" rx="2" transform="rotate(-60 44 -3)" fill="{SOL}"/>'
        f'<path d="M8 22 C 0 36, 6 56, 26 58 C 46 56, 52 36, 44 22 Z" fill="{CELESTE}" '
        f'fill-opacity="0.25" stroke="{CELESTE}" stroke-width="2.5"/>'
        f'<ellipse cx="26" cy="22" rx="18" ry="4.5" fill="#FBF8F4" stroke="{CELESTE}" stroke-width="2.5"/>'
        f'<path d="M12 40 C 20 44, 32 44, 40 40" fill="none" stroke="{SOL}" stroke-width="2"/>'
        f'<path d="M16 58 L14 64 L38 64 L36 58" fill="none" stroke="{CELESTE}" stroke-width="2.5"/>'
        "</g>"
    )


def andes(x0, x1, base):
    """A low silhouette of the Andes, Aconcagua the tallest peak."""
    peaks = [
        (0.0, 0),
        (0.07, 18),
        (0.13, 8),
        (0.21, 30),
        (0.28, 14),
        (0.36, 42),
        (0.42, 22),
        (0.5, 58),
        (0.56, 30),
        (0.63, 40),
        (0.7, 16),
        (0.78, 34),
        (0.85, 12),
        (0.92, 22),
        (1.0, 0),
    ]
    pts = " L".join(f"{x0 + (x1 - x0) * f:.0f} {base - h}" for f, h in peaks)
    return f'<path d="M{pts} Z" fill="{CELESTE}" opacity="0.14"/>'


def flor(cx, cy, r=7):
    """A fileteado flower: five gold petals around a celeste centre."""
    petals = "".join(
        f'<ellipse cx="{cx}" cy="{cy - r}" rx="{r * 0.45:.1f}" ry="{r * 0.8:.1f}" '
        f'transform="rotate({k * 72} {cx} {cy})"/>'
        for k in range(5)
    )
    return f'<g fill="{SOL}" opacity="0.8">{petals}<circle cx="{cx}" cy="{cy}" r="{r * 0.4:.1f}" fill="{CELESTE}"/></g>'


def svg(t):
    chips, x = [], 64
    for label in ["Español", "Deutsch", "Français", "Hinglish"]:
        c, w = chip(x, 268, label, t)
        chips.append(c)
        x += w + 10
    bank, bx = [], 762
    for label in ["me llamo", "soy", "mucho gusto"]:
        c, w = chip(bx, 264, label, t)
        bank.append(c)
        bx += w + 8
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="400" viewBox="0 0 1280 400" role="img" aria-label="Habla Hermano: talk your way from A0 to B1 with an AI conversation partner, with Argentine motifs: Sol de Mayo, fileteado, mate and the Andes">
  <defs>
    <clipPath id="card"><rect width="1280" height="400" rx="24"/></clipPath>
  </defs>
  <g clip-path="url(#card)">
    <rect width="1280" height="400" fill="{t["bg"]}"/>
    {sol_de_mayo(1214, 44, 34, 0.22)}
    <rect y="0" width="1280" height="10" fill="{CELESTE}"/>
    <rect y="390" width="1280" height="10" fill="{CELESTE}"/>
    {andes(250, 1030, 390)}
    {filete(34, 360)}
    {filete(1246, 370, flip=True)}
    {flor(214, 334)}
    {flor(1066, 344)}
    {mate(414, 258, 0.6)}
  </g>
  <g font-family="{FONT}">
    <rect x="64" y="84" width="64" height="64" rx="16" fill="{t["accent"]}"/>
    <svg x="80" y="100" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="{t["accent_text"]}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="{CHAT_ICON}"/></svg>
    <text x="64" y="208" font-size="58" font-weight="700" letter-spacing="-1.2" fill="{t["text"]}">Habla Hermano</text>
    <text x="66" y="246" font-size="22" font-weight="500" fill="{t["muted"]}">Talk your way from A0 to B1, with a big brother who never judges.</text>
    {"".join(chips)}

    <g>
      <rect x="742" y="110" width="290" height="96" rx="20" fill="{t["ai"]}" stroke="{t["ai_border"]}"/>
      <text x="766" y="148" font-size="19" font-weight="700" fill="{t["ai_text"]}">¡Hola! <tspan fill="{t["accent"]}">Me llamo</tspan> <tspan font-weight="500">Hermano.</tspan></text>
      <text x="766" y="178" font-size="19" font-weight="700" fill="{t["ai_text"]}">¡Mucho gusto!</text>
      <text x="762" y="250" font-size="12" font-weight="700" letter-spacing="1.4" fill="{t["muted"]}">WORD BANK</text>
      {"".join(bank)}
    </g>
  </g>
</svg>
'''


out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/assets")
out.mkdir(parents=True, exist_ok=True)
(out / "hero.svg").write_text(svg(AZULEJO), encoding="utf-8")
