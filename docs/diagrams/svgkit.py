"""Small SVG helpers for the thesis diagrams (no extra libraries).

Shapes size themselves to their text, so the figures stay readable when
they are printed on a long-bond page."""
import textwrap
from xml.sax.saxutils import escape

FONT = "Arial, Helvetica, sans-serif"
INK = "#1d2430"
MUTED = "#4a5566"
NAVY = "#1f3a5f"
MAROON = "#7a1f2b"
GOLD = "#a87f12"
GREEN = "#2f6b3f"
TEAL = "#1f6670"
GRAY = "#5b6676"

FILLS = {
    "navy": ("#eaf0f7", NAVY),
    "maroon": ("#f7eaec", MAROON),
    "gold": ("#fbf3df", GOLD),
    "green": ("#e8f3ec", GREEN),
    "teal": ("#e5f2f3", TEAL),
    "gray": ("#f1f3f6", GRAY),
    "white": ("#ffffff", GRAY),
}

# type scale (px in the SVG; the figures are 1150 px wide)
TITLE = 30
HEAD = 19     # band headers
TS = 17.5     # box titles
BS = 16       # box text
LS = 14       # arrow labels
LH = 1.28
F = 1.25      # every text size is multiplied by F (bigger print)


def wrap(text, width_px, size, bold=False):
    chars = max(6, int(width_px / (size * F * (0.57 if bold else 0.52))))
    out = []
    for part in str(text).split("\n"):
        out.extend(textwrap.wrap(part, chars, break_on_hyphens=False) or [""])
    return out


class R:
    """A placed rectangle."""

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h

    l = property(lambda s: s.x)
    t = property(lambda s: s.y)
    r = property(lambda s: s.x + s.w)
    b = property(lambda s: s.y + s.h)
    cx = property(lambda s: s.x + s.w / 2)
    cy = property(lambda s: s.y + s.h / 2)


class SVG:
    def __init__(self, w, title, subtitle=None):
        self.w = w
        self.items = []
        self.colors = set()
        self.text(w / 2, 52, title, TITLE, "bold", NAVY, "middle")
        if subtitle:
            self.text(w / 2, 88, subtitle, 16, "normal", MUTED, "middle", italic=True)

    # primitives -------------------------------------------------------
    def add(self, s):
        self.items.append(s)

    def rect(self, x, y, w, h, fill="#fff", stroke=INK, rx=8, sw=1.6, dash=None):
        d = f' stroke-dasharray="{dash}"' if dash else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

    def text(self, x, y, s, size=BS, weight="normal", fill=INK, anchor="start", italic=False):
        st = ' font-style="italic"' if italic else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT}" font-size="{size * F:.1f}" font-weight="{weight}" '
                 f'fill="{fill}" text-anchor="{anchor}"{st}>{escape(str(s))}</text>')

    def lines(self, x, y, rows, size=BS, weight="normal", fill=INK, anchor="start", italic=False):
        for i, r in enumerate(rows):
            self.text(x, y + i * size * F * LH, r, size, weight, fill, anchor, italic)
        return y + len(rows) * size * F * LH

    def label(self, x, y, s, fill=MUTED, size=LS):
        wpx = len(s) * size * F * 0.56 + 12
        self.add(f'<rect x="{x - wpx / 2:.1f}" y="{y - size * F:.1f}" width="{wpx:.1f}" height="{size * F + 8:.1f}" rx="4" '
                 f'fill="#ffffff" opacity="0.96"/>')
        self.text(x, y, s, size, "bold", fill, "middle")

    def path(self, pts, color=INK, sw=2, dash=None, head=True, both=False):
        d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        da = f' stroke-dasharray="{dash}"' if dash else ""
        mid = color.strip("#")
        me = f' marker-end="url(#a{mid})"' if head else ""
        ms = f' marker-start="url(#a{mid})"' if both else ""
        self.colors.add(color)
        self.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{da}{me}{ms} stroke-linejoin="round"/>')

    def down(self, a, b, color=INK, x1=None, x2=None, sw=2, dash=None, lab=None, lab_color=None):
        """Arrow from the bottom of `a` to the top of `b` (elbow in the middle)."""
        x1 = a.cx if x1 is None else x1
        x2 = b.cx if x2 is None else x2
        if abs(x1 - x2) < 1:
            pts = [(x1, a.b), (x2, b.t - 1)]
        else:
            m = (a.b + b.t) / 2
            pts = [(x1, a.b), (x1, m), (x2, m), (x2, b.t - 1)]
        self.path(pts, color, sw, dash)
        if lab:
            self.label(x2 + 8 + len(lab) * LS * 0.28, (a.b + b.t) / 2 + 5, lab, lab_color or color)

    def right(self, a, b, color=INK, y=None, sw=2, dash=None):
        y = a.cy if y is None else y
        self.path([(a.r, y), (b.l - 1, y)], color, sw, dash)

    # sizing ------------------------------------------------------------
    @staticmethod
    def _body_rows(w, body, size, bullets):
        rows = []
        for item in (body if isinstance(body, list) else [body] if body else []):
            for i, row in enumerate(wrap(("• " if bullets else "") + item, w - 26, size)):
                rows.append((row, bool(bullets and i)))
        return rows

    def box_h(self, w, title, body=None, ts=TS, bs=BS, bullets=False):
        tr = wrap(title, w - 26, ts, True) if title else []
        br = self._body_rows(w, body, bs, bullets)
        return 16 + len(tr) * ts * F * LH + (6 if br else 0) + len(br) * bs * F * LH + 8

    # shapes ------------------------------------------------------------
    def box(self, x, y, w, title, body=None, tone="navy", h=None, ts=TS, bs=BS, bullets=False, center=False,
            dash=None):
        fill, stroke = FILLS[tone]
        h = h or self.box_h(w, title, body, ts, bs, bullets)
        self.rect(x, y, w, h, fill, stroke, 8, 1.7, dash)
        anchor, tx = ("middle", x + w / 2) if center else ("start", x + 13)
        ty = y + 12 + ts * F
        for row in (wrap(title, w - 26, ts, True) if title else []):
            self.text(tx, ty, row, ts, "bold", stroke, anchor)
            ty += ts * F * LH
        ty += 6 - ts * F * LH + bs * F * LH if title else 0
        for row, indent in self._body_rows(w, body, bs, bullets):
            self.text(tx + (12 if indent else 0), ty, row, bs, "normal", INK, anchor)
            ty += bs * F * LH
        return R(x, y, w, h)

    def cyl_h(self, w, title, body=None, bs=BS):
        return self.box_h(w, title, body, TS, bs) + 26

    def cyl(self, x, y, w, title, body=None, tone="teal", h=None, bs=BS):
        fill, stroke = FILLS[tone]
        e = 11
        h = h or self.cyl_h(w, title, body, bs)
        self.add(f'<path d="M{x:.1f},{y + e:.1f} V{y + h - e:.1f} A{w / 2:.1f},{e} 0 0 0 {x + w:.1f},{y + h - e:.1f} '
                 f'V{y + e:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="1.7"/>')
        self.add(f'<ellipse cx="{x + w / 2:.1f}" cy="{y + e:.1f}" rx="{w / 2:.1f}" ry="{e}" fill="{fill}" '
                 f'stroke="{stroke}" stroke-width="1.7"/>')
        ty = y + 2 * e + 8 + TS * F
        for row in wrap(title, w - 26, TS, True):
            self.text(x + w / 2, ty, row, TS, "bold", stroke, "middle")
            ty += TS * F * LH
        ty += 6 - TS * F * LH + bs * F * LH
        for row, _ in self._body_rows(w, body, bs, False):
            self.text(x + w / 2, ty, row, bs, "normal", INK, "middle")
            ty += bs * F * LH
        return R(x, y, w, h)

    def node_h(self, w, s, size=BS):
        return len(wrap(s, w - 26, size)) * size * F * LH + 24

    def node(self, cx, y, w, s, tone="navy", size=BS, h=None):
        fill, stroke = FILLS[tone]
        h = h or self.node_h(w, s, size)
        self.rect(cx - w / 2, y, w, h, fill, stroke, 8, 1.7)
        rows = wrap(s, w - 26, size)
        y0 = y + h / 2 - (len(rows) - 1) * size * F * LH / 2 + size * F * 0.36
        self.lines(cx, y0, rows, size, "normal", INK, "middle")
        return R(cx - w / 2, y, w, h)

    def diamond_h(self, w, s, size=BS):
        return max(88 * F, len(wrap(s, w * 0.6, size, True)) * size * F * LH * 1.8 + 22)

    def diamond(self, cx, y, w, s, tone="gold", size=BS, h=None):
        fill, stroke = FILLS[tone]
        h = h or self.diamond_h(w, s, size)
        cy = y + h / 2
        self.add(f'<polygon points="{cx:.1f},{y:.1f} {cx + w / 2:.1f},{cy:.1f} {cx:.1f},{y + h:.1f} {cx - w / 2:.1f},{cy:.1f}" '
                 f'fill="{fill}" stroke="{stroke}" stroke-width="1.7"/>')
        rows = wrap(s, w * 0.6, size, True)
        y0 = cy - (len(rows) - 1) * size * F * LH / 2 + size * F * 0.36
        self.lines(cx, y0, rows, size, "bold", INK, "middle")
        return R(cx - w / 2, y, w, h)

    def pill(self, cx, y, w, s, tone="navy"):
        _, stroke = FILLS[tone]
        self.rect(cx - w / 2, y, w, 40 * F, stroke, stroke, 20 * F)
        self.text(cx, y + 27 * F, s, 17, "bold", "#ffffff", "middle")
        return R(cx - w / 2, y, w, 40 * F)

    def circle(self, cx, y, s, tone="maroon"):
        _, stroke = FILLS[tone]
        r = 19 * F
        self.add(f'<circle cx="{cx:.1f}" cy="{y + r:.1f}" r="{r:.1f}" fill="{stroke}"/>')
        self.text(cx, y + r + 7 * F, s, 18, "bold", "#ffffff", "middle")
        return R(cx - r, y, 2 * r, 2 * r)

    def band(self, x, y, w, h, title, sub=None, shade=True):
        self.rect(x, y, w, h, "#f5f7fa" if shade else "#ffffff", "#cfd7e2", 8, 1.2)
        self.text(x + 14, y + 27, title, HEAD, "bold", NAVY)
        if sub:
            tw = len(title) * HEAD * 0.58
            self.text(x + 28 + tw, y + 27, sub, 15, "normal", MAROON, italic=True)

    def table(self, x, y, w, name, fields, tone="navy", note=None, row_h=27 * F):
        """ER-style entity. fields: (key, name, type). Returns (R, row centre ys)."""
        fill, stroke = FILLS[tone]
        head = 38 * F + (20 * F if note else 0)
        h = head + row_h * len(fields) + 8
        self.rect(x, y, w, h, "#ffffff", stroke, 6, 1.7)
        self.add(f'<path d="M{x},{y + head} V{y + 6} Q{x},{y} {x + 6},{y} H{x + w - 6} Q{x + w},{y} {x + w},{y + 6} '
                 f'V{y + head} Z" fill="{stroke}"/>')
        self.text(x + w / 2, y + 25 * F, name, 17, "bold", "#ffffff", "middle")
        if note:
            self.text(x + w / 2, y + 46 * F, note, 13, "normal", "#eef2f7", "middle", italic=True)
        ys = []
        for i, (key, fname, ftype) in enumerate(fields):
            ry = y + head + 4 + i * row_h
            if i % 2:
                self.add(f'<rect x="{x + 1}" y="{ry}" width="{w - 2}" height="{row_h}" fill="{fill}"/>')
            cy = ry + row_h / 2 + 5.5 * F
            if key:
                kc = {"PK": MAROON, "FK": NAVY, "UK": GOLD}.get(key, MUTED)
                self.text(x + 9, cy, key, 12, "bold", kc)
            self.text(x + 38 * F, cy, fname, 15, "bold" if key == "PK" else "normal", INK)
            self.text(x + w - 9, cy, ftype, 13.5, "normal", MUTED, "end")
            ys.append(ry + row_h / 2)
        return R(x, y, w, h), ys

    def save(self, path, h):
        defs = []
        for c in sorted(self.colors):
            mid = c.strip("#")
            defs.append(f'<marker id="a{mid}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                        f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
        svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{h:.0f}" '
               f'viewBox="0 0 {self.w} {h:.0f}">\n<defs>{"".join(defs)}</defs>\n'
               f'<rect x="0" y="0" width="{self.w}" height="{h:.0f}" fill="#ffffff"/>\n' + "\n".join(self.items)
               + "\n</svg>\n")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        self.split(path, svg, h)
        return h

    def split(self, path, svg, h):
        """Also write the figure as two pages (…_p1.svg, …_p2.svg), cut at the
        break nearest the middle, so it prints large on a long-bond page."""
        cuts = [c for c in getattr(self, "cuts", []) if 0.3 * h < c < 0.7 * h]
        if not cuts:
            return
        cut = min(cuts, key=lambda c: abs(c - h / 2))
        head = f'width="{self.w}" height="{h:.0f}" viewBox="0 0 {self.w} {h:.0f}"'
        for i, (y0, y1) in enumerate(((0, cut), (cut, h)), 1):
            part = svg.replace(head, f'width="{self.w}" height="{y1 - y0:.0f}" viewBox="0 {y0:.0f} {self.w} {y1 - y0:.0f}"')
            with open(path.replace(".svg", f"_p{i}.svg"), "w", encoding="utf-8") as f:
                f.write(part)
