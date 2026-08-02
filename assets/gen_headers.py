"""
Generates the section header bars for the GitHub profile README.

Each bar is a full-width dark chip with the section title set in the same
8x8 arcade bitmap font as the hero name, a filled cyan accent square on the
left, a thin trace line filling the middle, and a hollow accent square on
the right, echoing the hero's ground line. The dark chip background means
the bars read correctly on both GitHub light and dark themes.

Self-contained on purpose. Re-run after changing TITLES or any constant.
"""

BACKGROUND = "#0d1117"
ACCENT = "#00e5ff"
TRACE = "#1a5f6e"
TEXT_BRIGHT = "#e6edf3"

BAR_WIDTH = 1200
BAR_HEIGHT = 44
CELL = 4

TITLES = ["FEATURED", "NATIVE", "WEB", "GAMES", "STACK"]

# Classic 8x8 arcade letterforms (IBM-style), 8 columns x 7 used rows.
PIXEL_FONT = {
    "A": [0x30, 0x78, 0xCC, 0xCC, 0xFC, 0xCC, 0xCC],
    "B": [0xFC, 0x66, 0x66, 0x7C, 0x66, 0x66, 0xFC],
    "C": [0x3C, 0x66, 0xC0, 0xC0, 0xC0, 0x66, 0x3C],
    "D": [0xF8, 0x6C, 0x66, 0x66, 0x66, 0x6C, 0xF8],
    "E": [0xFE, 0x62, 0x68, 0x78, 0x68, 0x62, 0xFE],
    "F": [0xFE, 0x62, 0x68, 0x78, 0x68, 0x60, 0xF0],
    "G": [0x3C, 0x66, 0xC0, 0xC0, 0xCE, 0x66, 0x3E],
    "K": [0xE6, 0x66, 0x6C, 0x78, 0x6C, 0x66, 0xE6],
    "M": [0xC6, 0xEE, 0xFE, 0xFE, 0xD6, 0xC6, 0xC6],
    "N": [0xC6, 0xE6, 0xF6, 0xDE, 0xCE, 0xC6, 0xC6],
    "R": [0xFC, 0x66, 0x66, 0x7C, 0x6C, 0x66, 0xE6],
    "S": [0x78, 0xCC, 0xE0, 0x70, 0x1C, 0xCC, 0x78],
    "T": [0xFC, 0xB4, 0x30, 0x30, 0x30, 0x30, 0x78],
    "U": [0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0x78],
    "V": [0xCC, 0xCC, 0xCC, 0xCC, 0xCC, 0x78, 0x30],
    "W": [0xC6, 0xC6, 0xC6, 0xD6, 0xFE, 0xEE, 0xC6],
    "I": [0x78, 0x30, 0x30, 0x30, 0x30, 0x30, 0x78],
}


def build_pixel_text(text, start_x, start_y):
    """One line of arcade text with horizontal pixel runs merged into solid
    rects, so the letterforms are strokes rather than separated squares."""
    advance = CELL * 9
    parts = []
    cursor_x = start_x
    for character in text:
        rows = PIXEL_FONT[character]
        for row_index, row_bits in enumerate(rows):
            col = 0
            while col < 8:
                if row_bits & (0x80 >> col):
                    run_start = col
                    while col < 8 and row_bits & (0x80 >> col):
                        col += 1
                    parts.append(
                        f'<rect x="{cursor_x + run_start * CELL}" '
                        f'y="{start_y + row_index * CELL}" '
                        f'width="{(col - run_start) * CELL}" height="{CELL}" '
                        f'fill="{TEXT_BRIGHT}"/>'
                    )
                else:
                    col += 1
        cursor_x += advance
    return "".join(parts), cursor_x - advance + 8 * CELL


def build_bar(title):
    text_height = 7 * CELL
    text_y = (BAR_HEIGHT - text_height) // 2
    pixels, text_end = build_pixel_text(title, 44, text_y)
    line_y = BAR_HEIGHT // 2
    line_start = text_end + 24
    line_end = BAR_WIDTH - 52
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {BAR_WIDTH} {BAR_HEIGHT}" '
        f'width="100%" role="img" aria-label="{title.title()}">'
        f"<title>{title.title()}</title>"
        f'<rect width="{BAR_WIDTH}" height="{BAR_HEIGHT}" rx="8" fill="{BACKGROUND}"/>'
        f'<rect x="20" y="{line_y - 4}" width="8" height="8" fill="{ACCENT}" opacity="0.9"/>'
        f"{pixels}"
        f'<line x1="{line_start}" y1="{line_y}" x2="{line_end}" y2="{line_y}" '
        f'stroke="{TRACE}" stroke-width="1" opacity="0.7"/>'
        f'<rect x="{BAR_WIDTH - 36}" y="{line_y - 4}" width="8" height="8" fill="none" '
        f'stroke="{ACCENT}" stroke-width="1.2" opacity="0.9"/>'
        f"</svg>"
    )


if __name__ == "__main__":
    import os

    out_dir = os.path.dirname(os.path.abspath(__file__))
    for title in TITLES:
        for character in title:
            if character not in PIXEL_FONT:
                raise SystemExit(f"missing glyph: {character}")
        path = os.path.join(out_dir, f"h-{title.lower()}.svg")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(build_bar(title))
        print(f"wrote {path}")
