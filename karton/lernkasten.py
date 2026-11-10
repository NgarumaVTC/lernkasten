# -*- coding: utf-8 -*-
"""
Lernkasten DIN A7 – fünf Fächer, braune Wellpappe
=================================================

Parametrische FreeCAD-Konstruktion für NgarumaVTC.

Aufruf (headless):   cd karton && freecadcmd lernkasten.py
Kartonstärke testen: LERNKASTEN_T=4 freecadcmd lernkasten.py

Aufbau:
  1. Fünf offene Innenkästen, gleich breit und hoch, verschieden tief.
     Je Kasten: Boden, 2 Längsseiten (stehen auf dem Boden), 2 Stirnwände
     (zwischen den Längsseiten). Kanten außen mit KKP-Winkeln verklebt.
  2. Die fünf Innenkästen aneinander geklebt (Trennwand = 2 Stirnwände).
  3. Außenkasten ohne Winkel flächig auf den Block gesprüht: Boden unter
     den Block, Stirnwände an die Enden, Längsseiten über alles.

Wellen in allen Wänden senkrecht (von oben sieht man in die Wellen), in den
Böden längs.

Erzeugt in ./build/:
  lernkasten.FCStd   Zusammenbau + Parameter
  lernkasten.step    Zusammenbau
  dxf/<teil>.dxf     Einzelteile (Layer AUSSEN, Wellenpfeil auf INFO)
  zuschnitt.pdf      Teileliste, Skizzen eines Satzes, KKP-Streifen, Bedarf
  bogen.dxf/.pdf     Nest auf einem Wellpappbogen
  montage.pdf        Montageanleitung Englisch / Kiswahili
"""

import math
import os
import subprocess

import FreeCAD as App
import Part

V = App.Vector

# ═════════════════════════════════════════════════════════════════════
#  PARAMETER  (alle Maße in mm)
# ═════════════════════════════════════════════════════════════════════

T = float(os.environ.get("LERNKASTEN_T", "3.0"))   # Kartonstärke – AM ECHTEN KARTON MESSEN!
K = 0.25           # Dicke KKP 205 g (nur Info, nicht im Modell)

CARD_W, CARD_H = 105.0, 74.0   # DIN A7, quer stehend
PLAY_W = 4.0                   # Luft der Karte in der Breite

FACH = [25.0, 40.0, 60.0, 90.0, 135.0]   # lichte Fachlängen, Fach 1 … 5

H = 50.0           # Außenhöhe

ANGLE_LEG = 15.0   # Schenkelbreite der KKP-Winkel (Streifen 2 × so breit)
KKP_SHEET = (210.0, 297.0)   # KKP-Bogen A4

# Serie
BOARD = (1200.0, 800.0)      # Wellpappbogen; Wellen laufen parallel zur 2. Zahl
BOARD_MARGIN = 10.0          # Randabstand
GAP = 2.0                    # Teileabstand im Nest
N_BOXES = 120
SCRAP = 0.05                 # Ausschuss-Zuschlag

FONT = "'Latin Modern Roman', 'CMU Serif', serif"

# ═════════════════════════════════════════════════════════════════════
#  Abgeleitete Maße
# ═════════════════════════════════════════════════════════════════════

WI = CARD_W + PLAY_W           # lichte Breite
HI = H - 2 * T                 # Wandhöhe Innenkasten (steht auf Innen- und Außenboden)
WB = WI + 2 * T                # Breite Block (= Innenkasten außen)
LBOX = [l + 2 * T for l in FACH]   # Länge der Innenkästen außen
LB = sum(LBOX)                 # Länge Block
L = LB + 2 * T                 # Außenlänge
W = WB + 2 * T                 # Außenbreite

BOX_X = []                     # x-Anfang je Innenkasten
_x = T
for _l in LBOX:
    BOX_X.append(_x)
    _x += _l

try:
    BASE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    BASE = os.getcwd()
OUT = os.environ.get("LERNKASTEN_OUT", os.path.join(BASE, "build"))


def log(*a):
    print(" ".join(str(x) for x in a), flush=True)


# ═════════════════════════════════════════════════════════════════════
#  Teile
#  2D-Zuschnitt: u = quer zur Welle, v = entlang der Welle.
#  Im Bogen laufen die Wellen in v-Richtung, Teile werden nie gedreht.
# ═════════════════════════════════════════════════════════════════════

def rect(u0, v0, u1, v1):
    pts = [V(u0, v0, 0), V(u1, v0, 0), V(u1, v1, 0), V(u0, v1, 0), V(u0, v0, 0)]
    return Part.Face(Part.makePolygon(pts))


def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x0, y0, z0))


# Teile-Tabelle: Schlüssel → (quer, entlang, Stück, deutsch, englisch, kiswahili)
def part_table():
    p = {}
    p["A"] = (L, H, 2, "Außen-Längsseite", "Outer long wall", "Ukuta mrefu wa nje")
    p["E"] = (WB, H, 2, "Außen-Stirnwand", "Outer end wall", "Ukuta wa mwisho wa nje")
    p["U"] = (WB, LB, 1, "Außenboden", "Outer bottom", "Kitako cha nje")
    p["S"] = (WI, HI, 2 * len(FACH), "Stirnwand innen", "Inner end wall",
              "Ukuta wa mwisho wa ndani")
    for i, lb in enumerate(LBOX):
        n = i + 1
        p["L%d" % n] = (lb, HI, 2, "Längsseite Kasten %d" % n, "Long wall, box %d" % n,
                        "Ukuta mrefu, sanduku %d" % n)
    for i, lb in enumerate(LBOX):
        n = i + 1
        p["B%d" % n] = (WB, lb, 1, "Boden Kasten %d" % n, "Bottom, box %d" % n,
                        "Kitako, sanduku %d" % n)
    return p


def build_parts():
    """Rückgabe: prof {key: (face2d, stück, de, en, sw)}, asm [(name, key, solid)]."""
    tab = part_table()
    prof = {k: (rect(0, 0, a, b), c, de, en, sw) for k, (a, b, c, de, en, sw) in tab.items()}
    asm = []
    # Außenkasten
    asm.append(("Aussen_Boden", "U", box(T, T, 0, LB, WB, T)))
    asm.append(("Aussen_Stirn_Fach1", "E", box(0, T, 0, T, WB, H)))
    asm.append(("Aussen_Stirn_Fach5", "E", box(L - T, T, 0, T, WB, H)))
    asm.append(("Aussen_Seite_vorn", "A", box(0, 0, 0, L, T, H)))
    asm.append(("Aussen_Seite_hinten", "A", box(0, W - T, 0, L, T, H)))
    # Innenkästen
    for i, (x0, lb) in enumerate(zip(BOX_X, LBOX)):
        n = i + 1
        asm.append(("Kasten%d_Boden" % n, "B%d" % n, box(x0, T, T, lb, WB, T)))
        asm.append(("Kasten%d_Seite_vorn" % n, "L%d" % n, box(x0, T, 2 * T, lb, T, HI)))
        asm.append(("Kasten%d_Seite_hinten" % n, "L%d" % n, box(x0, W - 2 * T, 2 * T, lb, T, HI)))
        asm.append(("Kasten%d_Stirn_a" % n, "S", box(x0, 2 * T, 2 * T, T, WI, HI)))
        asm.append(("Kasten%d_Stirn_b" % n, "S", box(x0 + lb - T, 2 * T, 2 * T, T, WI, HI)))
    # Stückzahlen gegen Zusammenbau prüfen
    for k, (_, cnt, *_r) in prof.items():
        got = sum(1 for _, kk, _ in asm if kk == k)
        assert got == cnt, "%s: %d im Zusammenbau, %d in der Liste" % (k, got, cnt)
    return prof, asm


def angles_of_box(lb):
    """KKP-Winkel eines Innenkastens: Liste (Kante, Länge)."""
    return ([("vertical", H - T)] * 4 +
            [("bottom long", lb)] * 2 +
            [("bottom end", WB)] * 2)


def angle_solids(x0, lb):
    """Nur zur Darstellung: KKP-Winkel als dünne Platten außen am Innenkasten."""
    k, a = 0.6, ANGLE_LEG        # optisch etwas dicker als echt
    y0, y1 = T, T + WB
    z0, z1 = T, H
    x1 = x0 + lb
    s = []
    for xc, sx in ((x0, 1), (x1, -1)):
        for yc, sy in ((y0, 1), (y1, -1)):
            # Schenkel auf der Längsseite
            s.append(box(xc if sx > 0 else xc - a, yc - k if sy > 0 else yc, z0, a, k, z1 - z0))
            # Schenkel auf der Stirnseite
            s.append(box(xc - k if sx > 0 else xc, yc if sy > 0 else yc - a, z0, k, a, z1 - z0))
    for yc, sy in ((y0, 1), (y1, -1)):
        s.append(box(x0, yc - k if sy > 0 else yc, z0, lb, k, a))
        s.append(box(x0, yc if sy > 0 else yc - a, z0 - k, lb, a, k))
    for xc, sx in ((x0, 1), (x1, -1)):
        s.append(box(xc - k if sx > 0 else xc, y0, z0, k, WB, a))
        s.append(box(xc if sx > 0 else xc - a, y0, z0 - k, a, WB, k))
    return s


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
    vol = sum(s.Volume for _, _, s in asm)
    log("  Außenmaß: %.1f × %.1f × %.1f mm" % (bb.XLength, bb.YLength, bb.ZLength))
    log("  Lichte Breite %.1f mm (Karte %.0f), lichte Höhe %.1f mm – Karte ragt %.0f mm heraus"
        % (WI, CARD_W, HI, CARD_H - HI))
    for k, l in enumerate(FACH):
        log("  Fach %d: %.0f mm lichte Länge ≈ %d Karten" % (k + 1, l, int(l / 0.25)))
    assert WI >= CARD_W and HI < CARD_H
    assert abs(bb.XLength - L) < 1e-6 and abs(bb.YLength - W) < 1e-6 and abs(bb.ZLength - H) < 1e-6
    # Hohlraum = Fächer: Gesamtvolumen − Material muss Summe der Fächer ergeben
    cav = L * W * H - vol
    exp = sum(FACH) * WI * HI
    if abs(cav - exp) > 1e-3:
        log("  Hohlraum %.0f mm³ ≠ Fächer %.0f mm³" % (cav, exp))
        ok = False
    log("  Kollisionsprüfung, Berührung, Hohlraum: %s" % ("OK" if ok else "FEHLER"))
    if not ok:
        raise RuntimeError("Zusammenbau fehlerhaft")


# ═════════════════════════════════════════════════════════════════════
#  KKP-Streifen
# ═════════════════════════════════════════════════════════════════════

def kkp_strips():
    """Alle Winkel eines Kastens, Streifenbreite 2·ANGLE_LEG.
    Rückgabe: [(länge, anzahl, kasten)], Streifen pro Bogen, Bögen je Kasten."""
    rows = []
    lengths = []
    for i, lb in enumerate(LBOX):
        cnt = {}
        for _, ln in angles_of_box(lb):
            cnt[round(ln, 2)] = cnt.get(round(ln, 2), 0) + 1
            lengths.append(ln)
        for ln, c in sorted(cnt.items(), reverse=True):
            rows.append((ln, c, i + 1))
    sw = 2 * ANGLE_LEG
    long_side = max(KKP_SHEET)
    strips_per_sheet = int(min(KKP_SHEET) // sw)
    too_long = [x for x in lengths if x > long_side]
    if too_long:
        raise RuntimeError("KKP-Winkel länger als Bogen: %s" % too_long)
    # First-Fit-Decreasing auf Streifen der Bogenlänge
    bins = []
    for ln in sorted(lengths, reverse=True):
        for b in bins:
            if sum(b) + ln <= long_side + 1e-9:
                b.append(ln)
                break
        else:
            bins.append([ln])
    sheets = len(bins) / float(strips_per_sheet)
    return rows, len(lengths), len(bins), strips_per_sheet, sheets


# ═════════════════════════════════════════════════════════════════════
#  DXF R12 (nur LINE / TEXT)
# ═════════════════════════════════════════════════════════════════════

class DXF:
    LAYERS = [("AUSSEN", 1), ("INFO", 8)]

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

    def face(self, f):
        for w in f.Wires:
            for e in w.Edges:
                self.line(e.Vertexes[0].Point, e.Vertexes[-1].Point, "AUSSEN")

    def flute_arrow(self, f):
        """Pfeil entlang der Welle (v-Richtung) auf Layer INFO."""
        bb = f.BoundBox
        cx = bb.XMin + min(12.0, bb.XLength / 2)
        y0, y1 = bb.YMin + 0.2 * bb.YLength, bb.YMin + 0.8 * bb.YLength
        a = min(3.0, 0.1 * bb.YLength)
        for y, s in ((y1, -1), (y0, 1)):
            self.line(V(cx, y, 0), V(cx - a, y + s * a, 0), "INFO")
            self.line(V(cx, y, 0), V(cx + a, y + s * a, 0), "INFO")
        self.line(V(cx, y0, 0), V(cx, y1, 0), "INFO")

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
    """Liest die DXF zurück und prüft, dass alle Schnittkonturen (AUSSEN) geschlossen sind."""
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
    for e in ents:
        if e["type"] == "LINE" and e.get("8") == "AUSSEN":
            a = key(float(e["10"]), float(e["20"]))
            b = key(float(e["11"]), float(e["21"]))
            adj.setdefault(a, []).append(b)
            adj.setdefault(b, []).append(a)
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
    ok = not bad and loops == expected_loops
    log("  %s: %d Konturen (erwartet %d), offene Enden: %d → %s"
        % (os.path.relpath(path, OUT), loops, expected_loops, len(bad), "OK" if ok else "FEHLER"))
    if not ok:
        raise RuntimeError("DXF-Prüfung fehlgeschlagen: " + path)


def moved(face, x, y):
    f = face.copy()
    bb = f.BoundBox
    f.translate(V(x - bb.XMin, y - bb.YMin, 0))
    return f


def write_dxf_faces(path, faces, labels=True, frame=None):
    d = DXF()
    for k, f in faces:
        d.face(f)
        d.flute_arrow(f)
        if labels:
            bb = f.BoundBox
            d.text(bb.XMin + 2, bb.YMax - 6, 4, k)
    if frame:
        w, h = frame
        for a, b in [((0, 0), (w, 0)), ((w, 0), (w, h)), ((w, h), (0, h)), ((0, h), (0, 0))]:
            d.line(V(*a, 0), V(*b, 0), "INFO")
    d.save(path)
    dxf_check(path, len(faces))


# ═════════════════════════════════════════════════════════════════════
#  Nesting: MaxRects (Best Short Side Fit), ohne Drehung (Wellenrichtung!)
# ═════════════════════════════════════════════════════════════════════

class MaxRects:
    def __init__(self, w, h):
        self.free = [(0.0, 0.0, w, h)]

    def insert(self, w, h):
        best = None
        for (fx, fy, fw, fh) in self.free:
            if w <= fw + 1e-9 and h <= fh + 1e-9:
                k = (min(fw - w, fh - h), max(fw - w, fh - h), fy, fx)
                if best is None or k < best[0]:
                    best = (k, fx, fy)
        if best is None:
            return None
        _, x, y = best
        self._split(x, y, w, h)
        return x, y

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
        out.append((k, r[0], r[1]))
    return out


def max_sets(prof, width, height):
    best, n = None, 1
    while True:
        r = nest(prof, n, width, height)
        if r is None:
            return n - 1, best
        best, n = r, n + 1


def placed_faces(prof, layout, ox, oy):
    return [(k, moved(prof[k][0], ox + x, oy + y)) for (k, x, y) in layout]


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


# ═════════════════════════════════════════════════════════════════════
#  SVG-Hilfen
# ═════════════════════════════════════════════════════════════════════

CARD = (0xc4, 0x93, 0x5a)       # Wellpappe braun
CARD_ALT = (0xa8, 0x78, 0x45)
CARD_OUT = (0xd6, 0xae, 0x7a)
PAPER = (0xf4, 0xef, 0xe1)      # KKP
INK = "#3b2a1a"
ACCENT = "#7a3e12"


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


def rect_svg(x, y, w, h, fill="#e6c79c", stroke=INK, sw=0.3, flutes=True, pitch=2.5):
    """Rechteck mit senkrechten Linien = Wellenrichtung."""
    out = ('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="%s" stroke="%s" '
           'stroke-width="%g"/>\n' % (x, y, w, h, fill, stroke, sw))
    if flutes and w > 2 * pitch:
        d = ""
        n = int(w / pitch)
        off = (w - n * pitch) / 2
        for i in range(1, n):
            xx = x + off + i * pitch
            d += "M%.3f,%.3f V%.3f " % (xx, y, y + h)
        out += '<path d="%s" stroke="#a9834f" stroke-width="%g" fill="none"/>\n' % (d, sw * 0.5)
    return out


def to_pdf(svg_path, pdf_path):
    try:
        subprocess.run(["inkscape", svg_path, "--export-type=pdf",
                        "--export-text-to-path", "--export-filename=" + pdf_path],
                       check=True, capture_output=True)
        return True
    except Exception as ex:   # noqa
        log("  (PDF-Export übersprungen: %s)" % ex)
        return False


def svgs_to_pdf(svgs, pdf_path):
    pdfs = []
    for p in svgs:
        q = p[:-4] + ".pdf"
        if to_pdf(p, q):
            pdfs.append(q)
    if len(pdfs) != len(svgs):
        return
    if len(pdfs) == 1:
        os.replace(pdfs[0], pdf_path)
        return
    try:
        subprocess.run(["pdfunite"] + pdfs + [pdf_path], check=True, capture_output=True)
        for q in pdfs:
            os.remove(q)
    except Exception as ex_:   # noqa
        log("  (pdfunite fehlt – Einzel-PDFs bleiben: %s)" % ex_)


# ═════════════════════════════════════════════════════════════════════
#  Zeichnungen: Satz und Bogen
# ═════════════════════════════════════════════════════════════════════

def nest_svg(faces, area_w, area_h, x0, y0, scale, outline):
    tf = lambda u, v: (x0 + u * scale, y0 + (area_h - v) * scale)
    b = ""
    if outline:
        b += ('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" fill="#f5f0e6" '
              'stroke="#888" stroke-width="0.3"/>\n' % (x0, y0, area_w * scale, area_h * scale))
    fs = max(1.6, min(4.0, 11 * scale))
    for k, f in faces:
        bb = f.BoundBox
        x, y = tf(bb.XMin, bb.YMax)
        b += rect_svg(x, y, bb.XLength * scale, bb.YLength * scale,
                      sw=0.3 if scale > 0.4 else 0.15, pitch=max(1.2, 6 * scale))
        cx, cy = tf((bb.XMin + bb.XMax) / 2, (bb.YMin + bb.YMax) / 2)
        b += ('<rect x="%.2f" y="%.2f" width="%.2f" height="%.2f" rx="0.6" fill="#ffffff" '
              'fill-opacity="0.85"/>\n' % (cx - fs * 0.45 * len(k) - 0.6, cy - fs * 0.75,
                                           fs * 0.9 * len(k) + 1.2, fs * 1.05))
        b += text(cx, cy, k, fs, "middle", "b", ACCENT)
    return b


def zuschnitt(prof, set_faces, set_w, set_h, kkp, board_info):
    """Seite A4 quer: Teileliste + Skizze eines Satzes + KKP + Bedarf."""
    Wp, Hp = 297.0, 210.0
    b = text(12, 16, "Lernkasten A7 aus Wellpappe – Zuschnitt", 6.5, style="b")
    b += text(12, 23, "Außenmaß %.0f × %.0f × %.0f mm · Kartonstärke t = %.2f mm · "
              "senkrechte Striche = Wellenrichtung" % (L, W, H, T), 3.6, style="i")
    # Tabelle links
    y = 34
    cols = (12, 22, 70, 84, 104)
    b += text(cols[0], y, "Teil", 3.4, style="b")
    b += text(cols[1], y, "Bezeichnung", 3.4, style="b")
    b += text(cols[2], y, "Stück", 3.4, style="b")
    b += text(cols[3], y, "quer", 3.4, style="b")
    b += text(cols[4], y, "längs Welle", 3.4, style="b")
    y += 2
    b += '<path d="M12,%.1f H128" stroke="#888" stroke-width="0.2"/>\n' % y
    y += 4.6
    area = 0.0
    for k, (face, cnt, de, en, sw) in prof.items():
        bb = face.BoundBox
        area += bb.XLength * bb.YLength * cnt
        b += text(cols[0], y, k, 3.3, style="b", fill=ACCENT)
        b += text(cols[1], y, de, 3.3)
        b += text(cols[2] + 6, y, "%d" % cnt, 3.3, "end")
        b += text(cols[3] + 14, y, "%.1f" % bb.XLength, 3.3, "end")
        b += text(cols[4] + 14, y, "%.1f" % bb.YLength, 3.3, "end")
        y += 4.6
    npcs = sum(c for _, c, *_ in prof.values())
    b += '<path d="M12,%.1f H128" stroke="#888" stroke-width="0.2"/>\n' % (y - 3)
    b += text(cols[1], y + 1, "%d Teile, %.3f m² Wellpappe netto" % (npcs, area / 1e6), 3.3,
              style="i")
    y += 10
    rows, n_ang, n_strips, per_sheet, sheets = kkp
    b += text(12, y, "KKP-Winkel (Karteikartenpapier 205 g)", 3.8, style="b")
    y += 5.2
    for ln in wrap("Streifen %.0f mm breit, mittig gefalzt (Schenkel %.0f mm). Je Innenkasten "
                   "4 senkrechte Ecken à %.0f mm und 4 Bodenkanten, alle außen. Der Außenkasten "
                   "hat keine Winkel." % (2 * ANGLE_LEG, ANGLE_LEG, H - T), 72):
        b += text(12, y, ln, 3.3)
        y += 4.4
    lens = {}
    for ln, c, _ in rows:
        lens[ln] = lens.get(ln, 0) + c
    for ln in wrap("Längen: " + ", ".join("%d × %.0f" % (c, l)
                                          for l, c in sorted(lens.items(), reverse=True))
                   + " mm", 72):
        b += text(12, y, ln, 3.3)
        y += 4.4
    b += text(12, y, "%d Winkel → %d Streifen à %.0f mm → %.2f Bogen A4 je Kasten"
              % (n_ang, n_strips, max(KKP_SHEET), sheets), 3.3)
    y += 9
    b += text(12, y, "Bedarf für %d Kästen (+%.0f %% Ausschuss)" % (N_BOXES, SCRAP * 100), 3.8,
              style="b")
    y += 5.2
    for ln in board_info:
        b += text(12, y, ln, 3.3)
        y += 4.4
    if y > Hp - 8:
        log("  WARNUNG: Zuschnittblatt läuft über (y = %.0f)" % y)
    # Skizze rechts
    x0, y0, ww, hh = 136, 30, Wp - 136 - 10, Hp - 30 - 14
    sc = min(ww / set_w, hh / set_h)
    b += nest_svg(set_faces, set_w, set_h, x0, y0, sc, False)
    b += text(x0, y0 + set_h * sc + 6, "Ein Satz, Maßstab 1 : %.1f" % (1 / sc), 3.2, style="i",
              fill="#555")
    p = os.path.join(OUT, "zuschnitt.svg")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(svg_doc(Wp, Hp, b))
    svgs_to_pdf([p], os.path.join(OUT, "zuschnitt.pdf"))


def bogen_svg(faces, n, boards):
    Wp, Hp = 297.0, 210.0
    sc = min((Wp - 24) / BOARD[0], (Hp - 44) / BOARD[1])
    b = text(12, 16, "Lernkasten A7 – Nest auf Wellpappbogen %.0f × %.0f mm" % BOARD, 6.5,
             style="b")
    b += text(12, 23, "%d Kästen pro Bogen · für %d Kästen (+%.0f %%) %d Bögen · Wellen "
              "senkrecht (parallel zur Seite %.0f mm), Teile nicht gedreht"
              % (n, N_BOXES, SCRAP * 100, boards, BOARD[1]), 3.6, style="i")
    b += nest_svg(faces, BOARD[0], BOARD[1], 12, 30, sc, True)
    p = os.path.join(OUT, "bogen.svg")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(svg_doc(Wp, Hp, b))
    svgs_to_pdf([p], os.path.join(OUT, "bogen.pdf"))


# ═════════════════════════════════════════════════════════════════════
#  Isometrische Darstellung (Maleralgorithmus über B-Rep-Flächen)
# ═════════════════════════════════════════════════════════════════════

VIEW = V(-0.45, -1.0, 0.75).normalize()          # zum Betrachter
RIGHT = V(0, 0, 1).cross(VIEW).normalize()
UP = VIEW.cross(RIGHT).normalize()
LIGHT = V(-0.35, -0.55, 1.0).normalize()


def _shade(n, base):
    k = 0.58 + 0.42 * max(0.0, n.dot(LIGHT))
    return "#%02x%02x%02x" % tuple(min(255, int(c * k)) for c in base)


def iso_polys(solids):
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
            loops = [[(p.dot(RIGHT), -p.dot(UP)) for p in w.discretize(Deflection=0.2)]
                     for w in f.Wires]
            polys.append((c.dot(VIEW), loops, _shade(n, base)))
        polys.sort(key=lambda t: t[0])
        cm = s.BoundBox.Center
        parts.append((cm.dot(VIEW), label, cm, polys, s.BoundBox))
    return [p[:4] for p in _paint_order(parts)]


def _in_front(a, b, eps=1e-6):
    """Achsparallele Quader: liegt a vor b (zum Betrachter hin)? None = unklar."""
    for lo, hi, d in (("XMin", "XMax", VIEW.x), ("YMin", "YMax", VIEW.y), ("ZMin", "ZMax", VIEW.z)):
        if getattr(a, hi) <= getattr(b, lo) + eps:      # a liegt auf der Minus-Seite von b
            return d < 0
        if getattr(b, hi) <= getattr(a, lo) + eps:
            return d > 0
    return None


def _paint_order(parts):
    """Topologische Sortierung nach Trennachse, Rückfall auf Tiefe der Mitte."""
    n = len(parts)
    after = [set() for _ in range(n)]   # after[i]: j wird nach i gemalt
    indeg = [0] * n
    for i in range(n):
        for j in range(i + 1, n):
            f = _in_front(parts[i][4], parts[j][4])
            if f is None:
                continue
            a, b = (j, i) if f else (i, j)   # hinteres zuerst
            if b not in after[a]:
                after[a].add(b)
                indeg[b] += 1
    out, ready = [], sorted(range(n), key=lambda k: parts[k][0])
    ready = [k for k in ready if indeg[k] == 0]
    done = set()
    while len(out) < n:
        if not ready:   # Zyklus: nach Tiefe auflösen
            ready = [min((k for k in range(n) if k not in done), key=lambda k: parts[k][0])]
        k = ready.pop(0)
        if k in done:
            continue
        done.add(k)
        out.append(parts[k])
        for m in after[k]:
            indeg[m] -= 1
            if indeg[m] == 0 and m not in done:
                ready.append(m)
        ready.sort(key=lambda q: parts[q][0])
    return out


def iso_svg(solids, x0, y0, w, h, labels=True, sw=0.18):
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
            out += ('<path d="%s" fill="%s" fill-rule="evenodd" stroke="%s" '
                    'stroke-width="%g" stroke-linejoin="round"/>\n' % (d, col, INK, sw))
    if labels:
        front = {}
        for depth, label, cm, _ in parts:
            if label and (label not in front or depth > front[label][0]):
                front[label] = (depth, cm)
        for label, (_, cm) in sorted(front.items()):
            px, py = ox + cm.dot(RIGHT) * sc, oy - cm.dot(UP) * sc
            r = 3.2 if len(label) == 1 else 3.8
            out += ('<circle cx="%.2f" cy="%.2f" r="%.1f" fill="#ffffff" stroke="%s" '
                    'stroke-width="0.4"/>\n' % (px, py, r, ACCENT))
            out += text(px, py + 1.3, label, 3.6, "middle", "b", ACCENT)
    return out


# ═════════════════════════════════════════════════════════════════════
#  Montageanleitung (Englisch / Kiswahili)
# ═════════════════════════════════════════════════════════════════════

TOOLS = [
    ("Sharp cutter knife, spare blades", "Kisu kikali (cutter) na vipande vya akiba"),
    ("Steel ruler, square, pencil, cutting board",
     "Rula ya chuma, pembemraba, penseli, ubao mnene wa kukatia"),
    ("Bone folder or blunt knife back for folding", "Kifaa cha kukunja au mgongo butu wa kisu"),
    ("Spray adhesive, newspaper to cover the table", "Gundi ya kunyunyiza, magazeti ya kufunika meza"),
    ("Corrugated cardboard, card paper 205 g (KKP)",
     "Kadibodi ya mawimbi ya kahawia, karatasi ya kadi 205 g"),
]


def steps():
    return [
        ("Cut all parts from the list. In every wall the flutes run up and down: from above you "
         "look into the open flutes. In the bottoms the flutes run along the long side. Cut with "
         "several light strokes along the steel ruler, keep the corners square.",
         "Kata vipande vyote vya orodha. Katika kila ukuta mawimbi yanaenda juu na chini: ukitazama "
         "kutoka juu unaona matundu ya mawimbi. Katika vitako mawimbi yanafuata upande mrefu. Kata "
         "kwa mipigo kadhaa myepesi kando ya rula ya chuma, pembe ziwe za mraba."),
        ("Cut KKP strips %.0f mm wide and fold each one lengthwise in the middle, so that it "
         "forms an angle with two legs of %.0f mm. Cut them to the lengths in the list."
         % (2 * ANGLE_LEG, ANGLE_LEG),
         "Kata vipande vya KKP vyenye upana wa mm %.0f na kunja kila kimoja katikati kwa urefu "
         "wake, kiwe pembe yenye pande mbili za mm %.0f. Vikate kwa urefu wa orodha."
         % (2 * ANGLE_LEG, ANGLE_LEG)),
        ("Build one inner box: put the two long walls L on the bottom B, the two end walls S "
         "stand between them. Glue the KKP angles on the outside: first the 4 bottom edges, "
         "then the 4 upright corners. Spray the angle, wait a moment, press it on firmly.",
         "Jenga sanduku moja la ndani: weka kuta mbili ndefu L juu ya kitako B, kuta mbili za "
         "mwisho S zinasimama katikati yake. Gundisha pembe za KKP kwa nje: kwanza kingo 4 za "
         "chini, kisha pembe 4 zilizosimama. Nyunyiza gundi kwenye pembe, subiri kidogo, kisha "
         "ibonyeze kwa nguvu."),
        ("Make all five inner boxes 1 to 5 this way. Each box must be square and a card must "
         "fit in easily. The number of the box is the number on L and B.",
         "Tengeneza masanduku yote matano ya ndani 1 hadi 5 kwa njia hii. Kila sanduku liwe la "
         "mraba na kadi iingie kwa urahisi. Namba ya sanduku ni namba iliyo kwenye L na B."),
        ("Glue the inner boxes together in a row, 1 to 5. Spray the end walls that touch, "
         "align bottoms and top edges and press.",
         "Gundisha masanduku ya ndani pamoja kwa mstari, 1 hadi 5. Nyunyiza gundi kwenye kuta "
         "za mwisho zinazogusana, linganisha vitako na kingo za juu, kisha bonyeza."),
        ("Outer box, no angles needed: glue the outer bottom U under the row, then the outer "
         "end walls E to both ends, then the outer long walls A over everything. Spray each "
         "part on the whole surface, align the top edges and press well.",
         "Sanduku la nje, halihitaji pembe: gundisha kitako cha nje U chini ya mstari, kisha kuta "
         "za mwisho za nje E pande zote mbili, kisha kuta ndefu za nje A juu ya vyote. Nyunyiza "
         "kila kipande eneo lote, linganisha kingo za juu na bonyeza vizuri."),
        ("Use spray adhesive only outdoors or with open windows, and cover the table with "
         "newspaper. Let the box dry for a few hours before use.",
         "Tumia gundi ya kunyunyiza nje tu au madirisha yakiwa wazi, na funika meza kwa magazeti. "
         "Acha sanduku likauke kwa saa chache kabla ya kulitumia."),
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


def write_steps(b, items, first, y):
    for i, (en, sw) in enumerate(items):
        b += ('<circle cx="19" cy="%.2f" r="3.4" fill="%s"/>\n' % (y - 1.3, ACCENT))
        b += text(19, y, str(first + i), 4, "middle", "b", "#fff")
        for ln in wrap(en, 98):
            b += text(26, y, ln, 3.6)
            y += 4.6
        for ln in wrap(sw, 98):
            b += text(26, y, ln, 3.6, style="i", fill="#3d3d3d")
            y += 4.6
        y += 3.6
    return b, y


def montage(prof, asm, kkp):
    col = {"A": CARD_OUT, "E": CARD_OUT, "U": CARD_OUT, "S": CARD_ALT}
    color = lambda k: col.get(k, CARD)
    label = lambda k: k[0] if k[0] in "LB" else k
    st = steps()
    pages = []

    # Seite 1: fertiger Kasten, Teileliste, Werkzeug
    full = [(None, s, color(k)) for n, k, s in asm]
    b = text(15, 22, "Learning card box A7 – assembly instructions", 7, style="b")
    b += text(15, 30, "Sanduku la kadi za kujifunzia A7 – maelekezo ya kuunganisha", 5.2, style="i")
    b += text(15, 37, "Leitner box, 5 compartments · corrugated cardboard %.1f mm · outside "
              "%.0f × %.0f × %.0f mm" % (T, L, W, H), 3.6, fill="#444")
    b += iso_svg(full, 15, 42, 180, 62, labels=False)
    y = 114
    b += text(15, y, "Parts per box · Vipande kwa kila sanduku", 4.6, style="b")
    y += 6
    b += text(24, y, "part · kipande", 3.0, fill="#555")
    b += text(128, y, "pcs", 3.0, "end", fill="#555")
    b += text(160, y, "across flutes", 3.0, "end", fill="#555")
    b += text(194, y, "along flutes", 3.0, "end", fill="#555")
    y += 3.5
    b += text(128, y, "idadi", 3.0, "end", "i", "#555")
    b += text(160, y, "kuvuka mawimbi", 3.0, "end", "i", "#555")
    b += text(194, y, "kufuata mawimbi", 3.0, "end", "i", "#555")
    y += 6
    for k, (face, cnt, de, en, sw) in prof.items():
        bb = face.BoundBox
        b += text(17, y, k, 3.5, style="b", fill=ACCENT)
        b += text(26, y, en, 3.5)
        b += text(74, y, sw, 3.5, style="i", fill="#3d3d3d")
        b += text(128, y, "%d" % cnt, 3.5, "end")
        b += text(160, y, "%.0f mm" % bb.XLength, 3.5, "end")
        b += text(194, y, "%.0f mm" % bb.YLength, 3.5, "end")
        y += 5.0
    rows, n_ang, n_strips, per_sheet, sheets = kkp
    y += 2
    b += text(17, y, "K", 3.5, style="b", fill=ACCENT)
    b += text(26, y, "KKP angles, strip %.0f mm wide · pembe za KKP, upana mm %.0f"
              % (2 * ANGLE_LEG, 2 * ANGLE_LEG), 3.5)
    y += 5.0
    for i, lb in enumerate(LBOX):
        b += text(26, y, "box · sanduku %d:  4 × %.0f,  2 × %.0f,  2 × %.0f mm"
                  % (i + 1, H - T, lb, WB), 3.4, fill="#333")
        y += 4.6
    y += 5
    b += text(15, y, "Tools and material · Vifaa", 4.6, style="b")
    y += 6.5
    for en, sw in TOOLS:
        b += text(15, y, "· " + en, 3.4)
        b += text(100, y, sw, 3.4, style="i", fill="#3d3d3d")
        y += 4.8
    if y > 282:
        log("  WARNUNG: Montageseite 1 läuft über (y = %.0f)" % y)
    b += text(15, 290, "NgarumaVTC · Lernkasten A7, Wellpappe", 3.0, fill="#666")
    pages.append(b)

    # Seite 2: Innenkasten
    x0, lb = BOX_X[2], LBOX[2]
    own = [(n, k, s) for n, k, s in asm if n.startswith("Kasten3_")]
    expl = {"Boden": V(0, 0, -30), "Seite_vorn": V(0, -40, 0), "Seite_hinten": V(0, 40, 0),
            "Stirn_a": V(-35, 0, 0), "Stirn_b": V(35, 0, 0)}
    ex = []
    for n, k, s in own:
        s2 = s.copy()
        s2.translate(expl[n.split("_", 1)[1]])
        ex.append((label(k), s2, color(k)))
    withang = [(None, s, color(k)) for n, k, s in own]
    withang += [(None, s, PAPER) for s in angle_solids(x0, lb)]
    row = []
    for i in range(5):
        for n, k, s in asm:
            if n.startswith("Kasten%d_" % (i + 1)):
                s2 = s.copy()
                s2.translate(V(i * 18, 0, 0))
                row.append((None, s2, color(k)))
    b = text(15, 18, "Steps · Hatua", 6, style="b")
    b += iso_svg(ex, 15, 24, 58, 50)
    b += iso_svg(withang, 78, 24, 52, 50, labels=False)
    b += iso_svg(row, 135, 24, 62, 50, labels=False)
    b += text(44, 80, "parts of one inner box", 3.0, "middle", "i", "#555")
    b += text(104, 80, "KKP angles outside", 3.0, "middle", "i", "#555")
    b += text(166, 80, "five boxes in a row", 3.0, "middle", "i", "#555")
    b += text(44, 84, "vipande vya sanduku moja", 3.0, "middle", "i", "#555")
    b += text(104, 84, "pembe za KKP kwa nje", 3.0, "middle", "i", "#555")
    b += text(166, 84, "masanduku matano kwa mstari", 3.0, "middle", "i", "#555")
    b, y = write_steps(b, st[:5], 1, 96)
    if y > 282:
        log("  WARNUNG: Montageseite 2 läuft über (y = %.0f)" % y)
    pages.append(b)

    # Seite 3: Außenkasten
    expl = {"Aussen_Boden": V(0, 0, -40), "Aussen_Stirn_Fach1": V(-60, 0, 0),
            "Aussen_Stirn_Fach5": V(60, 0, 0), "Aussen_Seite_vorn": V(0, -70, 0),
            "Aussen_Seite_hinten": V(0, 70, 0)}
    ex = []
    for n, k, s in asm:
        s2 = s.copy()
        if n in expl:
            s2.translate(expl[n])
            ex.append((k, s2, color(k)))
        else:
            ex.append((None, s2, color(k)))
    b = iso_svg(ex, 15, 14, 180, 90)
    b += text(105, 110, "outer box: no angles, glue on the whole surface · "
              "sanduku la nje: bila pembe, gundi eneo lote", 3.0, "middle", "i", "#555")
    b, y = write_steps(b, st[5:], 6, 124)
    b += text(15, 287, "Kiswahili text: please have it checked locally · Tafadhali kagueni "
              "maandishi ya Kiswahili.", 3.0, fill="#666")
    if y > 282:
        log("  WARNUNG: Montageseite 3 läuft über (y = %.0f)" % y)
    pages.append(b)

    svgs = []
    for i, b in enumerate(pages):
        p = os.path.join(OUT, "montage-%d.svg" % (i + 1))
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(svg_doc(210, 297, b))
        svgs.append(p)
    svgs_to_pdf(svgs, os.path.join(OUT, "montage.pdf"))


# ═════════════════════════════════════════════════════════════════════
#  FreeCAD-Dokument, Exporte
# ═════════════════════════════════════════════════════════════════════

def build_document(asm):
    doc = App.newDocument("Lernkasten_Karton")
    sp = doc.addObject("Spreadsheet::Sheet", "Parameter")
    rows = [("t", T, "Kartonstärke"), ("L", L, "Außenlänge"), ("W", W, "Außenbreite"),
            ("H", H, "Außenhöhe"), ("WI", WI, "lichte Breite"), ("HI", HI, "lichte Höhe"),
            ("angle_leg", ANGLE_LEG, "KKP-Winkel Schenkel")]
    sp.set("A1", "Name"), sp.set("B1", "Wert [mm]"), sp.set("C1", "Bedeutung")
    for i, (n, v, d) in enumerate(rows):
        sp.set("A%d" % (i + 2), n)
        sp.set("B%d" % (i + 2), "%g" % v)
        sp.set("C%d" % (i + 2), d)
    for i, a in enumerate(FACH):
        sp.set("A%d" % (len(rows) + 2 + i), "Fach%d" % (i + 1))
        sp.set("B%d" % (len(rows) + 2 + i), "%g" % a)
        sp.set("C%d" % (len(rows) + 2 + i), "lichte Länge")
    groups = {}
    objs = []
    for n, k, s in asm:
        g = n.split("_")[0]
        if g not in groups:
            groups[g] = doc.addObject("App::DocumentObjectGroup", g)
        o = doc.addObject("Part::Feature", n)
        o.Shape = s
        groups[g].addObject(o)
        objs.append(o)
    doc.recompute()
    doc.saveAs(os.path.join(OUT, "lernkasten.FCStd"))
    try:
        import Import
        Import.export(objs, os.path.join(OUT, "lernkasten.step"))
    except Exception:   # noqa
        Part.makeCompound([s for _, _, s in asm]).exportStep(os.path.join(OUT, "lernkasten.step"))


def main():
    os.makedirs(os.path.join(OUT, "dxf"), exist_ok=True)
    log("Lernkasten A7 Karton: %.1f × %.1f × %.1f mm, t = %.2f, Fächer %s"
        % (L, W, H, T, " / ".join("%g" % f for f in FACH)))
    prof, asm = build_parts()
    check_assembly(asm)

    log("— DXF Einzelteile —")
    for k, (face, cnt, de, en, sw) in prof.items():
        name = de.lower().replace(" ", "_").replace("ä", "ae").replace("ß", "ss")
        write_dxf_faces(os.path.join(OUT, "dxf", "%s_%s.dxf" % (k, name)),
                        [(k, moved(face, 0, 0))], labels=False)

    log("— KKP-Winkel —")
    kkp = kkp_strips()
    rows, n_ang, n_strips, per_sheet, sheets = kkp
    log("  %d Winkel je Kasten → %d Streifen %.0f × %.0f → %.2f Bogen A4 (%d Streifen/Bogen)"
        % (n_ang, n_strips, 2 * ANGLE_LEG, max(KKP_SHEET), sheets, per_sheet))

    log("— Bogennest %.0f × %.0f —" % BOARD)
    uw, uh = BOARD[0] - 2 * BOARD_MARGIN, BOARD[1] - 2 * BOARD_MARGIN
    n, lay = max_sets(prof, uw, uh)
    if n < 1:
        raise RuntimeError("Kein Satz passt auf den Bogen")
    board_faces = placed_faces(prof, lay, BOARD_MARGIN, BOARD_MARGIN)
    check_nest(board_faces, BOARD_MARGIN, BOARD_MARGIN, BOARD[0] - BOARD_MARGIN,
               BOARD[1] - BOARD_MARGIN, "Bogen")
    write_dxf_faces(os.path.join(OUT, "bogen.dxf"), board_faces, frame=BOARD)
    need = int(math.ceil(N_BOXES * (1 + SCRAP)))
    boards = int(math.ceil(need / float(n)))
    used = sum(f.Area for _, f in board_faces) / (BOARD[0] * BOARD[1])
    glue = (len(FACH) - 1) * WB * (H - T)                          # Kontaktflächen Block
    glue += LB * WB + 2 * WB * H + 2 * L * H                       # Außenkasten
    log("  %d Kästen pro Bogen (Ausnutzung %.0f %%)" % (n, used * 100))
    log("  %d Kästen + %.0f %% = %d → %d Bögen %.0f × %.0f mm"
        % (N_BOXES, SCRAP * 100, need, boards, BOARD[0], BOARD[1]))
    log("  Sprühklebefläche je Kasten ca. %.3f m² (ohne Winkel)" % (glue / 1e6))
    bogen_svg(board_faces, n, boards)

    log("— Zuschnitt ein Satz —")
    sw_, sh_ = 560.0, 520.0
    lay1 = nest(prof, 1, sw_, sh_)
    if lay1 is None:
        raise RuntimeError("Satz passt nicht auf %g × %g" % (sw_, sh_))
    set_faces = placed_faces(prof, lay1, 0, 0)
    check_nest(set_faces, 0, 0, sw_, sh_, "Satz")
    bb = Part.makeCompound([f for _, f in set_faces]).BoundBox
    write_dxf_faces(os.path.join(OUT, "zuschnitt.dxf"), set_faces)
    board_info = [
        "Wellpappe: %d Bögen %.0f × %.0f mm (%d Kästen je Bogen, Ausnutzung %.0f %%)"
        % (boards, BOARD[0], BOARD[1], n, used * 100),
        "KKP 205 g: %d Bogen A4" % int(math.ceil(need * sheets)),
        "Sprühkleber: Klebefläche ca. %.2f m² je Kasten, %.0f m² gesamt"
        % (glue / 1e6, need * glue / 1e6),
    ]
    zuschnitt(prof, set_faces, bb.XMax, bb.YMax, kkp, board_info)

    log("— Montageanleitung —")
    montage(prof, asm, kkp)

    log("— FreeCAD-Dokument / STEP —")
    build_document(asm)
    log("Fertig: " + OUT)


if not os.environ.get("LERNKASTEN_NOMAIN"):
    main()
