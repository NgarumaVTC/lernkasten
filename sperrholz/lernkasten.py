# -*- coding: utf-8 -*-
"""
Lernkasten DIN A7 – fünf Fächer, 6 mm Sperrholz, CNC (SCM)
===========================================================

Parametrische FreeCAD-Konstruktion für NgarumaVTC.

Aufruf (headless):   freecadcmd lernkasten.py
In der GUI:          Makro → Makros … → lernkasten.py ausführen

Erzeugt in ./build/:
  lernkasten.FCStd   Zusammenbau + flache Teile
  lernkasten.step    Zusammenbau
  dxf/<teil>.dxf     Einzelteile (Layer AUSSEN / INNEN)
  zuschnitt.dxf/.svg Ein Kastensatz verschachtelt
  platte.dxf/.svg    Volle Platte für die Serie
  montage.pdf        Montageanleitung Englisch / Kiswahili

Verbindungen: Fingerzinken an den Ecken, Boden und Trennwände mit
durchgesteckten Zapfen. Alle Konturen sind Durchgangsschnitte; jede
Innenecke bekommt automatisch einen Dogbone-Freistich für den Fräser.
"""

import math
import os
import subprocess
import sys

import FreeCAD as App
import Part

V = App.Vector

# ═════════════════════════════════════════════════════════════════════
#  PARAMETER  (alle Maße in mm)
# ═════════════════════════════════════════════════════════════════════

T = 6.0            # Materialstärke – VOR DER SERIE AM ECHTEN MATERIAL MESSEN!
C = 0.15           # Spiel gesamt für Schlitze und Zinken
TOOL_D = 6.0       # Fräserdurchmesser für Schlitze / Innenecken
R_DB = TOOL_D / 2 + 0.05   # Radius der Dogbone-Freistiche

CARD_W, CARD_H = 105.0, 74.0   # DIN A7, quer stehend
PLAY_W = 4.0                   # Luft der Karte in der Breite

FACH = [25.0, 40.0, 60.0, 90.0, 135.0]   # lichte Fachlängen, Fach 1 … 5

HW = 65.0          # Wandhöhe (Seiten- und Stirnwände), Außenmaß
S = 8.0            # Unterkante Boden über Tisch
HD = 50.0          # Trennwandhöhe über Innenboden
N_FING = 5         # Zinkenbänder über die Höhe (ungerade!)

GRIP_W = 40.0      # Griffmulde: Breite
GRIP_D_END = 20.0  #   Tiefe in den Stirnwänden
GRIP_D_DIV = 15.0  #   Tiefe in den Trennwänden

DIV_TAB_Z = (10.0, 40.0)     # Seitenzapfen der Trennwand, Höhe über Innenboden
DIV_BOT_TAB = (15.0, 40.0)   # Bodenzapfen der Trennwand, Abstand zur Innenwand
END_TAB = 50.0               # Bodenzapfen in die Stirnwände, Länge
BOT_TAB_MAX = 40.0           # Bodenzapfen in die Seitenwände, max. Länge

# Serie
SHEET = (2500.0, 1250.0)     # Plattenformat (M+M Einkauf, ggf. 1525 x 1525)
SHEET_MARGIN = 15.0          # Randabstand
GAP = 10.0                   # Teileabstand (>= TOOL_D + 4)
N_BOXES = 120
SCRAP = 0.05                 # Ausschuss-Zuschlag

FONT = "'Latin Modern Roman', 'CMU Serif', serif"

# ═════════════════════════════════════════════════════════════════════
#  Abgeleitete Maße
# ═════════════════════════════════════════════════════════════════════

assert N_FING % 2 == 1, "N_FING muss ungerade sein"
WI = CARD_W + PLAY_W                       # lichte Breite
W = WI + 2 * T                             # Außenbreite
L = sum(FACH) + (len(FACH) - 1) * T + 2 * T  # Außenlänge
F = S + T                                  # Oberkante Boden = Innenboden

COMPS = []      # (x_anfang, x_ende) je Fach, global
DIVS = []       # x_anfang je Trennwand
_x = T
for _i, _l in enumerate(FACH):
    COMPS.append((_x, _x + _l))
    _x += _l
    if _i < len(FACH) - 1:
        DIVS.append(_x)
        _x += T

DIV_BOT_Y = [(T + DIV_BOT_TAB[0], T + DIV_BOT_TAB[1]),
             (W - T - DIV_BOT_TAB[1], W - T - DIV_BOT_TAB[0])]


def bot_tab_len(fachlaenge):
    return min(0.5 * fachlaenge, BOT_TAB_MAX)


try:
    BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE = os.getcwd()
OUT = os.environ.get("LERNKASTEN_OUT", os.path.join(BASE, "build"))


def log(*a):
    print(" ".join(str(x) for x in a), flush=True)


# ═════════════════════════════════════════════════════════════════════
#  2D-Geometrie
# ═════════════════════════════════════════════════════════════════════

def rect(u0, v0, u1, v1):
    pts = [V(u0, v0, 0), V(u1, v0, 0), V(u1, v1, 0), V(u0, v1, 0), V(u0, v0, 0)]
    return Part.Face(Part.makePolygon(pts))


def circle(cu, cv, r):
    return Part.Face(Part.Wire(Part.makeCircle(r, V(cu, cv, 0))))


def single_face(shape, what):
    shape = shape.removeSplitter()
    if len(shape.Faces) != 1:
        raise RuntimeError("%s: %d Flächen statt 1" % (what, len(shape.Faces)))
    return shape.Faces[0]


def union(faces, what):
    return single_face(faces[0].fuse(faces[1:]) if len(faces) > 1 else faces[0], what)


def cut(face, tools, what):
    if not tools:
        return face
    return single_face(face.cut(Part.makeCompound(tools)), what)


def _signed_area(pts):
    n = len(pts)
    return 0.5 * sum(pts[i].x * pts[(i + 1) % n].y - pts[(i + 1) % n].x * pts[i].y
                     for i in range(n))


def add_dogbones(face, r, what):
    """Kreisförmiger Freistich in jeder Innenecke (Fräser kann sie nicht
    scharfkantig fräsen).  Außendraht CCW, Löcher CW → Material liegt
    links; jede Rechtskurve ist eine Innenecke."""
    outer = face.OuterWire
    bones = []
    for w in face.Wires:
        pts = [v.Point for v in w.OrderedVertexes]
        a = _signed_area(pts)
        is_outer = w.isSame(outer)
        if (is_outer and a < 0) or (not is_outer and a > 0):
            pts.reverse()
        n = len(pts)
        for i in range(n):
            p, v, q = pts[i - 1], pts[i], pts[(i + 1) % n]
            d1, d2 = v - p, q - v
            cross = d1.x * d2.y - d1.y * d2.x
            if cross < -1e-9:
                b = (p - v).normalize() + (q - v).normalize()
                b.normalize()
                c = v + b * r
                bones.append(circle(c.x, c.y, r))
    return cut(face, bones, what + " (Dogbones)"), len(bones)


def grip(face, cu, top, width, depth, what):
    """U-förmige Griffmulde von oben (Kreisbogen, ggf. mit Rechteck)."""
    R = width / 2
    cv = top - depth + R
    tools = [circle(cu, cv, R)]
    if depth > R:
        tools.append(rect(cu - R, cv, cu + R, top + 1))
    return cut(face, tools, what + " (Griffmulde)")


# ═════════════════════════════════════════════════════════════════════
#  Teile als 2D-Profile (lokal: u waagerecht, v senkrecht)
# ═════════════════════════════════════════════════════════════════════

def fingers(owner_even, u_ranges, height):
    h = height / N_FING
    out = []
    for k in range(N_FING):
        if (k % 2 == 0) != owner_even:
            continue
        v0 = k * h + (C / 2 if k > 0 else 0)
        v1 = (k + 1) * h - (C / 2 if k < N_FING - 1 else 0)
        for (u0, u1) in u_ranges:
            out.append(rect(u0, v0, u1, v1))
    return out


def part_seitenwand():
    name = "Seitenwand"
    f = [rect(T, 0, L - T, HW)] + fingers(True, [(0, T), (L - T, L)], HW)
    face = union(f, name)
    holes = []
    for (a, b) in COMPS:
        m, lt = (a + b) / 2, bot_tab_len(b - a)
        holes.append(rect(m - lt / 2 - C / 2, S - C / 2, m + lt / 2 + C / 2, S + T + C / 2))
    for d in DIVS:
        holes.append(rect(d - C / 2, F + DIV_TAB_Z[0] - C / 2,
                          d + T + C / 2, F + DIV_TAB_Z[1] + C / 2))
    face = cut(face, holes, name)
    face, nb = add_dogbones(face, R_DB, name)
    return face


def part_stirnwand():
    name = "Stirnwand"
    f = [rect(T, 0, W - T, HW)] + fingers(False, [(0, T), (W - T, W)], HW)
    face = union(f, name)
    face = cut(face, [rect(W / 2 - END_TAB / 2 - C / 2, S - C / 2,
                           W / 2 + END_TAB / 2 + C / 2, S + T + C / 2)], name)
    face, nb = add_dogbones(face, R_DB, name)
    return grip(face, W / 2, HW, GRIP_W, GRIP_D_END, name)


def part_boden():
    name = "Boden"
    f = [rect(T, T, L - T, W - T)]
    for (a, b) in COMPS:
        m, lt = (a + b) / 2, bot_tab_len(b - a)
        f += [rect(m - lt / 2, 0, m + lt / 2, T), rect(m - lt / 2, W - T, m + lt / 2, W)]
    f += [rect(0, W / 2 - END_TAB / 2, T, W / 2 + END_TAB / 2),
          rect(L - T, W / 2 - END_TAB / 2, L, W / 2 + END_TAB / 2)]
    face = union(f, name)
    holes = [rect(d - C / 2, y0 - C / 2, d + T + C / 2, y1 + C / 2)
             for d in DIVS for (y0, y1) in DIV_BOT_Y]
    face = cut(face, holes, name)
    face, nb = add_dogbones(face, R_DB, name)
    return face


def part_trennwand():
    name = "Trennwand"
    top = T + HD
    f = [rect(T, T, W - T, top),
         rect(0, T + DIV_TAB_Z[0], T, T + DIV_TAB_Z[1]),
         rect(W - T, T + DIV_TAB_Z[0], W, T + DIV_TAB_Z[1])]
    f += [rect(y0, 0, y1, T) for (y0, y1) in DIV_BOT_Y]
    face = union(f, name)
    face, nb = add_dogbones(face, R_DB, name)
    return grip(face, W / 2, top, GRIP_W, GRIP_D_DIV, name)


# ═════════════════════════════════════════════════════════════════════
#  Zusammenbau
# ═════════════════════════════════════════════════════════════════════

M_SIDE = App.Matrix(1, 0, 0, 0,  0, 0, -1, 0,  0, 1, 0, 0,  0, 0, 0, 1)  # (x,y,z)->(x,-z,y)
M_CYC = App.Matrix(0, 0, 1, 0,  1, 0, 0, 0,  0, 1, 0, 0,  0, 0, 0, 1)    # (x,y,z)->(z,x,y)
M_ID = App.Matrix()


def place(face, matrix, offset):
    solid = face.extrude(V(0, 0, T))
    s = solid.copy()
    s.Placement = App.Placement(matrix)
    s.translate(offset)
    return s


def build_parts():
    """Liefert dict Teiltyp -> (Profil, Stückzahl, Bezeichnung) und die
    Liste der eingebauten Körper [(Name, Teiltyp, Solid)]."""
    prof = {
        "A": (part_seitenwand(), 2, "Seitenwand", "Side wall", "Ubao wa pembeni"),
        "B": (part_stirnwand(), 2, "Stirnwand", "End wall", "Ubao wa mwisho"),
        "C": (part_boden(), 1, "Boden", "Bottom", "Ubao wa chini"),
        "D": (part_trennwand(), 4, "Trennwand", "Divider", "Kitenganishi"),
    }
    asm = []
    asm.append(("Seitenwand_vorn", "A", place(prof["A"][0], M_SIDE, V(0, T, 0))))
    asm.append(("Seitenwand_hinten", "A", place(prof["A"][0], M_SIDE, V(0, W, 0))))
    asm.append(("Stirnwand_Fach1", "B", place(prof["B"][0], M_CYC, V(0, 0, 0))))
    asm.append(("Stirnwand_Fach5", "B", place(prof["B"][0], M_CYC, V(L - T, 0, 0))))
    asm.append(("Boden", "C", place(prof["C"][0], M_ID, V(0, 0, S))))
    for i, d in enumerate(DIVS):
        asm.append(("Trennwand_%d" % (i + 1), "D", place(prof["D"][0], M_CYC, V(d, 0, S))))
    return prof, asm


def check_assembly(asm):
    log("— Prüfung Zusammenbau —")
    ok = True
    for i in range(len(asm)):
        for j in range(i + 1, len(asm)):
            v = asm[i][2].common(asm[j][2]).Volume
            if v > 1e-6:
                log("  KOLLISION %s / %s: %.4f mm³" % (asm[i][0], asm[j][0], v))
                ok = False
    for n, _, s in asm:
        touching = [m for m, _, o in asm if m != n and s.distToShape(o)[0] < 1e-6]
        if not touching:
            log("  %s berührt kein anderes Teil!" % n)
            ok = False
    comp = Part.makeCompound([s for _, _, s in asm])
    bb = comp.BoundBox
    log("  Außenmaß: %.1f × %.1f × %.1f mm" % (bb.XLength, bb.YLength, bb.ZLength))
    log("  Lichte Breite %.1f mm (Karte %.0f) – Karte ragt %.0f mm über Wand, %.0f mm über Trennwand"
        % (WI, CARD_W, F + CARD_H - HW, CARD_H - HD))
    for k, (a, b) in enumerate(COMPS):
        log("  Fach %d: %.0f mm lichte Länge ≈ %d Karten" % (k + 1, b - a, int((b - a) / 0.25)))
    assert WI >= CARD_W
    assert abs(bb.XLength - L) < 1e-6 and abs(bb.YLength - W) < 1e-6 and abs(bb.ZLength - HW) < 1e-6
    log("  Kollisionsprüfung: %s" % ("OK" if ok else "FEHLER"))
    if not ok:
        raise RuntimeError("Zusammenbau fehlerhaft")


# ═════════════════════════════════════════════════════════════════════
#  Drähte → Punktlisten
# ═════════════════════════════════════════════════════════════════════

def wire_points(w, defl=0.05):
    pts = []
    edges = w.OrderedEdges
    for k, e in enumerate(edges):
        p = list(e.discretize(Deflection=defl))
        if not pts:
            if len(edges) > 1:
                nxt = edges[1]
                ends = [nxt.Vertexes[0].Point, nxt.Vertexes[-1].Point]
                if min((p[0] - x).Length for x in ends) < min((p[-1] - x).Length for x in ends):
                    p.reverse()
            pts.extend(p)
        else:
            if (pts[-1] - p[0]).Length > (pts[-1] - p[-1]).Length:
                p.reverse()
            pts.extend(p[1:])
    return pts


def moved(face, x, y, rot=False):
    f = face.copy()
    if rot:
        f.rotate(V(0, 0, 0), V(0, 0, 1), 90)
    bb = f.BoundBox
    f.translate(V(x - bb.XMin, y - bb.YMin, 0))
    return f


# ═════════════════════════════════════════════════════════════════════
#  DXF R12 (eigener Writer: LINE / ARC / CIRCLE / TEXT)
# ═════════════════════════════════════════════════════════════════════

class DXF:
    LAYERS = [("AUSSEN", 1), ("INNEN", 5), ("INFO", 8)]

    def __init__(self):
        self.ent = []

    def _g(self, *pairs):
        for c, v in pairs:
            self.ent.append("%d\n%s\n" % (c, v))

    @staticmethod
    def _f(x):
        return "%.6f" % x

    def line(self, a, b, layer):
        self._g((0, "LINE"), (8, layer), (10, self._f(a.x)), (20, self._f(a.y)), (30, "0.0"),
                (11, self._f(b.x)), (21, self._f(b.y)), (31, "0.0"))

    def text(self, x, y, h, s, layer="INFO"):
        self._g((0, "TEXT"), (8, layer), (10, self._f(x)), (20, self._f(y)), (30, "0.0"),
                (40, self._f(h)), (1, s))

    def edge(self, e, layer):
        tid = e.Curve.TypeId
        if tid == "Part::GeomLine" or tid == "Part::GeomLineSegment":
            self.line(e.Vertexes[0].Point, e.Vertexes[-1].Point, layer)
        elif tid == "Part::GeomCircle":
            c, r = e.Curve.Center, e.Curve.Radius
            if e.isClosed():
                self._g((0, "CIRCLE"), (8, layer), (10, self._f(c.x)), (20, self._f(c.y)),
                        (30, "0.0"), (40, self._f(r)))
                return
            ang = lambda p: math.degrees(math.atan2(p.y - c.y, p.x - c.x)) % 360
            s = e.Vertexes[0].Point
            t = e.Vertexes[-1].Point
            m = e.valueAt((e.FirstParameter + e.LastParameter) / 2)
            a_s, a_e, a_m = ang(s), ang(t), ang(m)
            ccw = lambda a, b: (b - a) % 360
            if ccw(a_s, a_m) < ccw(a_s, a_e):
                a1, a2 = a_s, a_e
            else:
                a1, a2 = a_e, a_s
            self._g((0, "ARC"), (8, layer), (10, self._f(c.x)), (20, self._f(c.y)), (30, "0.0"),
                    (40, self._f(r)), (50, self._f(a1)), (51, self._f(a2)))
        else:
            pts = e.discretize(Deflection=0.01)
            for a, b in zip(pts, pts[1:]):
                self.line(a, b, layer)

    def face(self, f):
        outer = f.OuterWire
        for w in f.Wires:
            layer = "AUSSEN" if w.isSame(outer) else "INNEN"
            for e in w.Edges:
                self.edge(e, layer)

    def save(self, path):
        h = []
        add = lambda *p: h.extend("%d\n%s\n" % (c, v) for c, v in p)
        add((0, "SECTION"), (2, "HEADER"), (9, "$ACADVER"), (1, "AC1009"),
            (9, "$INSUNITS"), (70, 4), (0, "ENDSEC"))
        add((0, "SECTION"), (2, "TABLES"))
        add((0, "TABLE"), (2, "LTYPE"), (70, 1), (0, "LTYPE"), (2, "CONTINUOUS"), (70, 0),
            (3, "Solid line"), (72, 65), (73, 0), (40, "0.0"), (0, "ENDTAB"))
        add((0, "TABLE"), (2, "LAYER"), (70, len(self.LAYERS)))
        for n, col in self.LAYERS:
            add((0, "LAYER"), (2, n), (70, 0), (62, col), (6, "CONTINUOUS"))
        add((0, "ENDTAB"), (0, "ENDSEC"))
        add((0, "SECTION"), (2, "ENTITIES"))
        with open(path, "w", encoding="ascii", newline="\r\n") as fh:
            fh.write("".join(h) + "".join(self.ent) + "0\nENDSEC\n0\nEOF\n")


def dxf_check(path, expected_loops):
    """Liest die DXF zurück und prüft, dass alle Konturen geschlossen sind."""
    with open(path) as fh:
        tok = [x.strip() for x in fh.read().splitlines()]
    pairs = list(zip(tok[0::2], tok[1::2]))
    ents, cur = [], None
    for c, v in pairs:
        if c == "0":
            if cur:
                ents.append(cur)
            cur = {"type": v}
        elif cur is not None:
            cur.setdefault(c, v)
    if cur:
        ents.append(cur)
    grid = {}

    def key(x, y, tol=1e-3):
        gx, gy = int(math.floor(x / 0.01)), int(math.floor(y / 0.01))
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                for p in grid.get((gx + i, gy + j), []):
                    if abs(p[0] - x) < tol and abs(p[1] - y) < tol:
                        return p
        grid.setdefault((gx, gy), []).append((x, y))
        return (x, y)

    adj = {}
    loops_circle = 0

    def link(a, b):
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    for e in ents:
        t = e["type"]
        if t == "LINE":
            link(key(float(e["10"]), float(e["20"])), key(float(e["11"]), float(e["21"])))
        elif t == "ARC":
            cx, cy, r = float(e["10"]), float(e["20"]), float(e["40"])
            a1, a2 = math.radians(float(e["50"])), math.radians(float(e["51"]))
            link(key(cx + r * math.cos(a1), cy + r * math.sin(a1)),
                 key(cx + r * math.cos(a2), cy + r * math.sin(a2)))
        elif t == "CIRCLE":
            loops_circle += 1
    bad = [k for k, v in adj.items() if len(v) != 2]
    seen, loops = set(), 0
    for k in adj:
        if k in seen:
            continue
        loops += 1
        stack = [k]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            stack.extend(adj[n])
    loops += loops_circle
    ok = not bad and loops == expected_loops
    log("  %s: %d Konturen (erwartet %d), offene Enden: %d → %s"
        % (os.path.relpath(path, OUT), loops, expected_loops, len(bad), "OK" if ok else "FEHLER"))
    if not ok:
        raise RuntimeError("DXF-Prüfung fehlgeschlagen: " + path)


# ═════════════════════════════════════════════════════════════════════
#  Nesting: MaxRects (Best Short Side Fit), 90°-Drehung erlaubt
# ═════════════════════════════════════════════════════════════════════

class MaxRects:
    def __init__(self, w, h):
        self.free = [(0.0, 0.0, w, h)]

    def insert(self, w, h, rot_ok=True):
        best = None
        for (fx, fy, fw, fh) in self.free:
            for (rw, rh, rot) in [(w, h, False)] + ([(h, w, True)] if rot_ok else []):
                if rw <= fw + 1e-9 and rh <= fh + 1e-9:
                    k = (min(fw - rw, fh - rh), max(fw - rw, fh - rh), fy, fx)
                    if best is None or k < best[0]:
                        best = (k, fx, fy, rw, rh, rot)
        if best is None:
            return None
        _, x, y, rw, rh, rot = best
        self._split(x, y, rw, rh)
        return x, y, rot

    def _split(self, x, y, w, h):
        new = []
        for f in self.free:
            fx, fy, fw, fh = f
            if x >= fx + fw or x + w <= fx or y >= fy + fh or y + h <= fy:
                new.append(f)
                continue
            if x > fx:
                new.append((fx, fy, x - fx, fh))
            if x + w < fx + fw:
                new.append((x + w, fy, fx + fw - x - w, fh))
            if y > fy:
                new.append((fx, fy, fw, y - fy))
            if y + h < fy + fh:
                new.append((fx, y + h, fw, fy + fh - y - h))

        def inside(a, b):
            return (a[0] >= b[0] - 1e-9 and a[1] >= b[1] - 1e-9 and
                    a[0] + a[2] <= b[0] + b[2] + 1e-9 and a[1] + a[3] <= b[1] + b[3] + 1e-9)
        self.free = [a for i, a in enumerate(new)
                     if not any(j != i and inside(a, b) and (a != b or j < i)
                                for j, b in enumerate(new))]


def nest(prof, n_sets, width, height):
    """Versucht n_sets komplette Sätze auf width × height zu legen.
    Rückgabe: Liste (Teiltyp, x, y, rot) oder None."""
    items = []
    for k, (face, cnt, *_rest) in prof.items():
        bb = face.BoundBox
        items += [(k, bb.XLength, bb.YLength)] * (cnt * n_sets)
    items.sort(key=lambda it: (-it[1] * it[2], it[0]))
    mr = MaxRects(width + GAP, height + GAP)
    out = []
    for k, w, h in items:
        r = mr.insert(w + GAP, h + GAP)
        if r is None:
            return None
        out.append((k, r[0], r[1], r[2]))
    return out


def max_sets(prof, width, height):
    best, n = None, 1
    while True:
        r = nest(prof, n, width, height)
        if r is None:
            return n - 1, best
        best, n = r, n + 1


def placed_faces(prof, layout, ox, oy):
    return [(k, moved(prof[k][0], ox + x, oy + y, rot)) for (k, x, y, rot) in layout]


def check_nest(faces, x0, y0, x1, y1, what):
    bad = 0
    bbs = [f.BoundBox for _, f in faces]
    for b in bbs:
        if b.XMin < x0 - 1e-6 or b.YMin < y0 - 1e-6 or b.XMax > x1 + 1e-6 or b.YMax > y1 + 1e-6:
            bad += 1
    for i in range(len(bbs)):
        for j in range(i + 1, len(bbs)):
            a, b = bbs[i], bbs[j]
            dx = max(b.XMin - a.XMax, a.XMin - b.XMax)
            dy = max(b.YMin - a.YMax, a.YMin - b.YMax)
            if max(dx, dy) < GAP - 1e-6:
                bad += 1
    log("  %s: %d Teile, Abstand ≥ %.0f mm, innerhalb der Fläche → %s"
        % (what, len(faces), GAP, "OK" if not bad else "FEHLER (%d)" % bad))
    if bad:
        raise RuntimeError("Nesting fehlerhaft: " + what)


def write_dxf_faces(path, faces, labels=True):
    d = DXF()
    loops = 0
    for k, f in faces:
        d.face(f)
        loops += len(f.Wires)
        if labels:
            bb = f.BoundBox
            d.text(bb.XMin + 2, bb.YMax + 1.5, 4, k)
    d.save(path)
    dxf_check(path, loops)


# ═════════════════════════════════════════════════════════════════════
#  SVG-Hilfen
# ═════════════════════════════════════════════════════════════════════

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def svg_doc(w_mm, h_mm, body):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" '
            'viewBox="0 0 %g %g" font-family="%s">\n'
            '<rect width="100%%" height="100%%" fill="#ffffff"/>\n%s</svg>\n'
            % (w_mm, h_mm, w_mm, h_mm, FONT.replace('"', "'"), body))


def text(x, y, s, size=3.5, anchor="start", style="", fill="#1a1a1a"):
    st = ' font-style="italic"' if "i" in style else ""
    st += ' font-weight="bold"' if "b" in style else ""
    return ('<text x="%.2f" y="%.2f" font-size="%.2f" text-anchor="%s" fill="%s"%s>%s</text>\n'
            % (x, y, size, anchor, fill, st, esc(s)))


def face_path_2d(f, tf, fill="#ead2a8", stroke="#3b2a1a", sw=0.35):
    d = ""
    for w in f.Wires:
        pts = [tf(p) for p in wire_points(w, 0.05)]
        d += "M" + " L".join("%.3f,%.3f" % p for p in pts) + " Z "
    return '<path d="%s" fill="%s" fill-rule="evenodd" stroke="%s" stroke-width="%g"/>\n' % (
        d, fill, stroke, sw)


def to_pdf(svg_path, pdf_path):
    try:
        subprocess.run(["inkscape", svg_path, "--export-type=pdf",
                        "--export-text-to-path", "--export-filename=" + pdf_path],
                       check=True, capture_output=True)
        return True
    except Exception as ex:   # noqa
        log("  (PDF-Export übersprungen: %s)" % ex)
        return False


# ═════════════════════════════════════════════════════════════════════
#  Zuschnitt-Zeichnungen
# ═════════════════════════════════════════════════════════════════════

def zuschnitt_svg(path, prof, faces, area_w, area_h, title, subtitle, sheet_outline=False):
    margin, head, foot = 12.0, 22.0, 30.0
    scale = min(1.0, 400.0 / area_w) if not sheet_outline else 380.0 / area_w
    W_mm = area_w * scale + 2 * margin
    H_mm = area_h * scale + 2 * margin + head + foot
    oy = margin + head
    tf = lambda p: (margin + p.x * scale, oy + (area_h - p.y) * scale)
    body = text(margin, margin + 6, title, 6, style="b")
    body += text(margin, margin + 13, subtitle, 3.6, style="i")
    if sheet_outline:
        body += ('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="#f5f0e6" '
                 'stroke="#888" stroke-width="0.3"/>\n'
                 % (margin, oy, area_w * scale, area_h * scale))
    sw = 0.35 if scale > 0.5 else 0.15
    for k, f in faces:
        body += face_path_2d(f, tf, sw=sw)
        bb = f.BoundBox
        cx, cy = tf(V((bb.XMin + bb.XMax) / 2, (bb.YMin + bb.YMax) / 2, 0))
        fs = 5.0 if scale > 0.5 else 2.2
        body += text(cx, cy + fs * 0.35, k, fs, "middle", "b", "#7a3e12")
    y = oy + area_h * scale + 8
    x = margin
    for k, (face, cnt, de, en, sw_) in prof.items():
        bb = face.BoundBox
        body += text(x, y, "%s  %s  %d×  %.1f × %.1f mm" % (k, de, cnt, bb.XLength, bb.YLength), 3.4)
        x += (W_mm - 2 * margin) / 2
        if x > W_mm - margin - 10:
            x, y = margin, y + 5.5
    body += text(margin, H_mm - margin + 2,
                 "t = %.2f mm · Spiel c = %.2f mm · Fräser Ø %.1f mm · Dogbones r = %.2f mm · "
                 "Layer AUSSEN / INNEN (Innenkonturen zuerst)" % (T, C, TOOL_D, R_DB), 3.0,
                 fill="#555")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg_doc(W_mm, H_mm, body))


# ═════════════════════════════════════════════════════════════════════
#  Isometrische Darstellung (Maleralgorithmus über B-Rep-Flächen)
# ═════════════════════════════════════════════════════════════════════

VIEW = V(-0.45, -1.0, 0.75).normalize()          # zum Betrachter
RIGHT = V(0, 0, 1).cross(VIEW).normalize()
UP = VIEW.cross(RIGHT).normalize()
LIGHT = V(-0.35, -0.55, 1.0).normalize()
WOOD = (0xe9, 0xcf, 0xa2)
WOOD_ALT = (0xd9, 0xb3, 0x7c)


def _shade(n, base):
    k = 0.58 + 0.42 * max(0.0, n.dot(LIGHT))
    return "#%02x%02x%02x" % tuple(min(255, int(c * k)) for c in base)


def iso_polys(solids):
    """solids: [(label, solid, farbe)] → Liste (tiefe, punkte-listen, farbe) sortiert."""
    parts = []
    for label, s, base in solids:
        polys = []
        for f in s.Faces:
            u0, u1, v0, v1 = f.ParameterRange
            n = f.normalAt((u0 + u1) / 2, (v0 + v1) / 2)
            c = f.CenterOfMass
            if s.isInside(c + n * 0.05, 1e-4, False):
                n = -n
            if n.dot(VIEW) <= 1e-6:
                continue
            loops = [[(p.dot(RIGHT), -p.dot(UP)) for p in wire_points(w, 0.2)] for w in f.Wires]
            polys.append((c.dot(VIEW), loops, _shade(n, base)))
        polys.sort(key=lambda t: t[0])
        cm = s.BoundBox.Center
        parts.append((cm.dot(VIEW), label, cm, polys))
    parts.sort(key=lambda t: t[0])
    return parts


def iso_svg(solids, x0, y0, w, h, labels=True):
    parts = iso_polys(solids)
    xs = [p[0] for _, _, _, pl in parts for _, loops, _ in pl for lp in loops for p in lp]
    ys = [p[1] for _, _, _, pl in parts for _, loops, _ in pl for lp in loops for p in lp]
    sc = min(w / (max(xs) - min(xs)), h / (max(ys) - min(ys)))
    ox = x0 + (w - (max(xs) - min(xs)) * sc) / 2 - min(xs) * sc
    oy = y0 + (h - (max(ys) - min(ys)) * sc) / 2 - min(ys) * sc
    out = ""
    for _, label, cm, polys in parts:
        for _, loops, col in polys:
            d = ""
            for lp in loops:
                d += "M" + " L".join("%.3f,%.3f" % (ox + a * sc, oy + b * sc) for a, b in lp) + " Z "
            out += ('<path d="%s" fill="%s" fill-rule="evenodd" stroke="#3b2a1a" '
                    'stroke-width="0.18" stroke-linejoin="round"/>\n' % (d, col))
    if labels:
        # je Teiltyp nur eine Marke, am vordersten Exemplar
        front = {}
        for depth, label, cm, _ in parts:
            if label and (label not in front or depth > front[label][0]):
                front[label] = (depth, cm)
        for label, (_, cm) in sorted(front.items()):
            px, py = ox + cm.dot(RIGHT) * sc, oy - cm.dot(UP) * sc
            out += ('<circle cx="%.2f" cy="%.2f" r="3.2" fill="#ffffff" stroke="#7a3e12" '
                    'stroke-width="0.4"/>\n' % (px, py))
            out += text(px, py + 1.4, label, 4, "middle", "b", "#7a3e12")
    return out


# ═════════════════════════════════════════════════════════════════════
#  Montageanleitung (Englisch / Kiswahili)
# ═════════════════════════════════════════════════════════════════════

STEPS = [
    ("Sort the parts. Each box needs 2 × A, 2 × B, 1 × C and 4 × D. Put aside damaged parts.",
     "Panga vipande. Kila sanduku linahitaji A × 2, B × 2, C × 1 na D × 4. "
     "Weka kando vipande vilivyoharibika."),
    ("Sand all faces and edges before gluing (grit 120, then 180). "
     "Do not sand the tabs and fingers of the joints – they would become loose.",
     "Sugua nyuso na kingo zote kwa msasa kabla ya kugundisha (namba 120, kisha 180). "
     "Usisugue ndimi na meno ya viungo – vitalegea."),
    ("Dry fit: assemble the whole box without glue. Every tab must go in by hand "
     "or with light taps of a wooden mallet. Then take it apart again.",
     "Jaribio bila gundi: unganisha sanduku zima kwanza bila gundi. Kila ulimi uingie "
     "kwa mkono au kwa kugonga kidogo kwa nyundo ya mbao. Kisha lifungue tena."),
    ("Lay one side wall A flat, inside up, with the slots for the bottom at the lower edge. "
     "Put a little glue into its slots and insert the bottom C and the four dividers D. "
     "C and A fit only one way round: the smallest compartment is at the same end.",
     "Laza ubao wa pembeni A mezani, upande wa ndani juu, matundu ya ubao wa chini yakiwa "
     "chini. Weka gundi kidogo kwenye matundu yake, kisha chomeka ubao wa chini C na "
     "vitenganishi vinne D. C na A zinaingiana kwa njia moja tu: chumba kidogo kabisa "
     "kiko upande mmoja."),
    ("Put glue into the slots of the second side wall A and press it on from above.",
     "Weka gundi kwenye matundu ya ubao wa pembeni A wa pili na uubonyeze juu yake."),
    ("Glue on the two end walls B: the fingers interlock, the tab of the bottom goes into "
     "the slot. The end walls have a finger recess at the top.",
     "Gundisha mbao mbili za mwisho B: meno yanaingiana, ulimi wa ubao wa chini unaingia "
     "kwenye tundu. Mbao za mwisho zina mfuko wa kidole juu."),
    ("Clamp lightly or tie with a strap. Check the right angles with a square, or measure "
     "both diagonals – they must be equal. Wipe off squeezed-out glue at once with a damp cloth.",
     "Bana kidogo kwa vibano au funga kwa kamba. Kagua pembe kwa pembemraba, au pima "
     "milalo yote miwili – lazima iwe sawa. Futa gundi inayotoka mara moja kwa kitambaa "
     "chenye unyevu."),
    ("Leave clamped for 1 hour, do not use for 24 hours. Then sand the tab ends flush "
     "and round the edges slightly. Glue sets faster in hot weather – work quickly.",
     "Acha ikiwa imebanwa kwa saa 1, usiitumie kwa saa 24. Kisha sugua ncha za ndimi "
     "ziwe sawa na lainisha kingo kidogo. Gundi hukauka haraka wakati wa joto – fanya kazi "
     "haraka."),
]

TOOLS = [
    ("Wood glue (white PVA, D2 or D3)", "Gundi ya mbao (nyeupe, PVA, D2 au D3)"),
    ("Sandpaper grit 120 and 180, sanding block", "Msasa namba 120 na 180, kipande cha kusugulia"),
    ("Wooden or rubber mallet", "Nyundo ya mbao au ya mpira"),
    ("2 clamps or a strap, try square", "Vibano 2 au kamba, pembemraba"),
    ("Damp cloth, small stick to spread glue", "Kitambaa chenye unyevu, kijiti cha kupaka gundi"),
]


def wrap(s, n):
    words, lines, cur = s.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    return lines


def montage(prof, asm, outdir):
    colors = {"A": WOOD, "B": WOOD_ALT, "C": WOOD, "D": WOOD_ALT}
    expl = {"Seitenwand_vorn": V(0, -70, 0), "Seitenwand_hinten": V(0, 70, 0),
            "Stirnwand_Fach1": V(-60, 0, 0), "Stirnwand_Fach5": V(60, 0, 0),
            "Boden": V(0, 0, -45)}
    ex = []
    for n, k, s in asm:
        s2 = s.copy()
        s2.translate(expl.get(n, V(0, 0, 70)))
        ex.append((k, s2, colors[k]))

    # Seite 1
    b = text(15, 22, "Learning card box A7 – assembly instructions", 7, style="b")
    b += text(15, 30, "Sanduku la kadi za kujifunzia A7 – maelekezo ya kuunganisha", 5.2, style="i")
    b += text(15, 37, "Leitner box, 5 compartments · 6 mm plywood · outside %.0f × %.0f × %.0f mm"
              % (L, W, HW), 3.6, fill="#444")
    b += iso_svg(ex, 15, 45, 180, 120)
    y = 178
    b += text(15, y, "Parts per box", 4.6, style="b")
    b += text(110, y, "Vipande kwa kila sanduku", 4.6, style="bi")
    y += 8
    for k, (face, cnt, de, en, sw) in prof.items():
        b += ('<circle cx="18.5" cy="%.2f" r="3" fill="#fff" stroke="#7a3e12" stroke-width="0.4"/>\n'
              % (y - 1.3))
        b += text(18.5, y, k, 3.8, "middle", "b", "#7a3e12")
        b += text(25, y, "%s × %d" % (en, cnt), 3.8)
        b += text(110, y, "%s × %d" % (sw, cnt), 3.8, style="i")
        y += 8
    y += 4
    b += text(15, y, "Tools and material", 4.6, style="b")
    b += text(110, y, "Vifaa", 4.6, style="bi")
    y += 7
    for en, sw in TOOLS:
        b += text(15, y, "· " + en, 3.5)
        b += text(110, y, "· " + sw, 3.5, style="i")
        y += 6
    b += text(15, 287, "NgarumaVTC · parts milled by M+M Fräsdienstleistungen, Kappeln (Germany)",
              3.0, fill="#666")
    p1 = os.path.join(outdir, "montage-1.svg")
    with open(p1, "w", encoding="utf-8") as fh:
        fh.write(svg_doc(210, 297, b))

    # Seite 2: zwei Zustandsbilder + Schritte
    step4 = [(k, s, colors[k]) for n, k, s in asm
             if n not in ("Seitenwand_vorn", "Stirnwand_Fach1", "Stirnwand_Fach5")]
    full = [(k, s, colors[k]) for n, k, s in asm]
    b = text(15, 18, "Steps · Hatua", 6, style="b")
    b += iso_svg(step4, 15, 24, 85, 52, labels=False)
    b += iso_svg(full, 110, 24, 85, 52, labels=False)
    b += text(57, 82, "after step 4 · baada ya hatua 4", 3.2, "middle", "i", "#555")
    b += text(152, 82, "finished · tayari", 3.2, "middle", "i", "#555")
    y = 94
    for i, (en, sw) in enumerate(STEPS):
        b += ('<circle cx="19" cy="%.2f" r="3.4" fill="#7a3e12"/>\n' % (y - 1.3))
        b += text(19, y, str(i + 1), 4, "middle", "b", "#fff")
        for ln in wrap(en, 98):
            b += text(26, y, ln, 3.6)
            y += 4.6
        for ln in wrap(sw, 98):
            b += text(26, y, ln, 3.6, style="i", fill="#3d3d3d")
            y += 4.6
        y += 3.6
    b += text(15, 287, "Kiswahili text: please have it checked locally · Tafadhali kagueni "
              "maandishi ya Kiswahili.", 3.0, fill="#666")
    p2 = os.path.join(outdir, "montage-2.svg")
    with open(p2, "w", encoding="utf-8") as fh:
        fh.write(svg_doc(210, 297, b))
    if y > 282:
        log("  WARNUNG: Montageseite 2 läuft über (y = %.0f)" % y)

    pdfs = []
    for p in (p1, p2):
        q = p[:-4] + ".pdf"
        if to_pdf(p, q):
            pdfs.append(q)
    if len(pdfs) == 2:
        try:
            subprocess.run(["pdfunite"] + pdfs + [os.path.join(outdir, "montage.pdf")],
                           check=True, capture_output=True)
            for q in pdfs:
                os.remove(q)
        except Exception as ex_:   # noqa
            log("  (pdfunite fehlt – Einzel-PDFs bleiben: %s)" % ex_)


# ═════════════════════════════════════════════════════════════════════
#  FreeCAD-Dokument, Exporte
# ═════════════════════════════════════════════════════════════════════

def build_document(prof, asm, set_faces):
    doc = App.newDocument("Lernkasten")
    sp = doc.addObject("Spreadsheet::Sheet", "Parameter")
    rows = [("t", T, "Materialstärke"), ("c", C, "Spiel"), ("tool_d", TOOL_D, "Fräser"),
            ("L", L, "Außenlänge"), ("W", W, "Außenbreite"), ("Hw", HW, "Wandhöhe"),
            ("Hd", HD, "Trennwandhöhe über Boden"), ("s", S, "Bodenunterkante")]
    sp.set("A1", "Name"), sp.set("B1", "Wert [mm]"), sp.set("C1", "Bedeutung")
    for i, (n, v, d) in enumerate(rows):
        sp.set("A%d" % (i + 2), n)
        sp.set("B%d" % (i + 2), "%g" % v)
        sp.set("C%d" % (i + 2), d)
    for i, a in enumerate(FACH):
        sp.set("A%d" % (len(rows) + 2 + i), "Fach%d" % (i + 1))
        sp.set("B%d" % (len(rows) + 2 + i), "%g" % a)
        sp.set("C%d" % (len(rows) + 2 + i), "lichte Länge")
    g1 = doc.addObject("App::DocumentObjectGroup", "Zusammenbau")
    objs = []
    for n, k, s in asm:
        o = doc.addObject("Part::Feature", n)
        o.Shape = s
        g1.addObject(o)
        objs.append(o)
    g2 = doc.addObject("App::DocumentObjectGroup", "Zuschnitt")
    for i, (k, f) in enumerate(set_faces):
        o = doc.addObject("Part::Feature", "Zuschnitt_%s_%d" % (prof[k][2], i + 1))
        o.Shape = f.extrude(V(0, 0, T))
        o.Placement.Base = V(0, -W - 80, 0)
        g2.addObject(o)
    doc.recompute()
    doc.saveAs(os.path.join(OUT, "lernkasten.FCStd"))
    try:
        import Import
        Import.export(objs, os.path.join(OUT, "lernkasten.step"))
    except Exception:   # noqa
        Part.makeCompound([s for _, _, s in asm]).exportStep(os.path.join(OUT, "lernkasten.step"))
    return doc


def main():
    os.makedirs(os.path.join(OUT, "dxf"), exist_ok=True)
    log("Lernkasten A7: %.0f × %.0f × %.0f mm, t = %.2f, Fächer %s"
        % (L, W, HW, T, " / ".join("%g" % f for f in FACH)))
    prof, asm = build_parts()
    check_assembly(asm)

    log("— DXF Einzelteile —")
    for k, (face, cnt, de, en, sw) in prof.items():
        write_dxf_faces(os.path.join(OUT, "dxf", "%s_%s.dxf" % (k, de.lower())),
                        [(k, moved(face, 0, 0))], labels=False)

    log("— Zuschnitt ein Satz —")
    lay = nest(prof, 1, 420.0, 600.0)
    set_faces = placed_faces(prof, lay, 0, 0)
    bb = Part.makeCompound([f for _, f in set_faces]).BoundBox
    check_nest(set_faces, 0, 0, 420, 600, "Satz")
    write_dxf_faces(os.path.join(OUT, "zuschnitt.dxf"), set_faces)
    zuschnitt_svg(os.path.join(OUT, "zuschnitt.svg"), prof, set_faces, bb.XMax, bb.YMax,
                  "Lernkasten A7 – Zuschnitt für einen Kasten",
                  "9 Teile · Außenmaß %.0f × %.0f × %.0f mm · Sperrholz %.0f mm" % (L, W, HW, T))
    to_pdf(os.path.join(OUT, "zuschnitt.svg"), os.path.join(OUT, "zuschnitt.pdf"))

    log("— Plattennest %.0f × %.0f —" % SHEET)
    uw, uh = SHEET[0] - 2 * SHEET_MARGIN, SHEET[1] - 2 * SHEET_MARGIN
    n, lay = max_sets(prof, uw, uh)
    sheet_faces = placed_faces(prof, lay, SHEET_MARGIN, SHEET_MARGIN)
    check_nest(sheet_faces, SHEET_MARGIN, SHEET_MARGIN,
               SHEET[0] - SHEET_MARGIN, SHEET[1] - SHEET_MARGIN, "Platte")
    d = DXF()
    for k, f in sheet_faces:
        d.face(f)
    for a, b in [((0, 0), (SHEET[0], 0)), ((SHEET[0], 0), SHEET), (SHEET, (0, SHEET[1])),
                 ((0, SHEET[1]), (0, 0))]:
        d.line(V(*a, 0), V(*b, 0), "INFO")
    d.save(os.path.join(OUT, "platte.dxf"))
    dxf_check(os.path.join(OUT, "platte.dxf"), sum(len(f.Wires) for _, f in sheet_faces) + 1)
    need = int(math.ceil(N_BOXES * (1 + SCRAP)))
    sheets = int(math.ceil(need / float(n)))
    used = sum(f.Area for _, f in sheet_faces) / (SHEET[0] * SHEET[1])
    log("  %d Kästen pro Platte (Ausnutzung %.0f %%)" % (n, used * 100))
    log("  %d Kästen + %.0f %% Ausschuss = %d → %d Platten %.0f × %.0f mm"
        % (N_BOXES, SCRAP * 100, need, sheets, SHEET[0], SHEET[1]))
    zuschnitt_svg(os.path.join(OUT, "platte.svg"), prof, sheet_faces, SHEET[0], SHEET[1],
                  "Lernkasten A7 – Plattennest %.0f × %.0f mm" % SHEET,
                  "%d Kästen pro Platte · für %d Kästen (+%.0f %%) %d Platten · Teile teils um 90° gedreht"
                  % (n, N_BOXES, SCRAP * 100, sheets), sheet_outline=True)
    to_pdf(os.path.join(OUT, "platte.svg"), os.path.join(OUT, "platte.pdf"))

    log("— Montageanleitung —")
    montage(prof, asm, OUT)

    log("— FreeCAD-Dokument / STEP —")
    build_document(prof, asm, set_faces)
    log("Fertig: " + OUT)


if not os.environ.get("LERNKASTEN_NOMAIN"):
    main()
