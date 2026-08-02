"""
Generates hero.svg for the GitHub profile README. Version 9.

Left: the name in a two-line arcade bitmap font. Middle: a full 3x3 Rubik's
cube in glowing blue outlines that solves itself: individual layers rotate
in true 3D (U and R turns with easing), cells wrap around corners mid-turn,
and the whole cube drifts through a slow quarter-turn yaw so the loop is
seamless. Right: the isometric wave field. Background: twinkling pixel stars.

Face visibility is calibrated empirically against the known front faces at
identity, which fixes the v8 defect where the sign was inverted and the two
rear faces rendered through the front. Occlusion between the rotating layer
and the static block is computed per sample with convex-hull and depth tests.

Flat SVG shapes with SMIL and CSS animation only. No scripts, no external
resources. Re-run after changing any constant in CONFIG.
"""

import math

CONFIG = {
    "canvas_width": 1200,
    "canvas_height": 300,
    # Wave field
    "columns": 10,
    "rows": 5,
    "tile_half_width": 20,
    "tile_half_height": 10,
    "origin_x": 860,
    "origin_y": 126,
    "min_block_height": 4,
    "max_block_height": 34,
    "wave_period_seconds": 6.0,
    "float_distance": 6,
    # Rubik's cube
    "cube_centre_x": 585,
    "cube_centre_y": 170,
    "cube_scale": 30.0,
    "turn_seconds": 1.1,
    "pause_seconds": 0.5,
    "turn_samples": 16,
    "pause_samples": 4,
    # Pixel font
    "pixel_cell": 6,
    "name_x": 70,
    "name_y": 58,
    "name_line_gap": 10,
}

BACKGROUND = "#0d1117"
ACCENT = "#00e5ff"
TRACE = "#1a5f6e"
TEXT_BRIGHT = "#e6edf3"
TEXT_DIM = "#7d8590"

TIERS = [
    ("#132f36", "#0d2228", "#081a1f"),
    ("#175160", "#103a45", "#0b2a32"),
    ("#1a7488", "#135362", "#0d3c47"),
    ("#00b8cc", "#008799", "#00616e"),
    ("#00e5ff", "#00a8bd", "#007487"),
]

CUBE_STROKE_DARK = (10, 58, 74)
CUBE_STROKE_BRIGHT = (0, 229, 255)
CUBE_BODY_DARK = (7, 15, 19)
CUBE_BODY_LIT = (26, 49, 60)
LIGHT_3D = (-0.55, 0.62, -0.45)

PIXEL_FONT = {
    "A": [0x30, 0x78, 0xCC, 0xCC, 0xFC, 0xCC, 0xCC],
    "D": [0xF8, 0x6C, 0x66, 0x66, 0x66, 0x6C, 0xF8],
    "H": [0xCC, 0xCC, 0xCC, 0xFC, 0xCC, 0xCC, 0xCC],
    "I": [0x78, 0x30, 0x30, 0x30, 0x30, 0x30, 0x78],
    "M": [0xC6, 0xEE, 0xFE, 0xFE, 0xD6, 0xC6, 0xC6],
    "R": [0xFC, 0x66, 0x66, 0x7C, 0x6C, 0x66, 0xE6],
    "S": [0x78, 0xCC, 0xE0, 0x70, 0x1C, 0xCC, 0x78],
    "T": [0xFC, 0xB4, 0x30, 0x30, 0x30, 0x30, 0x78],
    "Y": [0xCC, 0xCC, 0xCC, 0x78, 0x30, 0x30, 0x78],
}


# ------------------------------------------------------------- 3D primitives

def rotate_axis(axis, angle, point):
    x, y, z = point
    c = math.cos(angle)
    s = math.sin(angle)
    if axis == "y":
        return (x * c + z * s, y, -x * s + z * c)
    if axis == "x":
        return (x, y * c - z * s, y * s + z * c)
    raise ValueError(axis)


def project(point):
    x, y, z = point
    s = CONFIG["cube_scale"]
    sx = CONFIG["cube_centre_x"] + (x - z) * s
    sy = CONFIG["cube_centre_y"] + (x + z) * s * 0.5 - y * s * 1.1
    return sx, sy


def depth(point):
    """Larger = nearer the viewer for this projection."""
    x, y, z = point
    return x + z + y * 0.909


def signed_area(points):
    area = 0.0
    for index in range(len(points)):
        x1, y1 = points[index]
        x2, y2 = points[(index + 1) % len(points)]
        area += x1 * y2 - x2 * y1
    return area / 2.0


def points_string(points):
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in points)


def lerp3(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def shade(normal, dark, bright, floor):
    length = math.sqrt(sum(component * component for component in normal))
    nx, ny, nz = (component / length for component in normal)
    ll = math.sqrt(sum(component * component for component in LIGHT_3D))
    lx, ly, lz = (component / ll for component in LIGHT_3D)
    lambert = max(0.0, nx * lx + ny * ly + nz * lz)
    eased = floor + (1.0 - floor) * lambert
    r = round(dark[0] + (bright[0] - dark[0]) * eased)
    g = round(dark[1] + (bright[1] - dark[1]) * eased)
    b = round(dark[2] + (bright[2] - dark[2]) * eased)
    return f"#{r:02x}{g:02x}{b:02x}"


def convex_hull(points):
    pts = sorted(set(points))
    if len(pts) <= 2:
        return pts
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def inside_hull(point, hull):
    if len(hull) < 3:
        return False
    for index in range(len(hull)):
        a = hull[index]
        b = hull[(index + 1) % len(hull)]
        cross = (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0])
        if cross < 0:
            return False
    return True


# ------------------------------------------------------- faces, cells, boxes

def box_faces(minimum, maximum):
    """Six faces of an axis-aligned box, each with its outward normal.
    The corner pattern per normal direction is fixed, so the calibrated
    orientation map applies to every box built here."""
    x0, y0, z0 = minimum
    x1, y1, z1 = maximum
    return [
        {"normal": (1, 0, 0), "corners": [(x1, y1, z0), (x1, y1, z1), (x1, y0, z1), (x1, y0, z0)]},
        {"normal": (-1, 0, 0), "corners": [(x0, y1, z1), (x0, y1, z0), (x0, y0, z0), (x0, y0, z1)]},
        {"normal": (0, 1, 0), "corners": [(x1, y1, z0), (x1, y1, z1), (x0, y1, z1), (x0, y1, z0)]},
        {"normal": (0, -1, 0), "corners": [(x1, y0, z1), (x1, y0, z0), (x0, y0, z0), (x0, y0, z1)]},
        {"normal": (0, 0, 1), "corners": [(x1, y1, z1), (x0, y1, z1), (x0, y0, z1), (x1, y0, z1)]},
        {"normal": (0, 0, -1), "corners": [(x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0)]},
    ]


def calibrate_orientation():
    """Empirical fix for the v8 inversion: at identity, the front faces of
    this projection are +x, +z, and +y. The orientation factor per canonical
    normal makes (factor * signed_area) > 0 mean front-facing, for any rigid
    rotation of a face drawn with the same corner pattern."""
    front_normals = {(1, 0, 0), (0, 1, 0), (0, 0, 1)}
    orientation = {}
    for face in box_faces((-1, -1, -1), (1, 1, 1)):
        area = signed_area([project(corner) for corner in face["corners"]])
        sign = 1 if area > 0 else -1
        orientation[face["normal"]] = sign if face["normal"] in front_normals else -sign
    return orientation


ORIENTATION = calibrate_orientation()


def face_is_front(projected, canonical_normal):
    return ORIENTATION[canonical_normal] * signed_area(projected) > 0.5


def build_cells():
    """54 outlined cells covering all six canonical faces. The bottom face
    is hidden at rest but its cells rotate into view during R turns; without
    them the column arriving from below has no outlines until the snap."""
    inset = 0.84
    cells = []
    for face in box_faces((-1, -1, -1), (1, 1, 1)):
        c0, c1, c2, c3 = face["corners"]
        for i in range(3):
            for j in range(3):
                u0, u1 = i / 3.0, (i + 1) / 3.0
                v0, v1 = j / 3.0, (j + 1) / 3.0
                uc, vc = (u0 + u1) / 2.0, (v0 + v1) / 2.0
                u0 = uc + (u0 - uc) * inset
                u1 = uc + (u1 - uc) * inset
                v0 = vc + (v0 - vc) * inset
                v1 = vc + (v1 - vc) * inset
                def at(u, v):
                    top = lerp3(c0, c1, u)
                    bottom = lerp3(c3, c2, u)
                    return lerp3(top, bottom, v)
                corners = [at(u0, v0), at(u1, v0), at(u1, v1), at(u0, v1)]
                centre = at(uc, vc)
                cells.append({"corners": corners, "centre": centre,
                              "normal": face["normal"]})
    return cells


# ------------------------------------------------------------ move timeline

MOVES = [
    {"axis": "y", "direction": 1, "layer": lambda centre: centre[1] > 1 / 3},
    {"axis": "x", "direction": -1, "layer": lambda centre: centre[0] > 1 / 3},
    {"axis": "y", "direction": -1, "layer": lambda centre: centre[1] > 1 / 3},
    {"axis": "x", "direction": 1, "layer": lambda centre: centre[0] > 1 / 3},
]

SLABS = {
    "y": {"rotating": ((-1, 1 / 3, -1), (1, 1, 1)), "static": ((-1, -1, -1), (1, 1 / 3, 1))},
    "x": {"rotating": ((1 / 3, -1, -1), (1, 1, 1)), "static": ((-1, -1, -1), (1 / 3, 1, 1))},
}


def smoothstep(p):
    return p * p * (3.0 - 2.0 * p)


def build_timeline():
    """Sample schedule over one loop: four windows of pause + eased turn,
    with near-duplicate samples at window boundaries so the slab
    decomposition can switch without a visible morph. The whole cube also
    yaws 90 degrees across the loop, so the end is congruent to the start."""
    window = CONFIG["pause_seconds"] + CONFIG["turn_seconds"]
    total = window * len(MOVES)
    epsilon = 0.0005
    samples = []
    for index, move in enumerate(MOVES):
        window_start = index * window
        if index > 0:
            samples.append((window_start / total + epsilon, index, 0.0))
        for p in range(CONFIG["pause_samples"]):
            t = window_start + CONFIG["pause_seconds"] * p / CONFIG["pause_samples"]
            samples.append((t / total, index, 0.0))
        for p in range(CONFIG["turn_samples"] + 1):
            phase = p / CONFIG["turn_samples"]
            t = window_start + CONFIG["pause_seconds"] + CONFIG["turn_seconds"] * phase
            time_norm = min(t / total, 1.0)
            samples.append((time_norm, index, smoothstep(phase)))
    deduped = []
    for sample in samples:
        if deduped and sample[0] <= deduped[-1][0]:
            continue
        deduped.append(sample)
    if deduped[-1][0] < 1.0:
        deduped.append((1.0, len(MOVES) - 1, 1.0))
    return deduped, total


def transform_for(move, turn_progress, yaw, centre):
    """Returns the corner transform for a cell with the given canonical
    centre during this sample."""
    in_layer = move["layer"](centre)
    angle = move["direction"] * (math.pi / 2) * turn_progress
    def apply(point):
        if in_layer:
            point = rotate_axis(move["axis"], angle, point)
        return rotate_axis("y", yaw, point)
    return apply, in_layer


def box_corners(minimum, maximum):
    x0, y0, z0 = minimum
    x1, y1, z1 = maximum
    return [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]


def box_centre(minimum, maximum):
    return tuple((minimum[axis] + maximum[axis]) / 2.0 for axis in range(3))


def build_solving_cube():
    timeline, total_seconds = build_timeline()
    key_times = ";".join(f"{sample[0]:.4f}" for sample in timeline)
    cells = build_cells()

    body_slots = {"static": [[] for _ in range(6)], "rotating": [[] for _ in range(6)]}
    body_fills = {"static": [[] for _ in range(6)], "rotating": [[] for _ in range(6)]}
    cell_points = [[] for _ in cells]
    cell_opacity = [[] for _ in cells]
    cell_strokes = [[] for _ in cells]

    for time_norm, move_index, turn_progress in timeline:
        move = MOVES[move_index]
        yaw = (math.pi / 2) * time_norm
        slabs = SLABS[move["axis"]]
        turning = 0.02 < turn_progress < 0.98

        transforms = {}
        for role in ("static", "rotating"):
            minimum, maximum = slabs[role]
            rotate_slab = role == "rotating"
            angle = move["direction"] * (math.pi / 2) * turn_progress
            def slab_apply(point, rotate_slab=rotate_slab, angle=angle, axis=move["axis"]):
                if rotate_slab:
                    point = rotate_axis(axis, angle, point)
                return rotate_axis("y", yaw, point)
            transforms[role] = slab_apply

        hulls = {}
        centre_depths = {}
        for role in ("static", "rotating"):
            minimum, maximum = slabs[role]
            world = [transforms[role](corner) for corner in box_corners(minimum, maximum)]
            hulls[role] = convex_hull([tuple(round(v, 2) for v in project(p)) for p in world])
            centre_depths[role] = depth(transforms[role](box_centre(minimum, maximum)))

        for role in ("static", "rotating"):
            minimum, maximum = slabs[role]
            for face_index, face in enumerate(box_faces(minimum, maximum)):
                projected = [project(transforms[role](corner)) for corner in face["corners"]]
                if face_is_front(projected, face["normal"]):
                    body_slots[role][face_index].append(points_string(projected))
                else:
                    body_slots[role][face_index].append(points_string([projected[0]] * 4))
                world_normal = transforms[role](face["normal"])
                origin = transforms[role]((0, 0, 0))
                normal_vec = tuple(world_normal[axis] - origin[axis] for axis in range(3))
                body_fills[role][face_index].append(
                    shade(normal_vec, CUBE_BODY_DARK, CUBE_BODY_LIT, 0.12))

        for cell_index, cell in enumerate(cells):
            apply, in_layer = transform_for(move, turn_progress, yaw, cell["centre"])
            world_corners = [apply(corner) for corner in cell["corners"]]
            projected = [project(corner) for corner in world_corners]
            world_centre = apply(cell["centre"])
            visible = face_is_front(projected, cell["normal"])

            if visible and turning:
                other = "static" if in_layer else "rotating"
                screen_centre = project(world_centre)
                if inside_hull(screen_centre, hulls[other]):
                    if depth(world_centre) < centre_depths[other]:
                        visible = False

            if visible:
                cell_points[cell_index].append(points_string(projected))
                cell_opacity[cell_index].append("1")
            else:
                cell_points[cell_index].append(points_string([projected[0]] * 4))
                cell_opacity[cell_index].append("0")

            origin = apply((0, 0, 0))
            world_normal = apply(cell["normal"])
            normal_vec = tuple(world_normal[axis] - origin[axis] for axis in range(3))
            cell_strokes[cell_index].append(
                shade(normal_vec, CUBE_STROKE_DARK, CUBE_STROKE_BRIGHT, 0.22))

    duration = total_seconds

    def animate(attribute, frames):
        return (
            f'<animate attributeName="{attribute}" dur="{duration}s" repeatCount="indefinite" '
            f'calcMode="linear" keyTimes="{key_times}" values="{";".join(frames)}"/>'
        )

    parts = []
    for role in ("static", "rotating"):
        for face_index in range(6):
            frames = body_slots[role][face_index]
            fills = body_fills[role][face_index]
            parts.append(
                f'<polygon points="{frames[0]}" fill="{fills[0]}">'
                f"{animate('points', frames)}{animate('fill', fills)}</polygon>"
            )
    for cell_index in range(len(cells)):
        parts.append(
            f'<polygon points="{cell_points[cell_index][0]}" fill="none" '
            f'stroke="{cell_strokes[cell_index][0]}" stroke-width="1.6" '
            f'stroke-linejoin="round" stroke-opacity="{cell_opacity[cell_index][0]}">'
            f"{animate('points', cell_points[cell_index])}"
            f"{animate('stroke', cell_strokes[cell_index])}"
            f"{animate('stroke-opacity', cell_opacity[cell_index])}"
            f"</polygon>"
        )
    return '<g class="bob">' + "".join(parts) + "</g>", timeline


def cube_screen_bounds():
    timeline, _ = build_timeline()
    xs, ys = [], []
    for time_norm, move_index, turn_progress in timeline:
        move = MOVES[move_index]
        yaw = (math.pi / 2) * time_norm
        for role, (minimum, maximum) in SLABS[move["axis"]].items():
            angle = move["direction"] * (math.pi / 2) * turn_progress
            for corner in box_corners(minimum, maximum):
                point = corner
                if role == "rotating":
                    point = rotate_axis(move["axis"], angle, point)
                point = rotate_axis("y", yaw, point)
                sx, sy = project(point)
                xs.append(sx)
                ys.append(sy)
    return min(xs), max(xs), min(ys), max(ys)


def pseudo_random(column, row):
    seed = math.sin(column * 127.1 + row * 311.7) * 43758.5453
    return seed - math.floor(seed)


def block_height(column, row):
    ridge = 10.0 * math.sin(column * 0.55 + row * 0.35)
    swell = 7.0 * math.sin(column * 0.22)
    jitter = 11.0 * pseudo_random(column, row)
    raw = 7.0 + ridge + swell + jitter
    if raw < CONFIG["min_block_height"]:
        return CONFIG["min_block_height"]
    if raw > CONFIG["max_block_height"]:
        return CONFIG["max_block_height"]
    return raw


def tier_for_height(height):
    span = CONFIG["max_block_height"] - CONFIG["min_block_height"]
    ratio = (height - CONFIG["min_block_height"]) / span
    index = int(ratio * len(TIERS))
    if index >= len(TIERS):
        index = len(TIERS) - 1
    return TIERS[index]


def build_block(column, row):
    half_width = CONFIG["tile_half_width"]
    half_height = CONFIG["tile_half_height"]

    centre_x = CONFIG["origin_x"] + (column - row) * half_width
    ground_y = CONFIG["origin_y"] + (column + row) * half_height
    height = block_height(column, row)
    top_y = ground_y - height

    top_colour, right_colour, left_colour = tier_for_height(height)

    top_face = (
        f"{centre_x},{top_y:.1f} {centre_x + half_width},{top_y + half_height:.1f} "
        f"{centre_x},{top_y + half_height * 2:.1f} {centre_x - half_width},{top_y + half_height:.1f}"
    )
    left_face = (
        f"{centre_x - half_width},{top_y + half_height:.1f} {centre_x},{top_y + half_height * 2:.1f} "
        f"{centre_x},{ground_y + half_height * 2:.1f} {centre_x - half_width},{ground_y + half_height:.1f}"
    )
    right_face = (
        f"{centre_x},{top_y + half_height * 2:.1f} {centre_x + half_width},{top_y + half_height:.1f} "
        f"{centre_x + half_width},{ground_y + half_height:.1f} {centre_x},{ground_y + half_height * 2:.1f}"
    )

    period = CONFIG["wave_period_seconds"]
    delay = -((column * 0.28) + (row * 0.18)) % period

    return (
        f'<g class="blk" style="animation-delay:-{delay:.2f}s">'
        f'<polygon points="{left_face}" fill="{left_colour}"/>'
        f'<polygon points="{right_face}" fill="{right_colour}"/>'
        f'<polygon points="{top_face}" fill="{top_colour}"/>'
        f"</g>"
    )


def build_field():
    blocks = []
    for depth in range(CONFIG["columns"] + CONFIG["rows"] - 1):
        for column in range(CONFIG["columns"]):
            row = depth - column
            if 0 <= row < CONFIG["rows"]:
                blocks.append(build_block(column, row))
    return "".join(blocks)


# ---------------------------------------------------------------- text layer


def build_starfield():
    """Pixel stars scattered across the background: tiny squares, four-arm
    plus glyphs, and small diamonds, each with its own slow twinkle phase.
    Deterministic placement so the field is stable between runs."""
    parts = []
    star_count = 30
    for index in range(star_count):
        u = pseudo_random(index, 7)
        v = pseudo_random(index, 13)
        x = 30 + u * 1140
        y = 18 + v * 250
        kind = index % 3
        accent = pseudo_random(index, 29) > 0.8
        colour = ACCENT if accent else TRACE
        duration = 2.6 + pseudo_random(index, 17) * 3.0
        delay = pseudo_random(index, 23) * duration
        style = f'style="animation-duration:{duration:.1f}s;animation-delay:-{delay:.1f}s"'
        if kind == 0:
            size = 2 if pseudo_random(index, 31) < 0.6 else 3
            parts.append(
                f'<rect class="tw" x="{x:.0f}" y="{y:.0f}" width="{size}" height="{size}" '
                f'fill="{colour}" {style}/>'
            )
        elif kind == 1:
            parts.append(
                f'<path class="tw" d="M{x - 4:.0f},{y:.0f} H{x + 4:.0f} M{x:.0f},{y - 4:.0f} V{y + 4:.0f}" '
                f'stroke="{colour}" stroke-width="1.2" fill="none" {style}/>'
            )
        else:
            parts.append(
                f'<path class="tw" d="M{x:.0f},{y - 4:.0f} L{x + 4:.0f},{y:.0f} L{x:.0f},{y + 4:.0f} '
                f'L{x - 4:.0f},{y:.0f} Z" fill="none" stroke="{colour}" stroke-width="1.2" {style}/>'
            )
    return "".join(parts)


def glyph_rows(character):
    return PIXEL_FONT[character]


def build_pixel_line(text, start_x, start_y):
    """Draws one line of arcade text, merging horizontal pixel runs so the
    letterforms are solid strokes rather than separated squares."""
    cell = CONFIG["pixel_cell"]
    advance = cell * 9
    parts = []
    cursor_x = start_x
    for character in text:
        rows = glyph_rows(character)
        for row_index, row_bits in enumerate(rows):
            col = 0
            while col < 8:
                if row_bits & (0x80 >> col):
                    run_start = col
                    while col < 8 and row_bits & (0x80 >> col):
                        col += 1
                    parts.append(
                        f'<rect x="{cursor_x + run_start * cell}" '
                        f'y="{start_y + row_index * cell}" '
                        f'width="{(col - run_start) * cell}" height="{cell}" '
                        f'fill="{TEXT_BRIGHT}"/>'
                    )
                else:
                    col += 1
        cursor_x += advance
    return "".join(parts), cursor_x - advance + 8 * cell


def build_baseline():
    y = 284
    parts = [
        f'<line x1="70" y1="{y}" x2="1130" y2="{y}" stroke="{TRACE}" stroke-width="1" opacity="0.55"/>'
    ]
    for x in range(70, 1131, 106):
        parts.append(
            f'<line x1="{x}" y1="{y - 4}" x2="{x}" y2="{y + 4}" '
            f'stroke="{TRACE}" stroke-width="1" opacity="0.55"/>'
        )
    parts.append(f'<rect x="66" y="{y - 3}" width="6" height="6" fill="{ACCENT}" opacity="0.8"/>')
    parts.append(
        f'<rect x="1126" y="{y - 3}" width="6" height="6" fill="none" '
        f'stroke="{ACCENT}" stroke-width="1.2" opacity="0.8"/>'
    )
    return "".join(parts)


def build_styles():
    return (
        "<style>"
        f".blk {{ animation: swell {CONFIG['wave_period_seconds']}s cubic-bezier(0.45, 0, 0.55, 1) infinite; }}"
        ".tw { animation-name: tw; animation-timing-function: ease-in-out; animation-iteration-count: infinite; }"
        "@keyframes tw { 0%, 100% { opacity: 0.15; } 50% { opacity: 0.75; } }"
        ".bob { animation: bob 5.5s ease-in-out infinite; }"
        "@keyframes bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-5px); } }"
        f"@keyframes swell {{ 0%, 100% {{ transform: translateY(0); }} 50% {{ transform: translateY(-{CONFIG['float_distance']}px); }} }}"
        "@media (prefers-reduced-motion: reduce) { .blk, .tw, .bob { animation: none; } }"
        "</style>"
    )


def build_text_layer(name_end_x):
    cell = CONFIG["pixel_cell"]
    line_height = 7 * cell
    second_line_bottom = CONFIG["name_y"] + line_height + CONFIG["name_line_gap"] + line_height
    rule_y = second_line_bottom + 16
    tagline_y = rule_y + 32
    detail_y = tagline_y + 26
    return (
        f'<line x1="72" y1="{rule_y}" x2="{name_end_x}" y2="{rule_y}" '
        f'stroke="{ACCENT}" stroke-width="1.5" opacity="0.6"/>'
        f'<text x="72" y="{tagline_y}" font-family="Consolas, \'Cascadia Mono\', Menlo, monospace" '
        f'font-size="14" letter-spacing="1" fill="{TEXT_DIM}">Toronto · Computer Science @ TMU</text>'
        f'<text x="72" y="{detail_y}" font-family="Consolas, \'Cascadia Mono\', Menlo, monospace" '
        f'font-size="12.5" letter-spacing="1" fill="{TEXT_DIM}" opacity="0.8">'
        f"Windows internals · web · game systems</text>"
    )


def build_svg():
    width = CONFIG["canvas_width"]
    height = CONFIG["canvas_height"]

    cell = CONFIG["pixel_cell"]
    line_height = 7 * cell
    line_one, end_one = build_pixel_line("ADITYA", CONFIG["name_x"], CONFIG["name_y"])
    line_two, end_two = build_pixel_line(
        "SHARMA", CONFIG["name_x"], CONFIG["name_y"] + line_height + CONFIG["name_line_gap"]
    )
    name_end_x = max(end_one, end_two)

    cube_markup, _ = build_solving_cube()

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'width="100%" role="img" aria-label="Aditya Sharma">'
        f"<title>Aditya Sharma</title>"
        f"{build_styles()}"
        f'<rect width="{width}" height="{height}" fill="{BACKGROUND}"/>'
        f"{build_starfield()}"
        f"{build_field()}"
        f"{cube_markup}"
        f"{build_baseline()}"
        f"{line_one}{line_two}"
        f"{build_text_layer(name_end_x)}"
        f"</svg>"
    )


if __name__ == "__main__":
    # The orientation calibration must mark exactly +x, +z, +y as front at rest.
    identity_front = set()
    for face in box_faces((-1, -1, -1), (1, 1, 1)):
        projected = [project(corner) for corner in face["corners"]]
        if face_is_front(projected, face["normal"]):
            identity_front.add(face["normal"])
    assert identity_front == {(1, 0, 0), (0, 1, 0), (0, 0, 1)}, identity_front

    left, right, top, bottom = cube_screen_bounds()
    assert bottom < 282, f"cube bottom {bottom:.0f} hits the baseline"
    assert left > 390, f"cube left {left:.0f} hits the name column"
    assert right < 756, f"cube right {right:.0f} hits the wave field"

    import os

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hero.svg")
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write(build_svg())
    print(f"cube screen bounds: x {left:.0f}..{right:.0f}, y {top:.0f}..{bottom:.0f}")
    print(f"wrote {output_path}")
