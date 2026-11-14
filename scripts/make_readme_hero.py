"""Generate the README hero banner (light and dark) from the app's theme palettes.

Usage: python3 scripts/make_readme_hero.py   # writes docs/assets/hero-{light,dark}.svg
Colours match the Azulejo (light) and Terracotta (dark) themes in base.html.
"""

import sys
from pathlib import Path

THEMES = {
    "light": {  # Azulejo
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
    },
    "dark": {  # Terracotta
        "bg": "#1C1410",
        "bg2": "#2A1F18",
        "tile": "#E07A5F",
        "tile_op": "0.08",
        "text": "#F2E8DE",
        "muted": "#D4BC9E",
        "accent": "#E07A5F",
        "accent_text": "#1C1410",
        "ai": "#2A1F18",
        "ai_border": "#4A3B30",
        "ai_text": "#F2E8DE",
        "user": "#C85A3A",
        "user_text": "#FFFFFF",
        "chip": "rgba(224,122,95,0.16)",
        "chip_text": "#EE9A7F",
        "rule": "#4A3B30",
    },
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
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="400" viewBox="0 0 1280 400" role="img" aria-label="Habla Hermano: talk your way from A0 to B1 with an AI conversation partner">
  <defs>
    <pattern id="azulejo" width="48" height="48" patternUnits="userSpaceOnUse">
      <g fill="none" stroke="{t["tile"]}" stroke-width="1.4" opacity="{t["tile_op"]}">
        <rect x="0.7" y="0.7" width="46.6" height="46.6"/>
        <path d="M24 4 L44 24 L24 44 L4 24 Z"/>
        <circle cx="24" cy="24" r="7"/>
        <path d="M0 0 L10 10 M48 0 L38 10 M0 48 L10 38 M48 48 L38 38"/>
      </g>
    </pattern>
    <linearGradient id="fade" x1="0" x2="1" y1="0" y2="0">
      <stop offset="0" stop-color="{t["bg"]}" stop-opacity="1"/>
      <stop offset="0.38" stop-color="{t["bg"]}" stop-opacity="1"/>
      <stop offset="0.62" stop-color="{t["bg"]}" stop-opacity="0"/>
    </linearGradient>
  </defs>
  <rect width="1280" height="400" rx="24" fill="{t["bg"]}"/>
  <rect width="1280" height="400" rx="24" fill="url(#azulejo)"/>
  <rect width="1280" height="400" rx="24" fill="url(#fade)"/>
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


def svg_journey(t):
    """Option B: wordmark plus the A0 to B1 track (English share shrinks as you level up)."""
    steps = [
        ("A0", 80, "one word at a time"),
        ("A1", 50, "short sentences"),
        ("A2", 20, "past tense, stories"),
        ("B1", 5, "real conversations"),
    ]
    nodes = []
    for n, (lvl, english, note) in enumerate(steps):
        x = 700 + n * 150
        target = 100 - english
        nodes.append(
            f'<circle cx="{x}" cy="200" r="22" fill="{t["accent"] if n == 3 else t["ai"]}" '
            f'stroke="{t["accent"]}" stroke-width="2.5"/>'
            f'<text x="{x}" y="206" text-anchor="middle" font-size="15" font-weight="700" '
            f'fill="{t["accent_text"] if n == 3 else t["accent"]}">{lvl}</text>'
            f'<rect x="{x - 50}" y="244" width="100" height="8" rx="4" fill="{t["chip"]}"/>'
            f'<rect x="{x - 50}" y="244" width="{target}" height="8" rx="4" fill="{t["accent"]}"/>'
            f'<text x="{x}" y="276" text-anchor="middle" font-size="13" font-weight="600" fill="{t["text"]}">{target}% target</text>'
            f'<text x="{x}" y="296" text-anchor="middle" font-size="12" fill="{t["muted"]}">{note}</text>'
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="400" viewBox="0 0 1280 400" role="img" aria-label="Habla Hermano: from A0 to B1, the conversation shifts from mostly English to almost all target language">
  <rect width="1280" height="400" rx="24" fill="{t["bg"]}"/>
  <g font-family="{FONT}">
    <rect x="64" y="104" width="56" height="56" rx="14" fill="{t["accent"]}"/>
    <svg x="78" y="118" width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="{t["accent_text"]}" stroke-width="2.3" stroke-linecap="round" stroke-linejoin="round"><path d="{CHAT_ICON}"/></svg>
    <text x="64" y="220" font-size="54" font-weight="700" letter-spacing="-1.2" fill="{t["text"]}">Habla Hermano</text>
    <text x="66" y="256" font-size="20" font-weight="500" fill="{t["muted"]}">An AI conversation partner that grows with you.</text>
    <text x="66" y="296" font-size="15" font-weight="600" fill="{t["accent"]}">Español  ·  Deutsch  ·  Français  ·  Hinglish</text>
    <text x="700" y="130" font-size="12" font-weight="700" letter-spacing="1.6" fill="{t["muted"]}">YOUR PATH</text>
    <line x1="700" y1="200" x2="1150" y2="200" stroke="{t["rule"]}" stroke-width="3" stroke-dasharray="2 8" stroke-linecap="round"/>
    {"".join(nodes)}
  </g>
</svg>
'''


def svg_editorial(t):
    """Option C: type-led. Big wordmark over greetings in each language, a thin accent rule."""
    words = [
        ("Hola", 640, 96, 64),
        ("Hallo", 930, 150, 52),
        ("Bonjour", 760, 238, 60),
        ("Namaste", 1010, 300, 44),
        ("¿Qué tal?", 690, 356, 38),
        ("Salut", 1080, 92, 40),
    ]
    bg_words = "".join(
        f'<text x="{x}" y="{y}" font-size="{size}" font-weight="700" fill="{t["accent"]}" opacity="0.12">{w}</text>'
        for w, x, y, size in words
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="400" viewBox="0 0 1280 400" role="img" aria-label="Habla Hermano: an AI conversation partner for Spanish, German, French and Hinglish">
  <rect width="1280" height="400" rx="24" fill="{t["bg"]}"/>
  <g font-family="{FONT}">
    {bg_words}
    <text x="64" y="120" font-size="13" font-weight="700" letter-spacing="2.4" fill="{t["accent"]}">AI LANGUAGE TUTOR  ·  A0 TO B1</text>
    <text x="60" y="214" font-size="84" font-weight="800" letter-spacing="-2.5" fill="{t["text"]}">Habla</text>
    <text x="60" y="296" font-size="84" font-weight="800" letter-spacing="-2.5" fill="{t["text"]}">Hermano<tspan fill="{t["accent"]}">.</tspan></text>
    <rect x="64" y="322" width="72" height="4" rx="2" fill="{t["accent"]}"/>
    <text x="156" y="330" font-size="18" font-weight="500" fill="{t["muted"]}">Talk from message one. Scaffolding that fades as you grow.</text>
  </g>
</svg>
'''


VARIANTS = {"conversation": svg, "journey": svg_journey, "editorial": svg_editorial}


out = Path(sys.argv[1] if len(sys.argv) > 1 else "docs/assets")
for name, theme in THEMES.items():
    (out / f"hero-{name}.svg").write_text(svg(theme), encoding="utf-8")

# Design options, kept until one is picked for the README.
options = out / "hero-options"
options.mkdir(exist_ok=True)
for variant, render in VARIANTS.items():
    for name, theme in THEMES.items():
        (options / f"{variant}-{name}.svg").write_text(render(theme), encoding="utf-8")
print("written", out)
