#!/usr/bin/env python3
"""
Builds the SVGs in assets/ that the profile README shows.

Everything is drawn in the same language as arshchatrath.me: the same ink,
paper and teal, the same three fonts (Bricolage Grotesque, Schibsted Grotesk,
Fragment Mono, all SIL OFL), the same laser-engraved name and the same cat.

GitHub shows README images in a sandbox that can't load anything else, so
each SVG carries its own font subset and all motion is SMIL or CSS keyframes.

    pip install fonttools brotli skia-pathops uharfbuzz pillow
    python build/build.py
"""

import base64
import io
import math
import pathlib
from xml.sax.saxutils import escape

import pathops
import uharfbuzz as hb
from fontTools import subset
from fontTools.pens.basePen import BasePen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "assets"

INK = "#0a0a0a"
PAPER = "#f5f0e8"
TEAL = "#00B4D8"
W = 880  # every card is drawn at this width and scaled by GitHub
PAD = 40

# The site's arrival curve (expo.out), for CSS animations.
EASE_OUT = "cubic-bezier(0.16, 1, 0.3, 1)"


def num(v):
    s = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


# ── Fonts ────────────────────────────────────────────────────────────────────


class Face:
    """One font instance: measures with HarfBuzz, embeds as a woff2 subset."""

    def __init__(self, family, file, **axes):
        font = TTFont(HERE / "fonts" / file)
        if axes:
            font = instantiateVariableFont(font, axes)
        font.flavor = None
        font.recalcTimestamp = False
        buf = io.BytesIO()
        font.save(buf)
        self.data = buf.getvalue()
        self.family = family
        self.font = TTFont(io.BytesIO(self.data))
        self.upm = self.font["head"].unitsPerEm
        self.cmap = self.font.getBestCmap()
        self.hb = hb.Font(hb.Face(self.data))

    def shape(self, text):
        buf = hb.Buffer()
        buf.add_str(text)
        buf.guess_segment_properties()
        hb.shape(self.hb, buf, {"kern": True, "liga": True})
        return buf.glyph_infos, buf.glyph_positions

    def width(self, text, size, ls=0.0):
        _, pos = self.shape(text)
        return sum(p.x_advance for p in pos) * size / self.upm + ls * len(text)

    def woff2(self, chars):
        font = TTFont(io.BytesIO(self.data))
        opts = subset.Options()
        opts.flavor = "woff2"
        opts.layout_features = ["kern", "liga"]
        opts.name_IDs = []
        opts.notdef_outline = True
        sub = subset.Subsetter(opts)
        sub.populate(text=chars)
        sub.subset(font)
        out = io.BytesIO()
        font.flavor = "woff2"
        font.recalcTimestamp = False  # same input, same bytes: rebuilds don't touch untouched SVGs
        font.save(out)
        return base64.b64encode(out.getvalue()).decode()


# Display: the hero name's settings on the site (wdth 75, wght 760).
DISPLAY = Face("D", "bricolage-grotesque-latin.woff2", wght=760, wdth=75)
DISPLAY_EXT = Face("Dx", "bricolage-grotesque-latin-ext.woff2", wght=760, wdth=75)  # ₹
BODY = Face("B", "schibsted-grotesk-latin.woff2", wght=400)
BODY_BOLD = Face("Bb", "schibsted-grotesk-latin.woff2", wght=600)
MONO = Face("M", "fragment-mono-latin.woff2")


# ── SVG document ─────────────────────────────────────────────────────────────


class Svg:
    def __init__(self, w, h, label):
        self.w, self.h, self.label = w, h, label
        self.defs, self.css, self.body = [], [], []
        self.used = {}

    def add(self, *parts):
        self.body.extend(parts)

    def text(self, face, s, x, y, size, fill, ls=0, anchor=None, attrs="", family=None):
        self.used.setdefault(face, set()).update(s)
        style = f' letter-spacing="{num(ls)}"' if ls else ""
        a = f' text-anchor="{anchor}"' if anchor else ""
        fam = family or face.family
        return (
            f'<text x="{num(x)}" y="{num(y)}" font-family="{fam}" font-size="{num(size)}" '
            f'fill="{fill}"{style}{a} {attrs}>{escape(s)}</text>'
        )

    def use_chars(self, face, s):
        self.used.setdefault(face, set()).update(s)

    def card(self, rx=20, glow=(0.82, 0.0)):
        """The shared dark panel: ink, a slow teal glow, grain, hairline border."""
        gx, gy = glow
        self.defs.append(
            f'<clipPath id="card"><rect width="{self.w}" height="{self.h}" rx="{rx}"/></clipPath>'
            '<radialGradient id="glow"><stop offset="0" stop-color="#00B4D8" stop-opacity=".22"/>'
            '<stop offset="1" stop-color="#00B4D8" stop-opacity="0"/></radialGradient>'
            '<filter id="grain" x="0" y="0" width="100%" height="100%">'
            '<feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="2" stitchTiles="stitch"/>'
            '<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .55 0"/></filter>'
        )
        cx, cy, r = self.w * gx, self.h * gy, max(self.w, self.h) * 0.55
        self.add(
            '<g clip-path="url(#card)">',
            f'<rect width="{self.w}" height="{self.h}" fill="{INK}"/>',
            f'<circle cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" fill="url(#glow)">'
            f'<animate attributeName="cx" values="{num(cx)};{num(cx - self.w * 0.18)};{num(cx)}" '
            'dur="14s" repeatCount="indefinite" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"/>'
            "</circle>",
            f'<rect width="{self.w}" height="{self.h}" filter="url(#grain)" opacity=".07"/>',
            "</g>",
            f'<rect x=".5" y=".5" width="{self.w - 1}" height="{self.h - 1}" rx="{rx - 0.5}" '
            'fill="none" stroke="#f5f0e8" stroke-opacity=".09"/>',
        )

    def render(self):
        fonts = []
        for face, chars in self.used.items():
            chars = "".join(sorted(c for c in chars if ord(c) in face.cmap))
            if chars:
                fonts.append(
                    f'@font-face{{font-family:"{face.family}";'
                    f'src:url(data:font/woff2;base64,{face.woff2(chars)}) format("woff2")}}'
                )
        label = escape(self.label, {'"': "&quot;"})
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
            f'viewBox="0 0 {self.w} {self.h}" fill="none" role="img" aria-label="{label}">'
            f"<title>{escape(self.label)}</title>"
            f"<style>{''.join(fonts)}{''.join(self.css)}"
            # CSS animations only ever move things into their resting place,
            # so switching them off leaves the finished design.
            "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>"
            f"<defs>{''.join(self.defs)}</defs>"
            f"{''.join(self.body)}</svg>\n"
        )

    def save(self, name):
        (OUT / name).write_text(self.render(), encoding="utf-8")
        print(f"  {name:28} {(OUT / name).stat().st_size / 1024:6.1f} KB")


def arrow(x, y, size, color, width=1.4):
    """↗, drawn, since none of the three fonts has it."""
    s = size
    return (
        f'<path d="M{num(x)} {num(y + s)}L{num(x + s)} {num(y)}M{num(x + s * 0.3)} {num(y)}H{num(x + s)}V{num(y + s * 0.7)}" '
        f'stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>'
    )


# ── Name outlines and the laser path ─────────────────────────────────────────


class Flatten(BasePen):
    """Turns an outline into polylines, one per contour."""

    STEPS = 14

    def __init__(self):
        super().__init__(None)
        self.contours = []

    def _moveTo(self, p):
        self.contours.append([p])

    def _lineTo(self, p):
        self.contours[-1].append(p)

    def _qCurveToOne(self, p1, p2):
        p0 = self._getCurrentPoint()
        for i in range(1, self.STEPS + 1):
            t = i / self.STEPS
            a, b, c = (1 - t) ** 2, 2 * (1 - t) * t, t * t
            self.contours[-1].append((a * p0[0] + b * p1[0] + c * p2[0], a * p0[1] + b * p1[1] + c * p2[1]))

    def _curveToOne(self, p1, p2, p3):
        p0 = self._getCurrentPoint()
        for i in range(1, self.STEPS + 1):
            t = i / self.STEPS
            a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t**3
            self.contours[-1].append(
                (
                    a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0],
                    a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1],
                )
            )

    def _closePath(self):
        c = self.contours[-1]
        if c[-1] != c[0]:
            c.append(c[0])


def name_outlines(face, text, size, x0, baseline):
    """Each letter as one merged outline (like the site's nameGlyphs.ts)."""
    infos, pos = face.shape(text)
    order = face.font.getGlyphOrder()
    glyphs = face.font.getGlyphSet()
    k = size / face.upm
    letters, x = [], 0
    for info, p in zip(infos, pos):
        g = glyphs[order[info.codepoint]]
        path = pathops.Path()
        g.draw(TransformPen(path.getPen(), (k, 0, 0, -k, x0 + (x + p.x_offset) * k, baseline - p.y_offset * k)))
        if len(path) > 0:
            path.simplify(fix_winding=True)
            letters.append(path)
        x += p.x_advance
    return letters


def path_d(path):
    pen = SVGPathPen(None, ntos=num)
    path.draw(pen)
    return pen.getCommands()


def contours(path):
    """Each contour as its own SVG path, with its length."""
    rec = RecordingPen()
    path.draw(rec)
    groups = []
    for op, args in rec.value:
        if op == "moveTo":
            groups.append([])
        groups[-1].append((op, args))
    fl = Flatten()
    path.draw(fl)
    out = []
    for group, pts in zip(groups, fl.contours):
        pen = SVGPathPen(None, ntos=num)
        for op, args in group:
            getattr(pen, op)(*args)
        out.append((pen.getCommands(), sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))))
    return out


def laser_track(path, samples=72):
    """
    Where the laser tip is over time, as SMIL values + keyTimes.

    Progress is by outline length, matching how stroke-dashoffset reveals a
    path with pathLength="1"; between contours the tip jumps instead of sliding.
    """
    fl = Flatten()
    path.draw(fl)
    segs = []  # (contour index, start point, end point, start length, length)
    total = 0.0
    for ci, pts in enumerate(fl.contours):
        for a, b in zip(pts, pts[1:]):
            L = math.dist(a, b)
            if L > 0:
                segs.append((ci, a, b, total, L))
                total += L
    keys = []
    si = 0
    for i in range(samples + 1):
        d = total * i / samples
        while si < len(segs) - 1 and segs[si][3] + segs[si][4] < d:
            nxt = segs[si + 1]
            if nxt[0] != segs[si][0]:  # contour change: end here, restart there
                t = nxt[3] / total
                keys.append((t, segs[si][2]))
                keys.append((t, nxt[1]))
            si += 1
        ci, a, b, s0, L = segs[si]
        u = min(1.0, max(0.0, (d - s0) / L))
        keys.append((d / total, (a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u)))
    keys.sort(key=lambda k: k[0])
    times = ";".join(f"{t:.4f}" for t, _ in keys)
    xs = ";".join(num(p[0]) for _, p in keys)
    ys = ";".join(num(p[1]) for _, p in keys)
    return times, xs, ys, keys[0][1]


# ── Header ───────────────────────────────────────────────────────────────────


def wrap(face, text, size, max_w):
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and face.width(trial, size) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    lines.append(cur)
    return lines


def header():
    H = 344
    s = Svg(W, H, "Hi, I’m Arsh Chatrath. A curious creative blending code and design to build meaningful digital experiences.")
    s.card(glow=(0.86, 0.1))
    inner = W - PAD * 2

    # Engraving timeline, in seconds.
    T0, DUR = 0.55, 2.3
    DONE = round(T0 + DUR, 3)

    # The site's big idea, in miniature: a field that starts as noise and
    # resolves into order. Faint lines are thrown about by turbulence that
    # dies down while the name is engraved, so they settle straight with it.
    field = "".join(f"M-60 {y}H{W + 60}" for y in range(20, H, 13))
    s.defs.append(
        '<filter id="chaos" x="-10%" y="-20%" width="120%" height="140%">'
        '<feTurbulence type="fractalNoise" baseFrequency=".006 .045" numOctaves="2" seed="11" result="n">'
        f'<animate attributeName="baseFrequency" values=".006 .045;.009 .07;.006 .045" dur="{num(DONE)}s" fill="freeze"/>'
        "</feTurbulence>"
        '<feDisplacementMap in="SourceGraphic" in2="n" scale="0" xChannelSelector="R" yChannelSelector="G">'
        f'<animate attributeName="scale" values="90;90;0" keyTimes="0;.12;1" calcMode="spline" keySplines="0 0 1 1;.3 0 .1 1" dur="{num(DONE + 0.4)}s" fill="freeze"/>'
        "</feDisplacementMap></filter>"
    )
    s.add(
        '<g clip-path="url(#card)">',
        f'<path d="{field}" stroke="{PAPER}" stroke-opacity=".075" filter="url(#chaos)">'
        f'<animate attributeName="stroke-opacity" values=".075;.075;.035" keyTimes="0;.6;1" dur="{num(DONE + 1.2)}s" fill="freeze"/></path>',
        "</g>",
    )

    # Status row.
    status = "OPEN TO PRODUCT & GROWTH INTERNSHIPS"
    where = "PATIALA, PUNJAB"
    s.add(
        '<g opacity="0">',
        f'<animate attributeName="opacity" from="0" to="1" begin="{num(DONE + 0.35)}s" dur=".6s" fill="freeze"/>',
        f'<circle cx="{PAD + 4}" cy="45" r="3.5" fill="{TEAL}">'
        '<animate attributeName="opacity" values="1;.25;1" dur="1.8s" repeatCount="indefinite"/></circle>',
        s.text(MONO, status, PAD + 16, 49, 11, TEAL, ls=2.2),
        s.text(MONO, where, W - PAD, 49, 11, PAPER, ls=2.2, anchor="end", attrs='fill-opacity=".5"'),
        "</g>",
    )

    s.add(
        '<g opacity="0">',
        f'<animate attributeName="opacity" from="0" to="1" begin="{num(DONE)}s" dur=".7s" fill="freeze"/>',
        s.text(BODY, "Hi, I’m", PAD, 116, 26, PAPER, attrs='fill-opacity=".72"'),
        "</g>",
    )

    # The name, engraved.
    name = "ARSH CHATRATH"
    size = 100 * inner / DISPLAY.width(name, 100)
    base = 244
    letters = name_outlines(DISPLAY, name, size, PAD, base)
    n = len(letters)
    s.defs.append(
        '<filter id="hot" x="-50%" y="-50%" width="200%" height="200%">'
        '<feGaussianBlur stdDeviation="2.4" result="b"/>'
        '<feMerge><feMergeNode in="b"/><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>'
    )
    outlines, beams, heat = [], [], []
    trail_px = 26
    for i, path in enumerate(letters):
        times, xs, ys, (sx, sy) = laser_track(path)
        ex = PAD + inner * (i + 0.5) / n
        ey = 6
        # The fill is the whole letter; the engraving is per contour, each in
        # its own slice of the timeline. (Browsers disagree on whether a dash
        # pattern restarts at each subpath, so one path per contour is the
        # only way the stroke and the laser tip stay together everywhere.)
        outlines.append(
            f'<path d="{path_d(path)}" fill="{PAPER}" fill-opacity="0">'
            f'<animate attributeName="fill-opacity" from="0" to="1" begin="{num(DONE - 0.15)}s" dur=".8s" fill="freeze"/>'
            "</path>"
        )
        parts = contours(path)
        total = sum(L for _, L in parts)
        done = 0.0
        for d, L in parts:
            b, dur = T0 + DUR * done / total, DUR * L / total
            done += L
            t = min(0.5, trail_px / L)
            outlines.append(
                f'<path d="{d}" pathLength="1" stroke="{TEAL}" stroke-width="1.5" stroke-linejoin="round" '
                'stroke-dasharray="1 1" stroke-dashoffset="1">'
                f'<animate attributeName="stroke-dashoffset" from="1" to="0" begin="{num(b)}s" dur="{num(dur)}s" fill="freeze"/>'
                f'<animate attributeName="stroke-opacity" from="1" to="0" begin="{num(DONE + 0.4)}s" dur=".9s" fill="freeze"/>'
                "</path>"
            )
            # the hot trail right behind the tip
            heat.append(
                f'<path d="{d}" pathLength="1" stroke="#e6fbff" stroke-width="2.2" stroke-linecap="round" '
                f'stroke-dasharray="{num(t)} 3" stroke-dashoffset="{num(t)}" opacity="0">'
                f'<animate attributeName="stroke-dashoffset" from="{num(t)}" to="{num(t - 1)}" begin="{num(b)}s" dur="{num(dur)}s" fill="freeze"/>'
                f'<set attributeName="opacity" to="1" begin="{num(b)}s"/>'
                f'<animate attributeName="opacity" from="1" to="0" begin="{num(b + dur)}s" dur=".25s" fill="freeze"/>'
                "</path>"
            )
        motion = f'begin="{T0}s" dur="{DUR}s" keyTimes="{times}" fill="freeze"'
        beams.append(
            f'<line x1="{num(ex)}" y1="{ey}" x2="{num(sx)}" y2="{num(sy)}" stroke="{TEAL}" stroke-width=".8" stroke-opacity="0">'
            f'<animate attributeName="x2" values="{xs}" {motion}/>'
            f'<animate attributeName="y2" values="{ys}" {motion}/>'
            f'<animate attributeName="stroke-opacity" from="0" to=".42" begin="{num(T0 - 0.25)}s" dur=".3s" fill="freeze"/>'
            f'<animate attributeName="stroke-opacity" from=".42" to="0" begin="{num(DONE)}s" dur=".35s" fill="freeze"/>'
            "</line>"
        )
        heat.append(
            # the tip
            f'<circle cx="{num(sx)}" cy="{num(sy)}" r="2.6" fill="#ffffff" opacity="0">'
            f'<animate attributeName="cx" values="{xs}" {motion}/>'
            f'<animate attributeName="cy" values="{ys}" {motion}/>'
            f'<set attributeName="opacity" to="1" begin="{T0}s"/>'
            f'<animate attributeName="opacity" from="1" to="0" begin="{num(DONE - 0.05)}s" dur=".3s" fill="freeze"/>'
            f'<animate attributeName="r" values="2.2;3.4;2.2" dur=".16s" begin="{T0}s" repeatCount="15"/>'
            "</circle>"
            # its emitter
            f'<circle cx="{num(ex)}" cy="{ey}" r="2" fill="{TEAL}" opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" begin="{num(0.08 + i * 0.03)}s" dur=".25s" fill="freeze"/>'
            f'<animate attributeName="opacity" from="1" to="0" begin="{num(DONE + 0.1)}s" dur=".4s" fill="freeze"/>'
            "</circle>"
        )
    s.add(*beams, *outlines, '<g filter="url(#hot)">', *heat, "</g>")

    # Tagline, with the two words that were bold in the old README in teal.
    tag_size = 19
    tagline = "A curious creative blending code and design to build meaningful digital experiences."
    lines = wrap(BODY, tagline, tag_size, inner)
    s.use_chars(BODY, tagline)
    y = 296
    parts = ['<g opacity="0">', f'<animate attributeName="opacity" from="0" to="1" begin="{num(DONE + 0.2)}s" dur=".8s" fill="freeze"/>']
    for line in lines:
        spans = []
        for word in line.split(" "):
            color = TEAL if word in ("code", "design") else PAPER
            op = "1" if color == TEAL else ".78"
            spans.append(f'<tspan fill="{color}" fill-opacity="{op}">{escape(word)}</tspan>')
        parts.append(
            f'<text x="{PAD}" y="{y}" font-family="{BODY.family}" font-size="{tag_size}">{" ".join(spans)}</text>'
        )
        y += tag_size * 1.45
    parts.append("</g>")
    s.add(*parts)

    # Every so often the site's image-scan laser sweeps down the card.
    s.defs.append(
        '<linearGradient id="scan" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{TEAL}" stop-opacity="0"/><stop offset="1" stop-color="{TEAL}" stop-opacity=".16"/></linearGradient>'
    )
    s.add(
        '<g clip-path="url(#card)">',
        '<g transform="translate(0 -80)">',
        f'<animateTransform attributeName="transform" type="translate" values="0 -80;0 -80;0 {H + 4};0 {H + 4}" '
        f'keyTimes="0;.001;.16;1" dur="9s" begin="{num(DONE + 2.2)}s" repeatCount="indefinite"/>',
        f'<rect y="-56" width="{W}" height="56" fill="url(#scan)"/>',
        f'<line x1="0" y1="0" x2="{W}" y2="0" stroke="{TEAL}" stroke-opacity=".75" filter="url(#hot)"/>',
        "</g></g>",
    )
    s.save("header.svg")


# ── Link buttons ─────────────────────────────────────────────────────────────


def button(label, file):
    size, ls, h = 12, 2.2, 40
    tw = MONO.width(label, size, ls) - ls
    w = math.ceil(22 + tw + 12 + 9 + 20)
    s = Svg(w, h, label.title())
    s.add(
        f'<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="{(h - 1) / 2}" fill="#0b0b0b" stroke="{PAPER}" stroke-opacity=".14"/>',
        s.text(MONO, label, 22, 24.5, size, PAPER, ls=ls, attrs='fill-opacity=".85"'),
        arrow(22 + tw + 12, 15.5, 8.5, TEAL),
    )
    s.save(file)


# ── Proof strip ──────────────────────────────────────────────────────────────

STATS = [
    # (prefix, rolling number, suffix in teal, caption)
    ("", "8,000", "+", "users on Talkeys"),
    ("", "12,000", "+", "Helix registrations"),
    ("₹", "8.5", "L+", "revenue for Perplexity"),
    ("Top ", "1", "%", "Amazon ML School ’25"),
]


def proof():
    H = 184
    s = Svg(W, H, "Proof, not promises: 8,000+ users on Talkeys. 12,000+ Helix registrations. ₹8.5L+ revenue for Perplexity. Top 1% at Amazon ML School '25.")
    s.card(glow=(0.1, 1.0))
    s.add(s.text(MONO, "PROOF, NOT PROMISES", PAD, 48, 11, TEAL, ls=2.2))
    col = (W - PAD * 2) / len(STATS)
    size, base = 50, 116
    lh = size * 1.05
    s.defs.append(f'<clipPath id="row"><rect x="0" y="{num(base - size * 0.86)}" width="{W}" height="{num(size * 1.02)}"/></clipPath>')
    s.css.append(
        f".d{{font-family:{DISPLAY.family},{DISPLAY_EXT.family};font-size:{size}px}}"
        f"@keyframes in{{from{{opacity:0;transform:translateY(12px)}}to{{opacity:1;transform:none}}}}"
        f".in{{animation:in 1s {EASE_OUT} both}}"
    )
    s.use_chars(DISPLAY, "0123456789")
    slot = 0
    for c, (prefix, number, suffix, caption) in enumerate(STATS):
        x = PAD + col * c
        if c:
            s.add(f'<line x1="{num(x - 18)}" y1="{base - 44}" x2="{num(x - 18)}" y2="{H - 34}" stroke="{PAPER}" stroke-opacity=".1"/>')
        delay0 = 0.25 + c * 0.16
        parts = []
        for ch in prefix:
            face = DISPLAY if ord(ch) in DISPLAY.cmap else DISPLAY_EXT
            s.use_chars(face, ch)
            parts.append(f'<text class="d in" x="{num(x)}" y="{base}" fill="{PAPER}" style="animation-delay:{num(delay0)}s">{escape(ch)}</text>')
            x += face.width(ch, size) + (1.5 if ch == "₹" else 0)
        for i, ch in enumerate(number):
            w = DISPLAY.width(ch, size)
            s.use_chars(DISPLAY, ch)
            if ch.isdigit():
                d = int(ch)
                dist = (10 + d) * lh
                s.css.append(
                    f"@keyframes r{slot}{{from{{transform:translateY(0)}}to{{transform:translateY(-{num(dist)}px)}}}}"
                    f".r{slot}{{animation:r{slot} 2s {EASE_OUT} {num(delay0 + i * 0.07)}s both}}"
                )
                digits = "".join(
                    f'<text class="d" x="{num(x + w / 2)}" y="{num(base + j * lh)}" text-anchor="middle" fill="{PAPER}">{j % 10}</text>'
                    for j in range(11 + d)
                )
                parts.append(f'<g clip-path="url(#row)"><g class="r{slot}">{digits}</g></g>')
                slot += 1
            else:
                parts.append(f'<text class="d in" x="{num(x)}" y="{base}" fill="{PAPER}" style="animation-delay:{num(delay0)}s">{escape(ch)}</text>')
            x += w
        s.use_chars(DISPLAY, suffix)
        parts.append(f'<text class="d in" x="{num(x + 1)}" y="{base}" fill="{TEAL}" style="animation-delay:{num(delay0 + 0.5)}s">{escape(suffix)}</text>')
        parts.append(
            s.text(MONO, caption.upper(), PAD + col * c, base + 34, 10, PAPER, ls=1.1,
                   attrs=f'fill-opacity=".55" class="in" style="animation-delay:{num(delay0 + 0.3)}s"')
        )
        s.add(*parts)
    s.save("proof.svg")


# ── Chapter labels (drawn twice, for GitHub's light and dark themes) ─────────

CHAPTERS = ["Who am I?", "Selected Work", "Interests & Focus", "Skills & Currently Learning", "Let’s Connect"]
THEMES = {
    "dark": {"fg": PAPER, "teal": TEAL, "line": PAPER, "line_op": ".16"},
    "light": {"fg": INK, "teal": "#0086a0", "line": INK, "line_op": ".14"},
}


def chapter(i, title, theme):
    t = THEMES[theme]
    H = 64
    s = Svg(W, H, f"{i:02d} / {len(CHAPTERS):02d}. {title}")
    size = 32
    tx = 84
    tw = DISPLAY.width(title, size)
    s.css.append(
        f"@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}"
        f".grow{{transform-box:fill-box;transform-origin:0 50%;animation:grow 1.4s {EASE_OUT} .3s both}}"
        f"@keyframes up{{from{{opacity:0;transform:translateY(100%)}}to{{opacity:1;transform:none}}}}"
        f".up{{transform-box:fill-box;animation:up 1s {EASE_OUT} both}}"
    )
    s.defs.append(f'<clipPath id="c"><rect width="{W}" height="{H - 12}"/></clipPath>')
    x1 = tx + tw + 22
    s.add(
        s.text(MONO, f"{i:02d} / {len(CHAPTERS):02d}", 0, 42, 12, t["teal"], ls=1.8),
        '<g clip-path="url(#c)">',
        s.text(DISPLAY, title, tx, 46, size, t["fg"], attrs='class="up" style="animation-delay:.1s"'),
        "</g>",
        f'<line class="grow" x1="{num(x1)}" y1="35" x2="{W - 5}" y2="35" stroke="{t["line"]}" stroke-opacity="{t["line_op"]}"/>',
        f'<circle cx="{W - 4}" cy="35" r="3" fill="{t["teal"]}"><animate attributeName="opacity" values="0;0;1" keyTimes="0;.6;1" dur="1.4s" fill="freeze"/></circle>',
    )
    s.save(f"chapter-{i}-{theme}.svg")


# ── Who am I, and interests: numbered like the site, no emoji ───────────────

WHO = [
    # (line, the part that was bold in the old README)
    ("CSBS undergrad @ Thapar University", "Thapar University"),
    ("Founding Product & Growth Associate at Talkeys, a community-first college event & networking platform", "Talkeys"),
    ("I love bringing ideas to life through sleek UI/UX and scalable front-end solutions", None),
    ("Currently exploring product thinking, startup culture & community-focused tech", None),
]

INTERESTS = [
    "Product Design & Strategy",
    "UI/UX & Frontend Development",
    "Community Building & EduTech",
    "Marketing & Digital Experience Design",
]


def rise_css(s, dist=14):
    s.css.append(
        f"@keyframes rise{{from{{opacity:0;transform:translateY({dist}px)}}to{{opacity:1;transform:none}}}}"
        f".rise{{animation:rise 1s {EASE_OUT} both}}"
        f"@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}"
        f".grow{{transform-box:fill-box;transform-origin:0 50%;animation:grow 1.2s {EASE_OUT} both}}"
    )


def rich_lines(s, text, bold, size, max_w):
    """Wraps text whose `bold` part is set heavier and brighter; returns <tspan> runs per line."""
    a = text.index(bold) if bold else -1
    b = a + len(bold) if bold else -1
    # Each word is a list of (text, is_bold) pieces, so "Talkeys," keeps its
    # comma attached while only "Talkeys" is set bold.
    words, pos = [], 0
    for word in text.split(" "):
        pieces, i = [], pos
        for cut in sorted({pos, max(pos, min(a, pos + len(word))), max(pos, min(b, pos + len(word))), pos + len(word)}):
            if cut > i:
                pieces.append((text[i:cut], a <= i < b))
                i = cut
        words.append(pieces)
        pos += len(word) + 1

    def width(pieces):
        return sum((BODY_BOLD if pb else BODY).width(pt, size) for pt, pb in pieces)

    space = BODY.width(" ", size)
    lines, cur, cur_w = [], [], 0.0
    for pieces in words:
        ww = width(pieces)
        if cur and cur_w + space + ww > max_w:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur_w += (space if cur else 0) + ww
        cur.append(pieces)
    lines.append(cur)
    out = []
    for line in lines:
        spans = []
        for wi, pieces in enumerate(line):
            for pi, (pt, pb) in enumerate(pieces):
                face = BODY_BOLD if pb else BODY
                s.use_chars(face, pt + " ")
                gap = " " if wi and pi == 0 else ""  # the space before a word joins its first piece
                spans.append(
                    f'<tspan font-family="{face.family}" fill-opacity="{"1" if pb else ".74"}">{escape(gap + pt)}</tspan>'
                )
        out.append("".join(spans))
    return out


# ── Line illustrations ───────────────────────────────────────────────────────
#
# Drawn on a 48-unit grid in the site's two inks: teal for the part that
# matters, paper for the rest. Strokes draw themselves in (the engraving
# again), then each one keeps one small idle motion.


def _stroke(d, color=TEAL, op=1.0, extra=""):
    o = f' stroke-opacity="{op}"' if op != 1 else ""
    return f'<path class="draw" pathLength="1" d="{d}" stroke="{color}"{o}{extra}/>'


def _circle_d(cx, cy, r):
    return f"M{num(cx - r)} {num(cy)}a{num(r)} {num(r)} 0 1 0 {num(2 * r)} 0a{num(r)} {num(r)} 0 1 0 {num(-2 * r)} 0"


def _dot(cx, cy, r, color=TEAL, op=1.0, extra=""):
    o = f' fill-opacity="{op}"' if op != 1 else ""
    return f'<circle class="pop" cx="{num(cx)}" cy="{num(cy)}" r="{num(r)}" fill="{color}"{o}{extra}/>'


def icon_cap(t):
    """Mortarboard, for Thapar."""
    return [
        _stroke("M4 19L24 10L44 19L24 28Z"),
        _stroke("M12 23V31Q24 38 36 31V23", PAPER, 0.6),
        "<g>",
        _stroke("M44 19V30"),
        _dot(44, 32, 1.9),
        f'<animateTransform attributeName="transform" type="rotate" values="0 44 19;9 44 19;-6 44 19;3 44 19;0 44 19" '
        f'dur="3.2s" begin="{num(t)}s" repeatCount="indefinite"/>',
        "</g>",
    ]


def icon_ticket(t):
    """An event ticket with a growth line: Talkeys, product and growth."""
    return [
        _stroke("M9 14H39A4 4 0 0 1 43 18V21A3 3 0 0 0 43 27V30A4 4 0 0 1 39 34H9A4 4 0 0 1 5 30V27A3 3 0 0 0 5 21V18A4 4 0 0 1 9 14Z", PAPER, 0.6),
        f'<path class="pop" d="M15 17V31" stroke="{PAPER}" stroke-opacity=".4" stroke-dasharray="1.5 2.6"/>',
        _stroke("M20 29L26 24L30 27L37 20"),
        _stroke("M33 20H37V24"),
        f'<circle r="1.6" fill="{PAPER}" opacity="0"><set attributeName="opacity" to=".9" begin="{num(t)}s"/>'
        f'<animateMotion path="M20 29L26 24L30 27L37 20" dur="2.4s" begin="{num(t)}s" repeatCount="indefinite"/></circle>',
    ]


def icon_bezier(t):
    """A pen-tool curve with its handles: design, brought to life."""
    return [
        _stroke("M8 36L15 13", PAPER, 0.45),
        _stroke("M40 36L33 13", PAPER, 0.45),
        _stroke("M8 36C15 13 33 13 40 36"),
        _stroke(_circle_d(15, 13, 2.2), PAPER, 0.75),
        _stroke(_circle_d(33, 13, 2.2), PAPER, 0.75),
        f'<path class="pop" d="M5.5 33.5h5v5h-5Z" fill="{INK}" stroke="{TEAL}"/>',
        f'<path class="pop" d="M37.5 33.5h5v5h-5Z" fill="{INK}" stroke="{TEAL}"/>',
        # a point riding the curve, like a playhead
        f'<circle r="1.7" fill="{PAPER}" opacity="0"><set attributeName="opacity" to=".9" begin="{num(t)}s"/>'
        f'<animateMotion path="M8 36C15 13 33 13 40 36" dur="3s" begin="{num(t)}s" repeatCount="indefinite" '
        'keyPoints="0;1;0" keyTimes="0;.5;1" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1"/></circle>',
    ]


def icon_compass(t):
    """A compass whose needle keeps searching: exploring."""
    return [
        _stroke(_circle_d(24, 24, 17), PAPER, 0.5),
        _stroke("M24 4.5V8M24 40V43.5M4.5 24H8M40 24H43.5", PAPER, 0.5),
        "<g>",
        f'<path class="pop" d="M24 11.5L28 24H20Z" fill="{TEAL}"/>',
        _stroke("M24 36.5L28 24H20Z", PAPER, 0.6),
        f'<animateTransform attributeName="transform" type="rotate" values="-28 24 24;18 24 24;-9 24 24;6 24 24;-28 24 24" '
        f'dur="7s" begin="{num(t)}s" repeatCount="indefinite" calcMode="spline" keySplines=".45 0 .55 1;.45 0 .55 1;.45 0 .55 1;.45 0 .55 1"/>',
        "</g>",
        _dot(24, 24, 1.7, INK),
    ]


def icon_roadmap(t):
    """A roadmap to a flag: product design and strategy."""
    road = "M6 40C18 40 12 25 24 25C36 25 30 12 40 12"
    return [
        _stroke(road, PAPER, 0.55),
        _dot(6, 40, 2.6),
        _stroke(_circle_d(24, 25, 3.2)),
        _stroke("M40 13V2.5"),
        f'<path class="draw" pathLength="1" d="M40 2.8H47L44.6 5.6L47 8.4H40Z" stroke="{TEAL}" fill="{TEAL}" fill-opacity=".22"/>',
        f'<circle r="1.7" fill="{PAPER}" opacity="0"><set attributeName="opacity" to=".9" begin="{num(t)}s"/>'
        f'<animateMotion path="{road}" dur="3.6s" begin="{num(t)}s" repeatCount="indefinite"/></circle>',
    ]


def icon_browser(t):
    """A browser window with code in it: UI/UX and frontend."""
    return [
        _stroke("M8 8H40A4 4 0 0 1 44 12V36A4 4 0 0 1 40 40H8A4 4 0 0 1 4 36V12A4 4 0 0 1 8 8Z", PAPER, 0.55),
        _stroke("M4 15H44", PAPER, 0.4),
        _dot(8.6, 11.6, 1.1, PAPER, 0.6),
        _dot(12.4, 11.6, 1.1, PAPER, 0.6),
        _dot(16.2, 11.6, 1.1, PAPER, 0.6),
        _stroke("M17 22L12 27.5L17 33"),
        _stroke("M31 22L36 27.5L31 33"),
        _stroke("M26.5 20L21.5 35"),
        # a blinking caret
        f'<rect x="38" y="33.5" width="1.6" height="4" fill="{PAPER}" opacity="0">'
        f'<animate attributeName="opacity" values="0;.8;.8;0" keyTimes="0;.05;.5;.55" dur="1.1s" begin="{num(t)}s" repeatCount="indefinite"/></rect>',
    ]


def icon_network(t):
    """People connected around a centre: community building and edtech."""
    pts = [(24 + 16 * math.cos(math.radians(a)), 24 + 16 * math.sin(math.radians(a))) for a in range(-90, 270, 60)]
    links = "".join(f"M24 24L{num(x)} {num(y)}" for x, y in pts)
    rim = "M" + "L".join(f"{num(x)} {num(y)}" for x, y in pts) + "Z"
    out = [_stroke(rim, PAPER, 0.18), _stroke(links, PAPER, 0.45)]
    for k, (x, y) in enumerate(pts):
        out.append(
            f'<path class="draw" pathLength="1" d="{_circle_d(x, y, 3)}" stroke="{TEAL}" fill="{INK}">'
            f'<animate attributeName="stroke-opacity" values="1;.3;1" dur="2.4s" begin="{num(t + k * 0.4)}s" repeatCount="indefinite"/></path>'
        )
    out.append(_dot(24, 24, 4.4))
    return out


def icon_megaphone(t):
    """A megaphone: marketing."""
    waves = []
    for k, d in enumerate(["M38 19Q41.5 24 38 29", "M41.5 14.5Q47 24 41.5 33.5"]):
        waves.append(
            _stroke(d, extra="").replace(
                "/>",
                f'><animate attributeName="stroke-opacity" values="1;.2;1" dur="1.8s" begin="{num(t + k * 0.3)}s" repeatCount="indefinite"/></path>',
            )
        )
    return [
        _stroke("M7 20H14L33 11V37L14 28H7A2 2 0 0 1 5 26V22A2 2 0 0 1 7 20Z", PAPER, 0.6),
        _stroke("M14 28L17 37H21L19 29.5", PAPER, 0.6),
        *waves,
    ]


def illustration_css(s):
    s.css.append(
        "@keyframes draw{from{stroke-dashoffset:1}}"
        ".draw{stroke-dasharray:1;animation:draw 1.6s cubic-bezier(.65,0,.35,1) both}"
        f"@keyframes pop{{from{{opacity:0;transform:scale(.3)}}}}"
        f".pop{{transform-box:fill-box;transform-origin:center;animation:pop .7s {EASE_OUT} both}}"
    )


def place(icon, x, y, size, idle_at, stroke_px, cls):
    """An illustration at (x, y), `size` px square; its idle motion starts at `idle_at`."""
    k = size / 48
    return (
        f'<g class="{cls}" transform="translate({num(x)} {num(y)}) scale({num(k)})" stroke-width="{num(stroke_px / k)}" '
        f'stroke-linecap="round" stroke-linejoin="round" fill="none">{"".join(icon(idle_at))}</g>'
    )


WHO_ICONS = [icon_cap, icon_ticket, icon_bezier, icon_compass]
INTEREST_ICONS = [icon_roadmap, icon_browser, icon_network, icon_megaphone]


def who():
    size, lh, gap, plate = 18, 27, 30, 54
    px = PAD + 40
    tx = px + plate + 22
    s = Svg(W, 10, " ".join(t + "." for t, _ in WHO))  # height set once the text is wrapped
    rows = [rich_lines(s, t, b, size, W - tx - PAD) for t, b in WHO]
    # a row is as tall as its text or its plate, whichever is taller
    heights = [max(plate, (len(r) - 1) * lh + 14) for r in rows]
    top = 30
    H = top * 2 + sum(heights) + gap * (len(rows) - 1)
    s.h = H
    s.card(glow=(0.95, 1.0))
    rise_css(s)
    illustration_css(s)
    y = top
    for i, (lines, h) in enumerate(zip(rows, heights)):
        delay = 0.15 + i * 0.14
        text_h = (len(lines) - 1) * lh + 14
        base = y + (h - text_h) / 2 + 13.5
        py = y + (h - plate) / 2
        parts = [
            f'<g class="rise" style="animation-delay:{num(delay)}s">',
            s.text(MONO, f"{i + 1:02d}", PAD, py + plate / 2 + 4, 12, TEAL, ls=1.5),
            f'<rect x="{px + 0.5}" y="{num(py + 0.5)}" width="{plate - 1}" height="{plate - 1}" rx="12" fill="{PAPER}" fill-opacity=".03" stroke="{PAPER}" stroke-opacity=".1"/>',
        ]
        for j, spans in enumerate(lines):
            parts.append(f'<text x="{tx}" y="{num(base + j * lh)}" font-size="{size}" fill="{PAPER}">{spans}</text>')
        parts.append("</g>")
        s.add(*parts)
        s.add(place(WHO_ICONS[i], px + 10, py + 10, plate - 20, delay + 1.9, 1.4, f"d{i}"))
        s.css.append(f".d{i} .draw,.d{i} .pop{{animation-delay:{num(delay + 0.25)}s}}")
        y += h
        if i < len(rows) - 1:
            ly = y + gap / 2
            s.add(f'<line class="grow" x1="{PAD}" y1="{num(ly)}" x2="{W - PAD}" y2="{num(ly)}" stroke="{PAPER}" stroke-opacity=".08" style="animation-delay:{num(delay + 0.1)}s"/>')
            y += gap
    s.save("who.svg")


def interests():
    pad, g, th, art = 24, 12, 142, 78
    tw = (W - pad * 2 - g) / 2
    inner = tw - 48
    size = min(28.0, 28.0 * inner / max(DISPLAY.width(t, 28) for t in INTERESTS))
    H = pad * 2 + th * 2 + g
    s = Svg(W, H, "Interests & Focus: " + ", ".join(INTERESTS) + ".")
    s.card(glow=(0.5, 1.1))
    rise_css(s)
    illustration_css(s)
    for i, name in enumerate(INTERESTS):
        x = pad + (i % 2) * (tw + g)
        y = pad + (i // 2) * (th + g)
        delay = 0.15 + i * 0.12
        ax, ay = x + tw - 22 - art, y + 12
        s.add(
            f'<g class="rise" style="animation-delay:{num(delay)}s">',
            f'<rect x="{num(x + 0.5)}" y="{y + 0.5}" width="{num(tw - 1)}" height="{th - 1}" rx="14" fill="{PAPER}" fill-opacity=".025" stroke="{PAPER}" stroke-opacity=".1"/>',
            s.text(MONO, f"{i + 1:02d}", x + 24, y + 34, 12, TEAL, ls=1.5),
            f'<line x1="{num(x + 52)}" y1="{y + 30}" x2="{num(ax - 18)}" y2="{y + 30}" stroke="{PAPER}" stroke-opacity=".08"/>',
            s.text(DISPLAY, name, x + 24, y + th - 26, size, PAPER),
            "</g>",
            place(INTEREST_ICONS[i], ax, ay, art, delay + 1.9, 1.6, f"d{i}"),
        )
        s.css.append(f".d{i} .draw,.d{i} .pop{{animation-delay:{num(delay + 0.3)}s}}")
    s.save("interests.svg")


# ── Skills, as a set of marquees ─────────────────────────────────────────────

SKILLS = [
    ("Languages & Concepts", ["C", "C++", "Python", "SQL", "HTML/CSS", "OOPS", "DSA", "OS", "DBMS"]),
    ("Tools & Design", ["Git", "GitHub", "VS Code", "Cursor", "Kiro", "Vercel", "Dev C++", "Figma", "Canva", "Notion", "MATLAB"]),
    ("AI & Automation", ["n8n", "Workflow Automation", "LLM APIs (Claude, OpenAI)", "AI Agents", "Prompt Engineering"]),
    ("Product", ["Roadmapping", "Prioritization", "Stakeholder Management", "User Research", "Go-to-Market Strategy"]),
    ("Soft Skills", ["Leadership", "Event Mgmt", "Collaboration", "Innovation", "Communication"]),
    ("Currently Exploring", ["Product Mgmt", "Scalable FE", "UX Research", "Community Growth", "Startups"]),
]


def skills():
    row_h, top = 54, 30
    H = top * 2 + row_h * len(SKILLS) - 14
    alt = " ".join(f"{k}: {', '.join(v)}." for k, v in SKILLS)
    s = Svg(W, H, alt)
    s.card(glow=(0.95, 0.5))
    track_x = 244
    track_w = W - track_x - 22
    s.defs.append(
        f'<linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>'
        f'<stop offset=".08" stop-color="#fff"/><stop offset=".9" stop-color="#fff"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        f'<mask id="edge"><rect x="{track_x}" y="0" width="{track_w}" height="{H}" fill="url(#fade)"/></mask>'
    )
    size, pill_h, gap, padx = 15, 32, 10, 15
    for r, (label, items) in enumerate(SKILLS):
        y = top + r * row_h
        cy = y + pill_h / 2
        s.add(s.text(MONO, label.upper(), PAD - 8, cy + 3.5, 10.5, TEAL, ls=1.6))
        seq, x = [], 0.0
        for item in items:
            w = BODY.width(item, size) + padx * 2
            seq.append((x, w, item))
            x += w + gap
        seq_w = x
        copies = math.ceil((track_w + seq_w) / seq_w) + 1
        pills = []
        for c in range(copies):
            for px, w, item in seq:
                ox = track_x + c * seq_w + px
                pills.append(
                    f'<rect x="{num(ox)}" y="{y}" width="{num(w)}" height="{pill_h}" rx="{pill_h / 2}" stroke="{PAPER}" stroke-opacity=".16"/>'
                    + s.text(BODY, item, ox + padx, cy + 5.2, size, PAPER, attrs='fill-opacity=".86"')
                )
        speed = 26 + (r % 3) * 5  # px per second
        dur = seq_w / speed
        name = f"m{r}"
        frm, to = (0, -seq_w) if r % 2 == 0 else (-seq_w, 0)
        s.css.append(
            f"@keyframes {name}{{from{{transform:translateX({num(frm)}px)}}to{{transform:translateX({num(to)}px)}}}}"
            f".{name}{{animation:{name} {num(dur)}s linear infinite}}"
        )
        s.add(f'<g mask="url(#edge)"><g class="{name}">', *pills, "</g></g>")
    s.save("skills.svg")


# ── The quote ────────────────────────────────────────────────────────────────


def quote(theme):
    """
    The one section without a card: the quote set big, straight on the page,
    so the README has a moment that isn't another box.
    """
    t = THEMES[theme]
    first = "Design is not just what it looks like and feels like."
    second = "Design is how it works."
    size, lh = 46, 58
    x0, max_w = 92, W - 92
    words = [(w, t["fg"]) for w in first.split()] + [(w, t["teal"]) for w in second.split()]
    lines, cur, cur_w = [], [], 0.0
    space = DISPLAY.width(" ", size)
    for w, color in words:
        ww = DISPLAY.width(w, size)
        # each sentence starts its own line
        if cur and (cur_w + space + ww > max_w or color != cur[-1][1]):
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur.append((w, color, ww))
        cur_w += (space if len(cur) > 1 else 0) + ww
    lines.append(cur)
    top = 80
    H = top + lh * (len(lines) - 1) + 86
    s = Svg(W, H, f"“{first} {second}” Steve Jobs")
    s.css.append(
        f"@keyframes rise{{from{{transform:translateY({size}px)}}to{{transform:none}}}}"
        f".w{{animation:rise 1.1s {EASE_OUT} both}}"
        "@keyframes draw{from{stroke-dashoffset:1}}"
        ".draw{stroke-dasharray:1;animation:draw 1s cubic-bezier(.65,0,.35,1) both}"
    )
    s.add(s.text(DISPLAY, "“", 0, 108, 124, t["teal"]))
    k = 0
    for li, line in enumerate(lines):
        base = top + li * lh
        s.defs.append(f'<clipPath id="l{li}"><rect x="0" y="{num(base - size)}" width="{W}" height="{num(size * 1.32)}"/></clipPath>')
        x = x0
        parts = [f'<g clip-path="url(#l{li})">']
        for w, color, ww in line:
            parts.append(s.text(DISPLAY, w, x, base, size, color, attrs=f'class="w" style="animation-delay:{num(0.2 + k * 0.06)}s"'))
            x += ww + space
            k += 1
        parts.append("</g>")
        s.add(*parts)
    # a hand-drawn underline under "how it works."
    last = lines[-1]
    xs = [x0]
    for _, _, ww in last:
        xs.append(xs[-1] + ww + space)
    ux0, ux1 = xs[2] - 2, xs[-1] - space + 4
    uy = top + lh * (len(lines) - 1) + 14
    span = ux1 - ux0
    d = (
        f"M{num(ux0)} {num(uy + 2)}"
        f"C{num(ux0 + span * 0.3)} {num(uy - 3)} {num(ux0 + span * 0.62)} {num(uy + 3)} {num(ux1)} {num(uy - 1.5)}"
        f"M{num(ux0 + span * 0.08)} {num(uy + 8)}C{num(ux0 + span * 0.4)} {num(uy + 4)} {num(ux0 + span * 0.7)} {num(uy + 8.5)} {num(ux1 - span * 0.12)} {num(uy + 5)}"
    )
    s.add(
        f'<path class="draw" pathLength="1" d="{d}" stroke="{t["teal"]}" stroke-width="3" stroke-linecap="round" '
        f'style="animation-delay:{num(0.35 + k * 0.06)}s"/>'
    )
    ay = uy + 48
    s.add(
        f'<line x1="{x0}" y1="{ay - 4}" x2="{x0 + 26}" y2="{ay - 4}" stroke="{t["teal"]}"/>',
        s.text(MONO, "STEVE JOBS", x0 + 38, ay, 11, t["fg"], ls=2.2, attrs='fill-opacity=".6"'),
    )
    s.save(f"quote-{theme}.svg")


# ── Selected work ────────────────────────────────────────────────────────────

WORK = [
    dict(cat="PRODUCT", title="Perplexity AI Campus Growth", link="CASE STUDY",
         stat=("₹", "8.5", "L+"), caption="revenue · top 15 campus partners nationwide",
         result="Segmented CS and research students by need, then ran campus activations for each",
         stack=["Growth", "GTM", "Community"]),
    dict(cat="PRODUCT", title="Talkeys Community Platform", link="SITE",
         stat=("", "60", "%"), caption="lift in participation · 8,000+ users",
         result="User research, A/B tested three engagement strategies, prioritised features by data",
         stack=["Product", "A/B testing", "Ops"]),
    dict(cat="AI / ML", title="SafeSpace AI", link="LIVE",
         flow=["ESP32 WEARABLE", "VOICE", "DASS-21", "LATE FUSION", "XAI"],
         result="73% accuracy on 500+ samples · 3rd place at the Indian-Israeli Hackathon",
         stack=["Python", "FastAPI", "TensorFlow", "ESP32"]),
    dict(cat="SQL / PRODUCT DESIGN", title="DataPulse", link="CODE",
         stat=("", "20", "+"), caption="SQL query patterns on a live SQLite engine",
         result="A SQL lab that isn’t simulated: the rows a query touches are the ones that move",
         stack=["SQL", "SQLite", "WebAssembly"]),
    dict(cat="AUTOMATION", title="AI Job Search Agent", link="WORKFLOW",
         flow=["SERPAPI JOBS", "BATCH ×5", "LLM SCORE 1-10", "DAILY DIGEST"],
         result="One daily email of only the listings worth applying to",
         stack=["n8n", "SerpApi", "Groq", "Gmail"]),
    dict(cat="AUTOMATION", title="Daily LeetCode Agent", link="CODE",
         flow=["DAILY + TOPIC", "LLM SOLUTION", "SUBMIT / JUDGE", "SELF-CORRECT ×5"],
         result="Runs unattended once a day and tracks streak, success rate and attempts to accept",
         stack=["Python", "Claude Code CLI"]),
]


def work_card(i, p):
    CW, CH, pc = 430, 304, 26
    inner = CW - pc * 2
    alt = f"{i + 1:02d}, {p['cat']}: {p['title']}. " + (
        f"{''.join(p['stat'])} {p['caption']}. " if "stat" in p else " → ".join(p["flow"]) + ". "
    ) + p["result"] + "."
    s = Svg(CW, CH, alt)
    glows = [(0.9, 0.0), (0.1, 0.0), (0.95, 1.0), (0.05, 1.0), (0.9, 0.1), (0.1, 1.0)]
    s.card(rx=18, glow=glows[i % len(glows)])
    rise_css(s, 10)

    # top row: index, category, where the link goes
    s.add(
        s.text(MONO, f"{i + 1:02d}", pc, 40, 11, TEAL, ls=1.5),
        s.text(MONO, p["cat"], pc + 30, 40, 10, PAPER, ls=1.5, attrs='fill-opacity=".5"'),
    )
    lw = MONO.width(p["link"], 10, 1.5) - 1.5
    s.add(
        s.text(MONO, p["link"], CW - pc - 14 - lw, 40, 10, TEAL, ls=1.5),
        arrow(CW - pc - 8, 32, 8, TEAL, 1.3),
    )
    tsize = min(27.0, 27.0 * inner / DISPLAY.width(p["title"], 27))
    s.add(s.text(DISPLAY, p["title"], pc, 82, tsize, PAPER, attrs='class="rise" style="animation-delay:.1s"'))

    if "stat" in p:
        pre, n, suf = p["stat"]
        size, base = 64, 164
        x = pc
        parts = ['<g class="rise" style="animation-delay:.2s">']
        for ch in pre:
            face = DISPLAY if ord(ch) in DISPLAY.cmap else DISPLAY_EXT
            s.use_chars(face, ch)
            parts.append(f'<text x="{num(x)}" y="{base}" font-family="{DISPLAY.family},{DISPLAY_EXT.family}" font-size="{size}" fill="{PAPER}">{escape(ch)}</text>')
            x += face.width(ch, size) + 2
        parts.append(s.text(DISPLAY, n, x, base, size, PAPER))
        x += DISPLAY.width(n, size) + 1
        parts.append(s.text(DISPLAY, suf, x, base, size, TEAL))
        parts.append("</g>")
        s.add(*parts, s.text(MONO, p["caption"].upper(), pc, base + 24, 9.5, PAPER, ls=1.1,
                             attrs='fill-opacity=".55" class="rise" style="animation-delay:.35s"'))
    else:
        # the pipeline, with a pulse running through it
        fsize, fls, chip_h, gap, arr = 9.5, 1.0, 26, 7, 12
        chips, x, y = [], pc, 112
        for label in p["flow"]:
            w = MONO.width(label, fsize, fls) - fls + 20
            need = w if not chips or chips[-1][1] != y else arr + gap * 2 + w
            if chips and x + need > CW - pc:
                # wrap, and lead the new line with an arrow so the flow reads on
                x, y = pc - gap, y + chip_h + 12
                need = arr + gap * 2 + w
            cx = x + (need - w)
            chips.append((cx, y, w, label, x if need != w else None))
            x = cx + w
        n = len(chips)
        step = 0.5
        D = n * step + 1.6
        for k, (cx, cy, w, label, ax) in enumerate(chips):
            a0 = (k * step) / D
            a1 = min(0.999, (k * step + 0.25) / D)
            a2 = min(0.9995, (k * step + 0.9) / D)
            flash = f'values="0;0;1;0;0" keyTimes="0;{a0:.3f};{a1:.3f};{a2:.3f};1" dur="{num(D)}s" begin=".8s" repeatCount="indefinite"'
            parts = [
                f'<g class="rise" style="animation-delay:{num(0.2 + k * 0.08)}s">',
                f'<rect x="{num(cx)}" y="{cy}" width="{num(w)}" height="{chip_h}" rx="{chip_h / 2}" stroke="{PAPER}" stroke-opacity=".18"/>',
                f'<rect x="{num(cx)}" y="{cy}" width="{num(w)}" height="{chip_h}" rx="{chip_h / 2}" fill="{TEAL}" fill-opacity=".12" stroke="{TEAL}" opacity="0"><animate attributeName="opacity" {flash}/></rect>',
                s.text(MONO, label, cx + 10, cy + 16.6, fsize, PAPER, ls=fls, attrs='fill-opacity=".85"'),
            ]
            if ax is not None:
                mx = ax + gap
                my = cy + chip_h / 2
                parts.append(
                    f'<path d="M{num(mx)} {num(my)}H{num(mx + arr)}M{num(mx + arr - 3.5)} {num(my - 3.5)}L{num(mx + arr)} {num(my)}L{num(mx + arr - 3.5)} {num(my + 3.5)}" '
                    f'stroke="{TEAL}" stroke-opacity=".7" stroke-width="1.2" stroke-linecap="round" stroke-linejoin="round"/>'
                )
            parts.append("</g>")
            s.add(*parts)

    # the outcome and the stack
    s.add(f'<line x1="{pc}" y1="206" x2="{CW - pc}" y2="206" stroke="{PAPER}" stroke-opacity=".08"/>')
    lines = wrap(BODY, p["result"], 14, inner)[:2]
    s.use_chars(BODY, p["result"])
    s.add(*[
        f'<text x="{pc}" y="{230 + j * 20}" font-family="{BODY.family}" font-size="14" fill="{PAPER}" fill-opacity=".74" class="rise" style="animation-delay:.4s">{escape(line)}</text>'
        for j, line in enumerate(lines)
    ])
    s.add(s.text(MONO, " · ".join(p["stack"]).upper(), pc, CH - 24, 9.5, TEAL, ls=1.1, attrs='fill-opacity=".85"'))
    s.save(f"work-{i + 1}.svg")


def work():
    for i, p in enumerate(WORK):
        work_card(i, p)


# ── Now playing ──────────────────────────────────────────────────────────────


def cover_data_uri():
    """The poster from the old README's player card, cropped for a record label."""
    im = Image.open(HERE / "cover.jpg").convert("RGB")
    im = im.crop((300, 110, 780, 590)).resize((180, 180), Image.LANCZOS)
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def now_playing():
    H = 232
    s = Svg(W, H, "Now playing: Dil Toh Bacha Hai by Rahat Fateh Ali Khan. “Music is the universal language of mankind.”")
    s.card(glow=(0.15, 0.5))
    cx, cy, R = 132, H / 2, 86
    grooves = "".join(
        f'<circle cx="{cx}" cy="{num(cy)}" r="{r}" stroke="#fff" stroke-opacity="{0.035 + (r % 3) * 0.012:.3f}"/>'
        for r in range(42, R - 2, 3)
    )
    s.defs.append(
        f'<clipPath id="label"><circle cx="{cx}" cy="{num(cy)}" r="36"/></clipPath>'
        '<linearGradient id="sheen" x1="0" y1="0" x2="1" y2="1">'
        '<stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".45" stop-color="#fff" stop-opacity=".07"/>'
        '<stop offset=".55" stop-color="#fff" stop-opacity="0"/></linearGradient>'
    )
    s.css.append(
        f"@keyframes spin{{to{{transform:rotate(360deg)}}}}"
        f".spin{{transform-origin:{cx}px {num(cy)}px;animation:spin 1.8s linear infinite}}"
        "@keyframes eq{0%,100%{transform:scaleY(.25)}50%{transform:scaleY(1)}}"
        ".eq{transform-box:fill-box;transform-origin:50% 100%;animation:eq 1s ease-in-out infinite}"
    )
    img = cover_data_uri()
    s.add(
        f'<circle cx="{cx}" cy="{num(cy)}" r="{R}" fill="#111"/>',
        '<g class="spin">',
        grooves,
        f'<image href="{img}" x="{cx - 36}" y="{num(cy - 36)}" width="72" height="72" clip-path="url(#label)" preserveAspectRatio="xMidYMid slice"/>',
        f'<circle cx="{cx}" cy="{num(cy)}" r="36" stroke="#000" stroke-opacity=".5"/>',
        "</g>",
        f'<circle cx="{cx}" cy="{num(cy)}" r="{R}" fill="url(#sheen)"/>',
        f'<circle cx="{cx}" cy="{num(cy)}" r="3.2" fill="{INK}"/>',
        # tonearm
        f'<circle cx="{cx + 92}" cy="{num(cy - 72)}" r="7" fill="#1c1c1c" stroke="{PAPER}" stroke-opacity=".25"/>',
        f'<path d="M{cx + 92} {num(cy - 72)}L{cx + 70} {num(cy + 8)}L{cx + 50} {num(cy + 24)}" stroke="{PAPER}" stroke-opacity=".45" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>',
        f'<rect x="{cx + 42}" y="{num(cy + 18)}" width="14" height="9" rx="2" fill="{PAPER}" fill-opacity=".55" transform="rotate(-38 {cx + 49} {num(cy + 22)})"/>',
    )
    x = 272
    bars = "".join(
        f'<rect class="eq" x="{x + i * 6}" y="36" width="3" height="13" rx="1" fill="{TEAL}" style="animation-duration:{d}s;animation-delay:-{i * 0.23:.2f}s"/>'
        for i, d in enumerate((0.9, 1.25, 0.75, 1.1))
    )
    bar_w = W - x - PAD
    s.add(
        bars,
        s.text(MONO, "NOW PLAYING", x + 34, 48, 11, TEAL, ls=2.2),
        s.text(DISPLAY, "Dil Toh Bacha Hai", x, 98, 38, PAPER),
        s.text(BODY, "by Rahat Fateh Ali Khan", x, 128, 17, PAPER, attrs='fill-opacity=".62"'),
        f'<rect x="{x}" y="152" width="{bar_w}" height="3" rx="1.5" fill="{PAPER}" fill-opacity=".14"/>',
        f'<rect x="{x}" y="152" width="0" height="3" rx="1.5" fill="{TEAL}">'
        f'<animate attributeName="width" from="{bar_w * 0.12:.0f}" to="{bar_w}" dur="240s" repeatCount="indefinite"/></rect>',
        f'<circle cx="{x}" cy="153.5" r="5" fill="{PAPER}">'
        f'<animate attributeName="cx" from="{x + bar_w * 0.12:.0f}" to="{x + bar_w}" dur="240s" repeatCount="indefinite"/></circle>',
        s.text(BODY, "“Music is the universal language of mankind.”", x, 194, 15, PAPER,
               attrs='fill-opacity=".5" font-style="italic"'),
    )
    s.save("now-playing.svg")


# ── The cat ──────────────────────────────────────────────────────────────────

# Frames on the oneko sheet (column, row), from Neko.tsx.
RUN_E = [(3, 0), (3, 1)]
RUN_W = [(4, 2), (4, 3)]
ALERT = (7, 3)
SCRATCH = [(5, 0), (6, 0), (7, 0)]
TIRED = (3, 2)
SLEEP = [(2, 0), (2, 1)]
IDLE = (3, 3)


def sprite_uri(theme):
    im = Image.open(HERE / "oneko.gif").convert("RGBA")
    if theme == "dark":  # the site shows it inverted, so it reads on ink
        r, g, b, a = im.split()
        rgb = Image.merge("RGB", (r, g, b)).point(lambda v: 255 - v)
        im = Image.merge("RGBA", (*rgb.split(), a))
    im = im.resize((im.width * 2, im.height * 2), Image.NEAREST)
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def neko(theme):
    """
    The site's "Do you like cats?" switch, acted out on a loop, since nothing
    in a README can be clicked: the cursor switches it on, the cat wakes and
    chases the cursor, the cursor switches it off, and the cat walks back and
    curls up on the switch. The README links this strip to the real thing.
    """
    H, T = 116, 20.0
    cat = 64
    teal = TEAL if theme == "dark" else "#0086a0"
    s = Svg(W, H, "Thanks for stopping by! Do you like cats? The cat from arshchatrath.me wakes up when the switch turns on and chases the cursor.")

    size, ls = 12, 0.7
    label = "Do you like cats?"
    tw = MONO.width(label, size, ls)
    bw, bh = 16 + tw + 12 + 32 + 10, 36
    bx, by = W - bw - 48, H - bh - 4
    kx0 = bx + 16 + tw + 12  # toggle track
    ty = by + (bh - 18) / 2
    knob_off, knob_on, knob_y = kx0 + 9, kx0 + 23, ty + 9
    home = kx0 + 16 - cat / 2
    cy = by - cat + 10
    ground = cy + 38  # where the cursor hovers while the cat chases it

    def track(keys, fmt=num):
        """(t, value) pairs over one loop -> SMIL values/keyTimes."""
        keys = sorted(keys, key=lambda k: k[0])
        return (
            ";".join(fmt(v) for _, v in keys),
            ";".join(f"{t / T:.4f}" for t, _ in keys),
        )

    def loop(attr, keys, fmt=num, calc="linear", extra=""):
        values, times = track(keys, fmt)
        return (
            f'<animate attributeName="{attr}" values="{values}" keyTimes="{times}" calcMode="{calc}" '
            f'dur="{num(T)}s" repeatCount="indefinite"{extra}/>'
        )

    def move(keys):
        values, times = track(keys, fmt=lambda v: f"{num(v[0])} {num(v[1])}")
        return (
            f'<animateTransform attributeName="transform" type="translate" values="{values}" keyTimes="{times}" '
            f'dur="{num(T)}s" repeatCount="indefinite"/>'
        )

    # Clicks, and what they switch.
    click_on, click_off = 2.72, 10.87

    def switched(on_value, off_value):
        return [(0, off_value), (click_on + 0.03, off_value), (click_on + 0.33, on_value),
                (click_off + 0.03, on_value), (click_off + 0.33, off_value), (T, off_value)]

    s.add(
        f'<rect x="{num(bx)}" y="{by}" width="{num(bw)}" height="{bh}" rx="{bh / 2}" fill="#0b0b0b" fill-opacity=".92" stroke="#fff" stroke-opacity=".1"/>',
        s.text(MONO, label, bx + 16, by + 22.5, size, PAPER, ls=ls, attrs='fill-opacity=".75"'),
        f'<rect x="{num(kx0)}" y="{num(ty)}" width="32" height="18" rx="9" fill="#3a3a3a">'
        + loop("fill", switched(TEAL, "#3a3a3a"), fmt=str) + "</rect>",
        f'<circle cx="{num(knob_off)}" cy="{num(knob_y)}" r="7" fill="{PAPER}">'
        + loop("cx", switched(knob_on, knob_off)) + "</circle>",
        # the old README's sign-off, on the same line as the switch
        s.text(MONO, "Thanks for stopping by!", 0, by + 22.5, 12, PAPER if theme == "dark" else INK, ls=0.7,
               attrs='fill-opacity=".6"'),
    )

    # The cat: where it is, and which frame it shows.
    at1 = 300 + 36 - cat / 2   # stops just right of the cursor
    at2 = 500 - 36 - cat / 2   # then just left of it
    frames = []

    def act(frame_list, t0, t1, step):
        t, k = t0, 0
        while t < t1 - 1e-6:
            frames.append((t, frame_list[k % len(frame_list)]))
            t += step
            k += 1

    act(SLEEP, 0, 3.1, 0.7)
    act([ALERT], 3.1, 3.6, 1)
    act(RUN_W, 3.6, 6.2, 0.1)
    act([IDLE], 6.2, 6.9, 1)
    act(RUN_E, 6.9, 8.2, 0.1)
    act(SCRATCH, 8.2, 9.6, 0.14)
    act([IDLE], 9.6, click_off + 0.03, 1)
    act([ALERT], click_off + 0.03, 11.3, 1)
    act(RUN_E, 11.3, 13.3, 0.1)
    act([IDLE], 13.3, 13.6, 1)
    act([TIRED], 13.6, 14.6, 1)
    act(SLEEP, 14.6, T, 0.7)
    fx = [(t, -f[0] * cat) for t, f in frames]
    fy = [(t, -f[1] * cat) for t, f in frames]
    pos = [(0, home), (3.6, home), (6.2, at1), (6.9, at1), (8.2, at2), (11.3, at2), (13.3, home), (T, home)]

    glow = ' filter="url(#glow)"' if theme == "dark" else ""
    if theme == "dark":
        s.defs.append('<filter id="glow" x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#00B4D8" flood-opacity=".5"/></filter>')
    # A clip, not a nested <svg>: Chrome gives nested <svg>s their own clock.
    s.defs.append(f'<clipPath id="frame"><rect width="{cat}" height="{cat}"/></clipPath>')
    s.add(
        f'<g transform="translate({num(home)} {num(cy)})"{glow}>',
        move([(t, (x, cy)) for t, x in pos]),
        '<g clip-path="url(#frame)">',
        f'<image href="{sprite_uri(theme)}" width="{cat * 8}" height="{cat * 4}" x="{fx[0][1]}" y="{fy[0][1]}" style="image-rendering:pixelated">',
        loop("x", fx, calc="discrete"),
        loop("y", fy, calc="discrete"),
        "</image></g></g>",
    )

    # The cursor: the site's teal ring and dot.
    path = [
        (0, (-40, ground)), (1.0, (-40, ground)), (2.5, (knob_off, knob_y)), (3.3, (knob_off, knob_y)),
        (4.5, (300, ground - 2)), (6.4, (300, ground - 2)), (7.3, (500, ground + 2)), (9.2, (500, ground + 2)),
        (10.6, (knob_on, knob_y)), (11.2, (knob_on, knob_y)), (12.0, (W + 40, ground - 20)), (T, (W + 40, ground - 20)),
    ]
    ring = [(0, 11), (click_on - 0.12, 11), (click_on, 6.5), (click_on + 0.2, 11),
            (click_off - 0.12, 11), (click_off, 6.5), (click_off + 0.2, 11), (T, 11)]

    def ripple(t0):
        return [(0, 0), (t0, 0), (t0 + 0.01, 0.7), (t0 + 0.6, 0), (T, 0)]

    def ripple_r(t0):
        return [(0, 8), (t0, 8), (t0 + 0.6, 26), (T, 26)]

    s.add(
        f'<g opacity="0">',
        loop("opacity", [(0, 0), (1.0, 0), (1.3, 1), (11.7, 1), (12.0, 0), (T, 0)]),
        "<g>",
        move(path),
        f'<circle r="8" stroke="{teal}" stroke-width="1.2" opacity="0">{loop("r", ripple_r(click_on))}{loop("opacity", ripple(click_on))}</circle>',
        f'<circle r="8" stroke="{teal}" stroke-width="1.2" opacity="0">{loop("r", ripple_r(click_off))}{loop("opacity", ripple(click_off))}</circle>',
        f'<circle r="11" stroke="{teal}" stroke-width="1.5">{loop("r", ring)}</circle>',
        f'<circle r="2.6" fill="{teal}"/>',
        "</g></g>",
    )
    s.save(f"neko-{theme}.svg")


def main():
    OUT.mkdir(exist_ok=True)
    print("assets/")
    header()
    for label, file in [
        ("PORTFOLIO", "link-portfolio.svg"),
        ("LINKEDIN", "link-linkedin.svg"),
        ("INSTAGRAM", "link-instagram.svg"),
        ("TALKEYS", "link-talkeys.svg"),
        ("EMAIL", "link-email.svg"),
    ]:
        button(label, file)
    proof()
    for i, title in enumerate(CHAPTERS, 1):
        for theme in THEMES:
            chapter(i, title, theme)
    who()
    interests()
    skills()
    work()
    for theme in THEMES:
        quote(theme)
    now_playing()
    for theme in THEMES:
        neko(theme)


if __name__ == "__main__":
    main()
