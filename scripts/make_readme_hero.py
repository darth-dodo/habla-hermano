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


def svg(t):
    chips, x = [], 64
    for label in ["Español", "Deutsch", "Français", "Hinglish"]:
        c, w = chip(x, 268, label, t)
        chips.append(c)
        x += w + 10
    bank, bx = [], 762
    for label in ["me llamo", "soy", "mucho gusto"]:
        c, w = chip(bx, 228, label, t)
        bank.append(c)
        bx += w + 8
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="400" viewBox="0 0 1280 400" role="img" aria-label="Habla Hermano: talk your way from A0 to B1 with an AI conversation partner, with a Sol de Mayo and fileteado ornaments">
  <defs>
    <clipPath id="card"><rect width="1280" height="400" rx="24"/></clipPath>
  </defs>
  <g clip-path="url(#card)">
    <rect width="1280" height="400" fill="{t["bg"]}"/>
    {sol_de_mayo(1214, 44, 34, 0.22)}
    <rect y="0" width="1280" height="10" fill="{CELESTE}"/>
    <rect y="390" width="1280" height="10" fill="{CELESTE}"/>
    {filete(34, 360)}
    {filete(1246, 370, flip=True)}
  </g>
  <g font-family="{FONT}">
    <rect x="64" y="84" width="64" height="64" rx="16" fill="{t["accent"]}"/>
    <svg x="80" y="100" width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="{t["accent_text"]}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="{CHAT_ICON}"/></svg>
    <text x="64" y="208" font-size="58" font-weight="700" letter-spacing="-1.2" fill="{t["text"]}">Habla Hermano</text>
    <text x="66" y="246" font-size="22" font-weight="500" fill="{t["muted"]}">Talk your way from A0 to B1, with a big brother who never judges.</text>
    {"".join(chips)}

    <g>
      <rect x="742" y="76" width="420" height="96" rx="20" fill="{t["ai"]}" stroke="{t["ai_border"]}"/>
      <text x="766" y="114" font-size="19" font-weight="700" fill="{t["ai_text"]}">¡Hola! <tspan font-weight="500">I'm Hermano. How do you</tspan></text>
      <text x="766" y="144" font-size="19" font-weight="500" fill="{t["ai_text"]}">say your name? Try <tspan font-weight="700" fill="{t["accent"]}">Me llamo...</tspan></text>
      <text x="762" y="214" font-size="12" font-weight="700" letter-spacing="1.4" fill="{t["muted"]}">WORD BANK</text>
      {"".join(bank)}
      <rect x="852" y="284" width="310" height="54" rx="20" fill="{t["user"]}"/>
      <text x="1007" y="318" text-anchor="middle" font-size="19" font-weight="600" fill="{t["user_text"]}">Me llamo Ana. ¡Mucho gusto!</text>
    </g>
  </g>
</svg>
'''


out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/assets")
out.mkdir(parents=True, exist_ok=True)
(out / "hero.svg").write_text(svg(AZULEJO), encoding="utf-8")
