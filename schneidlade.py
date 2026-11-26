# -*- coding: utf-8 -*-
"""
Schneidlade für den Lernkasten aus Wellpappe
============================================

Holzvorrichtung mit Cutterklinge, gebaut von den Tischlerlehrlingen in Ngaruma.
Sie schneidet alle Kartonteile ohne Messen: Karton gegen den Anschlag schieben,
Schiene ablassen, Schlitten durchziehen.

Aufruf (headless):   freecadcmd schneidlade.py

Aufbau (x = Schnittrichtung, y = vom Bediener weg, z = oben; Schnittlinie y = 0):
  - Grundplatte mit Opferleiste unter der Schnittlinie
  - Schiene, links in einem Lagerbock drehbar, rechts in einer Fanggabel geführt
  - Schlitten auf der Schiene, Abbrechklinge 18 mm unter 45° an der hinteren Wange
  - Seitenanschlag links (rechtwinklig zur Schnittlinie)
  - Anschlagleiste hinter der Schnittlinie, gehalten von 2 Steckstiften;
    für jedes Maß gibt es ein eigenes Lochpaar in der Grundplatte

Die Maße der Kartonteile kommen aus lernkasten.py (gleiche Parameter, z. B. LERNKASTEN_T).

Erzeugt in ./build/schneidlade/:
  schneidlade.FCStd / .step   Modell
  bauplan.pdf                 Holzliste, Draufsicht mit Lochplan, Schnitt Schlitten 1:1,
                              Bau, Bedienung, Schneidplan je Bogen
"""

import math
import os
import sys

try:
    _HERE = os.path.dirname(os.path.abspath(__file__))
except NameError:
    _HERE = os.getcwd()
sys.path.insert(0, _HERE)
os.environ["LERNKASTEN_NOMAIN"] = "1"
import lernkasten as lk   # noqa: E402

import FreeCAD as App     # noqa: E402
import Part               # noqa: E402

V = App.Vector
log = lk.log
text, text_runs, wrap = lk.text, lk.text_runs, lk.wrap
DE_INK, INK_T, ACCENT = lk.DE_INK, lk.INK_T, lk.ACCENT

# ═════════════════════════════════════════════════════════════════════
#  PARAMETER  (mm)
# ═════════════════════════════════════════════════════════════════════

T = lk.T                    # Kartonstärke
TRIM = 5.0                  # Randschnitt am Wellpappbogen je Kante

CUT_MAX = 1220.0            # längster Schnitt (≥ längste Bogenseite)
BASE_T = 18.0               # Grundplatte Sperrholz
BASE_X0 = -230.0            # Grundplatte links
BASE_Y = (-130.0, 500.0)    # Grundplatte in y

GROOVE_W, GROOVE_D = 30.0, 6.0     # Nut für die Opferleiste
GROOVE_X0 = -160.0

RAIL_W, RAIL_H = 60.0, 45.0        # Schiene Hartholz
RAIL_X0 = -220.0
PIVOT_X = -200.0                   # Drehbolzen M10
CHEEK = 12.0                       # Wange des Schlittens zwischen Schiene und Klinge
PLAY = 0.3                         # Spiel Schlitten / Schiene
BLADE_T = 0.5                      # Abbrechklinge 18 mm
BLADE_W, BLADE_L = 18.0, 100.0
BLADE_ANGLE = 45.0
BLADE_DEPTH = 1.5                  # so weit taucht die Klinge in die Opferleiste
RAIL_Y1 = -(BLADE_T / 2 + CHEEK + PLAY)   # hintere Schienenfläche
RAIL_Y0 = RAIL_Y1 - RAIL_W

CAR_L = 110.0                      # Schlitten Länge in x
BLADE_X = 20.0                     # Klingenspitze ab hinterem (linkem) Ende des Schlittens
CAR_TOP = 15.0                     # Deckplatte
CLAMP_T = 10.0                     # Klemmplatte
CLEAR = 2.0                        # Wangen / Klemmplatte schweben über dem Karton
CAR_PARK_X = -165.0                # Parkstellung (linkes Ende des Schlittens)

PIVOT_BLOCK = (60.0, 20.0, 60.0)   # Lagerwange x, y, z (2 Stück)
FORK = (40.0, 40.0, 60.0)          # Fanggabel x, y, z (2 Stück)
# Die Klinge schneidet mit der hinten liegenden Spitze: der Schlitten muss um CAR_L − BLADE_X
# über das Schnittende hinaus fahren können, bevor er an die Fanggabel stößt.
FORK_X = CUT_MAX + CAR_L - BLADE_X + 2.0
GROOVE_X = (GROOVE_X0, FORK_X - 5.0)
RAIL_X = (RAIL_X0, FORK_X + FORK[0] + 110.0)
BASE_X = (BASE_X0, RAIL_X[1] + 10.0)

STOP_W, STOP_H = 30.0, 25.0        # Seitenanschlag
STOP_Y0 = 15.0                     # beginnt hinter der Opferleiste
FENCE_W, FENCE_H = 40.0, 30.0      # Anschlagleiste
FENCE_L = 1200.0
PEG_D, PEG_L = 12.0, 45.0          # Steckstifte Buche
HOLE_PITCH = 34.0                  # Versatz der Lochpaare in x
HOLE_X0 = 60.0                     # erstes Loch links, erstes Loch rechts = FENCE_L - HOLE_X0

OUT = os.path.join(lk.OUT, "schneidlade")

WOOD = (0xd9, 0xb3, 0x82)
WOOD_D = (0xb0, 0x7d, 0x48)
PLY = (0xe8, 0xcf, 0xa4)
SOFT = (0xf0, 0xe2, 0xbf)
STEEL = (0xa8, 0xb0, 0xb8)
CARDB = lk.CARD


def box(x0, y0, z0, dx, dy, dz):
    return Part.makeBox(dx, dy, dz, V(x0, y0, z0))


# ═════════════════════════════════════════════════════════════════════
#  Maße der Kartonteile → Anschlagmaße und Schneidplan
# ═════════════════════════════════════════════════════════════════════

def pieces_per_box():
    """Wandteile: (Streifenbreite = Maß längs Welle, Länge = quer), Bodenteile umgekehrt."""
    walls, bottoms = [], []
    for k, (u, v, cnt, de, en, sw) in lk.part_table().items():
        if k == "U" or k.startswith("B"):
            bottoms += [(u, v, k)] * cnt      # Streifen WB breit, quer zur Welle; Länge längs
        else:
            walls += [(v, u, k)] * cnt        # Streifen H/HI breit längs Welle; Länge quer
    return walls, bottoms


def measures():
    """Alle Anschlagmaße: {maß: [teile/verwendung]}."""
    walls, bottoms = pieces_per_box()
    m = {}
    for w, ln, k in walls + bottoms:
        m.setdefault(round(w, 2), set()).add("strip")
        m.setdefault(round(ln, 2), set()).add(k)
    return {d: sorted(v, key=lambda s: (s != "strip", s)) for d, v in sorted(m.items())}


def ffd(items, cap):
    """First-Fit-Decreasing, items [(länge, key)] → Behälter [[(länge, key)]]."""
    bins = []
    for it in sorted(items, key=lambda t: -t[0]):
        for b in bins:
            if sum(x for x, _ in b) + it[0] <= cap + 1e-6:
                b.append(it)
                break
        else:
            if it[0] > cap + 1e-6:
                return None
            bins.append([it])
    return bins


def board_plan(n):
    """Guillotine-Plan für n Kästen auf einem Bogen BOARD (u quer, v längs Welle).
    Erst Bodenstreifen (Breite WB in u, Länge v), dann aus dem Rest Wandstreifen
    (Breite in v, Länge = restliches u). Rückgabe dict oder None."""
    bu, bv = lk.BOARD
    U, Vv = bu - 2 * TRIM, bv - 2 * TRIM
    walls, bottoms = pieces_per_box()
    wb = bottoms[0][0]
    bstrips = ffd([(ln, k) for _, ln, k in bottoms] * n, Vv)
    if bstrips is None:
        return None
    ru = U - len(bstrips) * wb
    if ru <= 0:
        return None
    groups = {}
    for w, ln, k in walls * n:
        groups.setdefault(round(w, 2), []).append((ln, k))
    wstrips = []
    for w in sorted(groups, reverse=True):
        bins = ffd(groups[w], ru)
        if bins is None:
            return None
        wstrips += [(w, b) for b in bins]
    used_v = sum(w for w, _ in wstrips)
    if used_v > Vv + 1e-6:
        return None
    return dict(n=n, wb=wb, bstrips=bstrips, ru=ru, wstrips=wstrips, used_v=used_v, U=U, Vv=Vv)


def best_plan():
    best = None
    for n in range(1, 30):
        p = board_plan(n)
        if p is None:
            break
        best = p
    if best is None:
        raise RuntimeError("Kein Kasten passt im Streifenplan auf den Bogen %s" % (lk.BOARD,))
    return best


# ═════════════════════════════════════════════════════════════════════
#  Modell
# ═════════════════════════════════════════════════════════════════════

def hole_positions():
    """{maß: (y_loch, [x_links, x_rechts])} – y = Lochmitte ab Schnittlinie."""
    out = {}
    for i, d in enumerate(measures()):
        y = d + FENCE_W + PEG_D / 2
        out[d] = (y, [HOLE_X0 + i * HOLE_PITCH, FENCE_L - HOLE_X0 - i * HOLE_PITCH])
    return out


def blade_solid(x_tip):
    """Klinge als dünne Platte unter BLADE_ANGLE, Spitze unten hinten bei x_tip, z = −BLADE_DEPTH.
    Wie ein gezogenes Cuttermesser: die Klinge steigt in Zugrichtung (+x) an, die Schneide
    (untere Längskante) zeigt nach vorn unten, die Spitze läuft hinten nach."""
    b = Part.makeBox(BLADE_L, BLADE_T, BLADE_W)
    # Schneide = Kante z = 0, Spitze bei (0, 0, 0) → um y drehen, so dass +x ansteigt
    b.rotate(V(0, 0, 0), V(0, 1, 0), -BLADE_ANGLE)
    tip = min(b.Vertexes, key=lambda v: (v.Z, -v.X)).Point
    b.translate(V(x_tip - tip.x, -BLADE_T / 2 - tip.y, -BLADE_DEPTH - tip.z))
    return b


def blade_marks(x_tip):
    """Seitenansicht (x, z): Lage der 2 Schrauben M6 und der 2 Anschlagstifte am Klingenrücken."""
    a = math.radians(BLADE_ANGLE)
    e = (math.cos(a), math.sin(a))          # entlang der Schneide nach vorn oben
    nrm = (-math.sin(a), math.cos(a))       # zur Rückenkante
    tip = (x_tip, -BLADE_DEPTH)
    P = lambda t, o: (tip[0] + e[0] * t + nrm[0] * o, tip[1] + e[1] * t + nrm[1] * o)  # noqa: E731
    bolts = [P(58, -8.0), P(40, BLADE_W + 8.0)]
    pins = [P(12, BLADE_W + 1.5), P(66, BLADE_W + 1.5)]
    return bolts, pins


def holder_top(zr):
    """Oberkante Klingenwange und Klemmplatte: 8 mm über der Klinge."""
    bb = blade_solid(0).BoundBox
    return math.ceil(bb.ZMax + 8.0)


def build(cardboard=True, car_x=CAR_PARK_X):
    """Rückgabe [(name, key, solid, farbe)]; Schiene abgesenkt auf Karton der Stärke T."""
    zr = T if cardboard else 0.0          # Unterkante Schiene
    parts = []
    holes = hole_positions()
    base = box(BASE_X[0], BASE_Y[0], -BASE_T, BASE_X[1] - BASE_X[0], BASE_Y[1] - BASE_Y[0], BASE_T)
    base = base.cut(box(GROOVE_X[0], -GROOVE_W / 2, -GROOVE_D, GROOVE_X[1] - GROOVE_X[0],
                        GROOVE_W, GROOVE_D))
    for d, (y, xs) in holes.items():
        for x in xs:
            base = base.cut(Part.makeCylinder(PEG_D / 2, BASE_T + 2, V(x, y, -BASE_T - 1)))
    parts.append(("Grundplatte", "G", base, PLY))
    parts.append(("Opferleiste", "O", box(GROOVE_X[0], -GROOVE_W / 2, -GROOVE_D,
                                          GROOVE_X[1] - GROOVE_X[0], GROOVE_W, GROOVE_D), SOFT))
    rail = box(RAIL_X[0], RAIL_Y0, zr, RAIL_X[1] - RAIL_X[0], RAIL_W, RAIL_H)
    slot = Part.makeCylinder(5.0, RAIL_W + 2, V(PIVOT_X, RAIL_Y0 - 1, zr + RAIL_H / 2 - 3), V(0, 1, 0))
    slot = slot.fuse(Part.makeCylinder(5.0, RAIL_W + 2, V(PIVOT_X, RAIL_Y0 - 1, zr + RAIL_H / 2 + 3),
                                       V(0, 1, 0)))
    slot = slot.fuse(box(PIVOT_X - 5, RAIL_Y0 - 1, zr + RAIL_H / 2 - 3, 10, RAIL_W + 2, 6))
    rail = rail.cut(slot)
    parts.append(("Schiene", "R", rail, WOOD_D))
    # Drehbolzen auf fester Höhe: Mitte Langloch bei Karton T/2 → Bolzenachse fest
    zb = T / 2 + RAIL_H / 2
    bolt = Part.makeCylinder(5.0, RAIL_W + 2 * PIVOT_BLOCK[1] + 16,
                             V(PIVOT_X, RAIL_Y0 - PIVOT_BLOCK[1] - 8, zb), V(0, 1, 0))
    pbx = PIVOT_X - PIVOT_BLOCK[0] / 2
    for nm, y0 in (("Lagerwange vorn", RAIL_Y0 - PIVOT_BLOCK[1]), ("Lagerwange hinten", RAIL_Y1)):
        w = box(pbx, y0, 0, PIVOT_BLOCK[0], PIVOT_BLOCK[1], PIVOT_BLOCK[2])
        w = w.cut(Part.makeCylinder(5.2, PIVOT_BLOCK[1] + 2, V(PIVOT_X, y0 - 1, zb), V(0, 1, 0)))
        parts.append((nm, "P", w, WOOD))
    # Bolzen: im Langloch der Schiene; für die Kollisionsprüfung nur die Teile außerhalb der Schiene
    parts.append(("Bolzen M10", "M10", bolt.cut(box(RAIL_X[0], RAIL_Y0, -50, 400, RAIL_W, 200)),
                  STEEL))
    for nm, y0 in (("Fanggabel vorn", RAIL_Y0 - FORK[1]), ("Fanggabel hinten", RAIL_Y1)):
        parts.append((nm, "F", box(FORK_X, y0, 0, FORK[0], FORK[1], FORK[2]), WOOD))
    parts.append(("Griff", "H", box(RAIL_X[1] - 100, RAIL_Y0 + 10, zr + RAIL_H, 90, RAIL_W - 20, 30),
                  WOOD))
    # Schlitten
    cz0 = zr + CLEAR                       # Unterkante Wangen
    ztop = zr + RAIL_H
    x0 = car_x
    hz = holder_top(zr)
    parts.append(("Schlitten Deckplatte", "W1",
                  box(x0, RAIL_Y0 - PLAY - CHEEK, ztop + PLAY, CAR_L, RAIL_W + 2 * PLAY + CHEEK,
                      CAR_TOP), WOOD))
    parts.append(("Schlitten Wange vorn", "W2",
                  box(x0, RAIL_Y0 - PLAY - CHEEK, cz0, CAR_L, CHEEK, ztop + PLAY - cz0), WOOD))
    parts.append(("Klingenwange", "W5",
                  box(x0, RAIL_Y1 + PLAY, cz0, CAR_L, CHEEK, hz - cz0), WOOD))
    parts.append(("Klemmplatte", "W3",
                  box(x0, BLADE_T / 2, cz0, CAR_L, CLAMP_T, hz - cz0), WOOD))
    parts.append(("Knauf", "W4", Part.makeCylinder(15, 35, V(x0 + CAR_L / 2, (RAIL_Y0 + RAIL_Y1) / 2,
                                                              ztop + PLAY + CAR_TOP)), WOOD_D))
    parts.append(("Klinge", "K", blade_solid(x0 + BLADE_X), STEEL))
    # Seitenanschlag, Anschlagleiste, Stifte (Stellung: Maß 117)
    parts.append(("Seitenanschlag", "S", box(-STOP_W, STOP_Y0, 0, STOP_W, BASE_Y[1] - STOP_Y0 - 5,
                                             STOP_H), WOOD))
    d0 = lk.WB
    y, xs = holes[round(d0, 2)]
    parts.append(("Anschlagleiste", "A", box(0, d0, 0, FENCE_L, FENCE_W, FENCE_H), WOOD_D))
    for i, x in enumerate(xs):
        parts.append(("Stift %d" % (i + 1), "D",
                      Part.makeCylinder(PEG_D / 2 - 0.1, PEG_L, V(x, y, -BASE_T)), (0xc9, 0x9a, 0x5e)))
    if cardboard:
        parts.append(("Karton (Beispiel)", "C",
                      box(0, -400, 0, 800, 400 + d0, T), CARDB))
    return parts


def check(parts):
    log("— Prüfung Schneidlade —")
    ok = True
    allowed = {("Klinge", "Opferleiste"), ("Klinge", "Karton (Beispiel)")}
    for i in range(len(parts)):
        for j in range(i + 1, len(parts)):
            a, b = parts[i], parts[j]
            v = a[2].common(b[2]).Volume
            if v > 1e-4 and (a[0], b[0]) not in allowed and (b[0], a[0]) not in allowed:
                log("  KOLLISION %s / %s: %.3f mm³" % (a[0], b[0], v))
                ok = False
    by = {p[0]: p[2] for p in parts}
    bl = by["Klinge"].BoundBox
    log("  Klinge: Ebene y = %.2f … %.2f, Spitze z = %.2f (Karton 0 … %.1f)"
        % (bl.YMin, bl.YMax, bl.ZMin, T))
    if not (bl.YMin < 0 < bl.YMax and bl.ZMin < -0.5 and bl.ZMin > -GROOVE_D):
        log("  Klinge schneidet nicht durch oder zu tief")
        ok = False
    # Klinge darf nur die Opferleiste treffen, nicht die Grundplatte
    tips = (CAR_PARK_X + BLADE_X, FORK_X - CAR_L + BLADE_X)       # Parkstellung, Anschlag Gabel
    for x_tip in tips:
        bs = blade_solid(x_tip)
        if bs.common(by["Grundplatte"]).Volume > 1e-6:
            log("  Klinge trifft bei x = %.0f die Grundplatte" % x_tip)
            ok = False
    log("  Klingenweg x = %.0f … %.0f (Schnitt 0 … %.0f)" % (tips[0], tips[1], CUT_MAX))
    if tips[0] > -10 or tips[1] < CUT_MAX:
        log("  Klingenweg zu kurz")
        ok = False
    if CAR_PARK_X < PIVOT_X + PIVOT_BLOCK[0] / 2:
        log("  Parkstellung kollidiert mit dem Lagerbock")
        ok = False
    # Klinge liegt vollständig zwischen Klingenwange und Klemmplatte, Schrauben/Stifte im Holz
    ka = build(True, 300.0)
    kb = {p[0]: p[2] for p in ka}
    blb, w5b = kb["Klinge"].BoundBox, kb["Klingenwange"].BoundBox
    if blb.XMin < w5b.XMin or blb.XMax > w5b.XMax or blb.ZMax > w5b.ZMax:
        log("  Klinge ragt aus dem Halter")
        ok = False
    bolts, pins = blade_marks(BLADE_X)
    for x, z in bolts + pins:
        if not (6 <= x <= CAR_L - 6 and T + CLEAR + 6 <= z <= holder_top(T) - 6):
            log("  Schraube/Stift (%.0f | %.0f) zu nah am Rand des Halters" % (x, z))
            ok = False
    # Klemmplatte und Wangen über dem Karton
    for nm in ("Klemmplatte", "Schlitten Wange vorn", "Klingenwange"):
        if by[nm].BoundBox.ZMin < T + 0.5:
            log("  %s schleift auf dem Karton" % nm)
            ok = False
    # Lochabstand
    hp = [(x, y) for y, xs in hole_positions().values() for x in xs]
    dmin = min(math.hypot(a[0] - b[0], a[1] - b[1]) for i, a in enumerate(hp) for b in hp[i + 1:])
    log("  %d Lochpaare, kleinster Lochabstand %.1f mm (Ø %.0f)" % (len(hp) // 2, dmin, PEG_D))
    if dmin < PEG_D + 8:
        ok = False
    ymax = max(y for y, _ in hole_positions().values())
    if ymax + PEG_D / 2 + 10 > BASE_Y[1]:
        log("  hinterstes Loch zu nah am Rand")
        ok = False
    # Spalt unter der angehobenen Schiene am Seitenanschlag
    lift = math.radians(15)
    gap = (0 - PIVOT_X) * math.tan(lift)
    log("  Schiene 15° angehoben: Spalt bei x = 0: %.0f mm, bei x = %.0f: %.0f mm"
        % (gap, CUT_MAX, (CUT_MAX - PIVOT_X) * math.tan(lift)))
    bu, bv = lk.BOARD
    plan = best_plan()
    longest = max(bv, plan["ru"])
    log("  längster Schnitt im Schneidplan %.0f mm (möglich %.0f)" % (longest, CUT_MAX))
    if longest > CUT_MAX:
        ok = False
    log("  Schneidlade: %s" % ("OK" if ok else "FEHLER"))
    if not ok:
        raise RuntimeError("Schneidlade fehlerhaft")


# ═════════════════════════════════════════════════════════════════════
#  Holzliste
# ═════════════════════════════════════════════════════════════════════

def wood_list():
    """(key, stück, l, b, d, material de/en, bezeichnung en, sw, de)"""
    zr = T
    cz0 = zr + CLEAR
    cheek_h = RAIL_H + PLAY - CLEAR
    holder_h = holder_top(T) - cz0
    top_w = RAIL_W + 2 * PLAY + CHEEK
    return [
        ("G", 1, BASE_X[1] - BASE_X[0], BASE_Y[1] - BASE_Y[0], BASE_T, "plywood",
         "Base board", "Ubao wa chini", "Grundplatte"),
        ("O", 4, GROOVE_X[1] - GROOVE_X[0], GROOVE_W, GROOVE_D, "softwood / MDF",
         "Sacrificial strip (3 spare)", "Kipande cha kukatia (3 za akiba)",
         "Opferleiste (3 Ersatz)"),
        ("R", 1, RAIL_X[1] - RAIL_X[0], RAIL_W, RAIL_H, "hardwood, straight",
         "Rail", "Reli", "Schiene"),
        ("P", 2, PIVOT_BLOCK[0], PIVOT_BLOCK[2], PIVOT_BLOCK[1], "hardwood",
         "Pivot cheek", "Kishikio cha egemeo", "Lagerwange"),
        ("F", 2, FORK[0], FORK[2], FORK[1], "hardwood", "Fork block", "Kizuizi cha uma",
         "Fanggabel"),
        ("H", 1, 90, 30, RAIL_W - 20, "hardwood", "Handle", "Mshiko", "Griff"),
        ("W1", 1, CAR_L, top_w, CAR_TOP, "hardwood", "Carriage top", "Juu ya gari",
         "Schlitten Deckplatte"),
        ("W2", 1, CAR_L, cheek_h, CHEEK, "hardwood", "Front cheek", "Ubavu wa mbele",
         "Wange vorn"),
        ("W5", 1, CAR_L, holder_h, CHEEK, "hardwood", "Blade cheek", "Ubavu wa kiwembe",
         "Klingenwange"),
        ("W3", 1, CAR_L, holder_h, CLAMP_T, "hardwood", "Clamp plate", "Bamba la kubana",
         "Klemmplatte"),
        ("W4", 1, 35, 30, 30, "hardwood", "Knob Ø 30", "Kitasa Ø 30", "Knauf Ø 30"),
        ("S", 1, BASE_Y[1] - STOP_Y0 - 5, STOP_W, STOP_H, "hardwood, straight",
         "Side stop", "Kizuizi cha pembeni", "Seitenanschlag"),
        ("A", 1, FENCE_L, FENCE_W, FENCE_H, "hardwood, straight", "Fence", "Kizuizi cha nyuma",
         "Anschlagleiste"),
        ("D", 3, PEG_L, PEG_D, PEG_D, "beech dowel Ø 12", "Peg (1 spare)",
         "Kigingi (1 cha akiba)", "Steckstift (1 Ersatz)"),
    ]


HARDWARE = [
    ("1", "Bolt M10 × 140, 2 washers, lock nut", "Bolti M10 × 140, washa 2, nati ya kufunga",
     "Schraube M10 × 140, 2 Scheiben, Sicherungsmutter"),
    ("2", "Countersunk bolts M6 × 35, wing nuts, washers", "Bolti M6 × 35 za kichwa bapa, nati za "
     "mabawa, washa", "Senkschrauben M6 × 35, Flügelmuttern, Scheiben"),
    ("2", "Steel pins Ø 3 × 20 (cut nails) as blade stop", "Pini za chuma Ø 3 × 20 (misumari "
     "iliyokatwa) za kusimamisha kiwembe", "Stahlstifte Ø 3 × 20 (abgekniffene Nägel) als "
     "Klingenanschlag"),
    ("~30", "Wood screws 4 × 40, 4 × 25; wood glue", "Skrubu za mbao 4 × 40, 4 × 25; gundi ya mbao",
     "Holzschrauben 4 × 40, 4 × 25; Holzleim"),
    ("100", "Snap-off blades 18 mm (bring from Germany)",
     "Viwembe vya kuvunja 18 mm (vinaletwa kutoka Ujerumani)",
     "Abbrechklingen 18 mm (aus Deutschland mitbringen)"),
    ("1", "Pliers for snapping blades", "Koleo la kuvunja viwembe", "Zange zum Abbrechen der Klingen"),
]


# ═════════════════════════════════════════════════════════════════════
#  Zeichnungen
# ═════════════════════════════════════════════════════════════════════

INK = lk.INK
DIMC = "#7a3e12"


def rgb(c):
    return "#%02x%02x%02x" % c


def prect(x, y, w, h, fill="#ffffff", stroke=INK, sw=0.25, extra=""):
    return ('<rect x="%.3f" y="%.3f" width="%.3f" height="%.3f" fill="%s" stroke="%s" '
            'stroke-width="%g"%s/>\n' % (x, y, w, h, fill, stroke, sw, extra))


def pline(pts, stroke=INK, sw=0.25, fill="none", dash=None, close=False):
    d = "M" + " L".join("%.3f,%.3f" % p for p in pts) + (" Z" if close else "")
    da = ' stroke-dasharray="%s"' % dash if dash else ""
    return '<path d="%s" stroke="%s" stroke-width="%g" fill="%s"%s/>\n' % (d, stroke, sw, fill, da)


def arrow(x, y, ang, s=1.6):
    a1, a2 = ang + math.radians(160), ang - math.radians(160)
    return pline([(x + s * math.cos(a1), y + s * math.sin(a1)), (x, y),
                  (x + s * math.cos(a2), y + s * math.sin(a2))], DIMC, 0.2, DIMC, close=True)


def dim(x1, y1, x2, y2, off, label, size=2.6, ext=True):
    """Maßlinie zwischen (x1,y1) und (x2,y2), um off senkrecht versetzt (Seitenkoordinaten)."""
    ang = math.atan2(y2 - y1, x2 - x1)
    nx, ny = -math.sin(ang), math.cos(ang)
    a = (x1 + nx * off, y1 + ny * off)
    b = (x2 + nx * off, y2 + ny * off)
    out = ""
    if ext:
        sgn = 1 if off >= 0 else -1
        out += pline([(x1 + nx * sgn * 0.8, y1 + ny * sgn * 0.8), (a[0] + nx * sgn * 1.2,
                                                                   a[1] + ny * sgn * 1.2)], DIMC, 0.12)
        out += pline([(x2 + nx * sgn * 0.8, y2 + ny * sgn * 0.8), (b[0] + nx * sgn * 1.2,
                                                                   b[1] + ny * sgn * 1.2)], DIMC, 0.12)
    out += pline([a, b], DIMC, 0.15)
    out += arrow(a[0], a[1], ang + math.pi) + arrow(b[0], b[1], ang)
    mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
    deg = math.degrees(ang)
    if deg > 90 or deg < -90:
        deg += 180
    tx, ty = mx + nx * -1.0 if off < 0 else mx - nx * 1.0, my - (1.0 if abs(ny) > 0.5 else 0)
    out += ('<text x="%.2f" y="%.2f" font-size="%.2f" text-anchor="middle" fill="%s" '
            'transform="rotate(%.1f %.2f %.2f)">%s</text>\n'
            % (mx - nx * 1.0, my - ny * 1.0, size, DIMC, deg, mx - nx * 1.0, my - ny * 1.0,
               lk.esc(label)))
    return out


def fmt(v):
    return ("%.1f" % v).rstrip("0").rstrip(".")


def header(title_en, title_sw, title_de, page, npages, W=297.0):
    b = text_runs(12, 14, [(title_en + " · ", "b", INK_T), (title_sw, "bi", INK_T),
                           (" · " + title_de, "b", DE_INK)], 5.4)
    b += text(W - 12, 204, "%d / %d" % (page, npages), 2.8, "end", fill="#666")
    b += pline([(12, 17), (W - 12, 17)], "#999", 0.2)
    b += text(12, 204, "NgarumaVTC · Schneidlade für den Lernkasten A7 · Karton t = %s mm"
              % fmt(T), 2.8, fill="#666")
    return b


def tri_block(x, y, item, n=110, size=3.3, lh=4.1):
    out = ""
    for ln, st, col in lk.step_lines(item, n=n):
        out += text(x, y, ln, size, style=st, fill=col)
        y += lh
    return out, y


def page_overview(parts):
    b = header("Cutting jig", "Kifaa cha kukatia kadibodi", "Schneidlade", 1, 0)
    iso = [(None, s, c) for n, k, s, c in parts if k not in ("M10", "C")]
    b += lk.iso_svg(iso, 12, 20, 150, 92, labels=False)
    # Beschriftungen per Hand: Liste der Hauptteile
    y = 116
    b += text_runs(12, y, [("Wood parts · ", "b", INK_T), ("Vipande vya mbao", "bi", INK_T),
                           (" · Holzliste", "b", DE_INK)], 4.0)
    y += 5
    cols = (12, 22, 80, 130, 178, 196, 214, 232)
    hs = 2.6
    b += text(cols[1], y, "part", hs, fill="#555")
    b += text(cols[2], y, "sehemu", hs, style="i", fill="#555")
    b += text(cols[3], y, "Teil", hs, fill=DE_INK)
    b += text(cols[4], y, "pcs", hs, "end", fill="#555")
    b += text(cols[5], y, "L", hs, "end", fill="#555")
    b += text(cols[6], y, "W", hs, "end", fill="#555")
    b += text(cols[7], y, "T [mm]", hs, "end", fill="#555")
    b += text(cols[7] + 4, y, "material", hs, fill="#555")
    y += 4.2
    for k, cnt, l, w, d, mat, en, sw, de in wood_list():  # noqa
        b += text(cols[0], y, k, 3.0, style="b", fill=ACCENT)
        b += text(cols[1], y, en, 3.0)
        b += text(cols[2], y, sw, 3.0, style="i", fill="#3d3d3d")
        b += text(cols[3], y, de, 3.0, fill=DE_INK)
        b += text(cols[4], y, "%d" % cnt, 3.0, "end")
        b += text(cols[5], y, fmt(l), 3.0, "end")
        b += text(cols[6], y, fmt(w), 3.0, "end")
        b += text(cols[7], y, fmt(d), 3.0, "end")
        b += text(cols[7] + 4, y, mat, 3.0, fill="#444")
        y += 3.9
    # Rechts: Beschläge
    x = 168
    yy = 26
    b += text_runs(x, yy, [("Hardware · ", "b", INK_T), ("Vifaa vya chuma", "bi", INK_T),
                           (" · Beschläge", "b", DE_INK)], 4.0)
    yy += 5.5
    for cnt, en, sw, de in HARDWARE:
        b += text(x, yy, cnt, 3.0, style="b", fill=ACCENT)
        for i, (t, st, col) in enumerate(((en, "", INK_T), (sw, "i", "#3d3d3d"), (de, "", DE_INK))):
            for ln in wrap(t, 62):
                b += text(x + 8, yy, ln, 2.9, style=st, fill=col)
                yy += 3.5
        yy += 1.6
    yy = y + 4
    x = 12
    for ln_item in (("All sizes in mm. The dimensions L × W × T are finished sizes. Plane the rail R "
                     "and the fence A perfectly straight: the cut is only as straight as the rail.",
                     "Vipimo vyote kwa mm. L × W × T ni vipimo vya mwisho. Randa reli R na kizuizi A "
                     "viwe vinyoofu kabisa: mkato ni mnyoofu kama reli ilivyo.",
                     "Alle Maße in mm, Fertigmaße L × B × D. Schiene R und Anschlagleiste A ganz "
                     "gerade abrichten: Der Schnitt wird nur so gerade wie die Schiene."),):
        blk, yy = tri_block(x, yy, ln_item, n=170, size=2.9, lh=3.5)
        b += blk
    if yy > 201:
        log("  WARNUNG: Seite Holzliste läuft über (y = %.0f)" % yy)
    return b


def page_top(holes):
    """Draufsicht mit Hauptmaßen und Lochplan."""
    b = header("Top view and hole plan", "Mwonekano wa juu na mpango wa matundu",
               "Draufsicht und Lochplan", 2, 0)
    s = 0.12                                    # 1 : 8,3
    ox, oy = 22 - BASE_X[0] * s, 28 + BASE_Y[1] * s
    P = lambda x, y: (ox + x * s, oy - y * s)    # noqa: E731

    def R(x0, y0, x1, y1, fill, sw=0.25, dash=None):
        (a, b_), (c, d) = P(x0, y1), P(x1, y0)
        ex = ' stroke-dasharray="%s"' % dash if dash else ""
        return prect(a, b_, c - a, d - b_, fill, INK, sw, ex)
    b += R(BASE_X[0], BASE_Y[0], BASE_X[1], BASE_Y[1], rgb(PLY))
    b += R(GROOVE_X[0], -GROOVE_W / 2, GROOVE_X[1], GROOVE_W / 2, rgb(SOFT))
    b += R(RAIL_X[0], RAIL_Y0, RAIL_X[1], RAIL_Y1, rgb(WOOD_D))
    b += R(PIVOT_X - PIVOT_BLOCK[0] / 2, RAIL_Y0 - PIVOT_BLOCK[1], PIVOT_X + PIVOT_BLOCK[0] / 2,
           RAIL_Y0, rgb(WOOD))
    b += R(PIVOT_X - PIVOT_BLOCK[0] / 2, RAIL_Y1, PIVOT_X + PIVOT_BLOCK[0] / 2,
           RAIL_Y1 + PIVOT_BLOCK[1], rgb(WOOD))
    for y0 in (RAIL_Y0 - FORK[1], RAIL_Y1):
        b += R(FORK_X, y0, FORK_X + FORK[0], y0 + FORK[1], rgb(WOOD))
    b += R(-STOP_W, STOP_Y0, 0, BASE_Y[1] - 5, rgb(WOOD))
    # Schlitten in Parkstellung
    b += R(CAR_PARK_X, RAIL_Y0 - PLAY - CHEEK, CAR_PARK_X + CAR_L, BLADE_T / 2 + CLAMP_T, rgb(WOOD),
           0.25, "1,0.6")
    # Anschlagleiste gestrichelt in Stellung 117
    d0 = round(lk.WB, 2)
    b += R(0, d0, FENCE_L, d0 + FENCE_W, "none", 0.3, "2,1")
    # Schnittlinie
    a, c = P(GROOVE_X[0], 0), P(GROOVE_X[1], 0)
    b += pline([a, c], "#c0392b", 0.35, dash="4,1,1,1")
    # Löcher
    for i, (d, (y, xs)) in enumerate(holes.items()):
        for x in xs:
            px, py = P(x, y)
            b += '<circle cx="%.2f" cy="%.2f" r="%.2f" fill="#fff" stroke="%s" stroke-width="0.2"/>\n' % (
                px, py, PEG_D / 2 * s, INK)
        for x in xs:
            px, py = P(x, y)
            b += text(px, py + (-1.4 if i % 2 == 0 else 3.2), fmt(d), 2.1, "middle", "b", ACCENT)
    # Hauptmaße
    p0, p1 = P(BASE_X[0], BASE_Y[0]), P(BASE_X[1], BASE_Y[0])
    b += dim(p0[0], p0[1], p1[0], p1[1], -7, fmt(BASE_X[1] - BASE_X[0]))
    p0, p1 = P(BASE_X[1], BASE_Y[0]), P(BASE_X[1], BASE_Y[1])
    b += dim(p0[0], p0[1], p1[0], p1[1], -6, fmt(BASE_Y[1] - BASE_Y[0]))
    p0, p1 = P(BASE_X[0], BASE_Y[1]), P(0, BASE_Y[1])
    b += dim(p0[0], p0[1], p1[0], p1[1], 5, fmt(-BASE_X[0]))
    p0, p1 = P(0, BASE_Y[1]), P(FORK_X, BASE_Y[1])
    b += dim(p0[0], p0[1], p1[0], p1[1], 5, fmt(FORK_X))
    p0, p1 = P(BASE_X[0], 0), P(BASE_X[0], BASE_Y[0])
    b += dim(p0[0], p0[1], p1[0], p1[1], -6, fmt(-BASE_Y[0]))
    p0, p1 = P(PIVOT_X, RAIL_Y0 - 25), P(0, RAIL_Y0 - 25)
    b += dim(p0[0], p0[1], p1[0], p1[1], 0, fmt(-PIVOT_X), ext=False)
    # Legende links unten
    lx, ly = P(-60, BASE_Y[0])
    ly += 12
    for item in (("x = 0: face of the side stop S. y = 0: cut line (blade). All holes Ø %s mm, "
                  "drilled through G, square to the face. Fence A shown dashed at %s mm."
                  % (fmt(PEG_D), fmt(d0)),
                  "x = 0: uso wa kizuizi S. y = 0: mstari wa kukata (kiwembe). Matundu yote Ø %s mm, "
                  "yatobolewe G hadi chini, wima. Kizuizi A kimechorwa kwa mistari kwenye mm %s."
                  % (fmt(PEG_D), fmt(d0)),
                  "x = 0: Anlagefläche Seitenanschlag S. y = 0: Schnittlinie (Klinge). Alle Löcher "
                  "Ø %s mm durch G, senkrecht. Anschlagleiste A gestrichelt in Stellung %s mm."
                  % (fmt(PEG_D), fmt(d0))),):
        blk, ly = tri_block(12, ly, item, n=125, size=2.8, lh=3.4)
        b += blk
    # Lochtabelle rechts
    tx, ty = 238, 26
    b += text(tx, ty, "holes · matundu · Löcher", 3.0, style="b")
    ty += 4.5
    for t_, x_ in (("size", tx), ("y", tx + 17), ("x1", tx + 29), ("x2", tx + 42)):
        b += text(x_, ty, t_, 2.6, "end" if x_ != tx else "start", fill="#555")
    b += text(tx + 46, ty, "parts", 2.6, fill="#555")
    ty += 3.8
    for d, (y, xs) in holes.items():
        use = ", ".join("strip" if u == "strip" else u for u in measures()[d])
        b += text(tx, ty, fmt(d), 2.8, style="b", fill=ACCENT)
        b += text(tx + 17, ty, fmt(y), 2.8, "end")
        b += text(tx + 29, ty, fmt(xs[0]), 2.8, "end")
        b += text(tx + 42, ty, fmt(xs[1]), 2.8, "end")
        b += text(tx + 46, ty, use, 2.4, fill="#444")
        ty += 3.6
    ty += 2
    for item in (("y = size + %s (fence) + %s (half peg). Write the size next to each hole with a "
                  "marker." % (fmt(FENCE_W), fmt(PEG_D / 2)),
                  "y = kipimo + %s + %s. Andika kipimo karibu na kila tundu." % (fmt(FENCE_W),
                                                                                fmt(PEG_D / 2)),
                  "y = Maß + %s + %s. Maß mit Filzstift neben jedes Loch schreiben."
                  % (fmt(FENCE_W), fmt(PEG_D / 2))),):
        blk, ty = tri_block(tx, ty, item, n=38, size=2.5, lh=3.0)
        b += blk
    return b


def page_section():
    """Schnitt quer zur Schiene 1 : 1 und Seitenansicht der Klingenseite 1 : 1."""
    b = header("Carriage, scale 1 : 1", "Gari, kipimo 1 : 1", "Schlitten, Maßstab 1 : 1", 3, 0)
    zr = T
    cz0 = zr + CLEAR
    ztop = zr + RAIL_H
    hz = holder_top(zr)
    zw1 = ztop + PLAY + CAR_TOP
    base_line = 146.0                       # Seiten-y von z = 0

    # ── Schnitt (y nach rechts, z nach oben) ──
    ya, yb = RAIL_Y0 - 22, 38.0
    ox = 22 - ya
    P = lambda y, z: (ox + y, base_line - z)     # noqa: E731

    def R(y0, z0, y1, z1, fill, sw=0.3):
        (a, b_), (c, d) = P(y0, z1), P(y1, z0)
        return prect(a, b_, c - a, d - b_, fill, INK, sw)

    def D(y0, z0, y1, z1, off, lab):
        a, c = P(y0, z0), P(y1, z1)
        return dim(a[0], a[1], c[0], c[1], off, lab)

    b += text(22, 27, "Section across the rail", 3.3, style="b")
    b += text(22, 31, "Kata ya reli · Schnitt quer zur Schiene", 3.0, style="i", fill="#3d3d3d")
    b += R(ya, -BASE_T, yb, 0, rgb(PLY))
    b += R(-GROOVE_W / 2, -GROOVE_D, GROOVE_W / 2, 0, rgb(SOFT))
    b += R(ya, 0, yb, T, rgb(CARDB), 0.2)
    b += R(RAIL_Y0, zr, RAIL_Y1, ztop, rgb(WOOD_D))
    b += R(RAIL_Y0 - PLAY - CHEEK, ztop + PLAY, RAIL_Y1 + PLAY, zw1, rgb(WOOD))
    b += R(RAIL_Y0 - PLAY - CHEEK, cz0, RAIL_Y0 - PLAY, ztop + PLAY, rgb(WOOD))
    b += R(RAIL_Y1 + PLAY, cz0, -BLADE_T / 2, hz, rgb(WOOD))
    b += R(BLADE_T / 2, cz0, BLADE_T / 2 + CLAMP_T, hz, rgb(WOOD))
    b += R(-BLADE_T / 2, -BLADE_DEPTH, BLADE_T / 2, cz0 + 40, rgb(STEEL), 0.15)
    kx = (RAIL_Y0 + RAIL_Y1) / 2
    b += R(kx - 15, zw1, kx + 15, zw1 + 35, rgb(WOOD_D))
    zb6 = cz0 + 26
    yi = RAIL_Y1 + PLAY                     # Innenfläche W5: Senkkopf bündig
    b += R(yi + 3.3, zb6 - 3, BLADE_T / 2 + CLAMP_T + 6, zb6 + 3, "#d0d4d8", 0.2)
    b += pline([P(yi, zb6 - 6), P(yi + 3.3, zb6 - 3), P(yi + 3.3, zb6 + 3), P(yi, zb6 + 6)], INK, 0.2,
               "#d0d4d8", close=True)
    b += R(BLADE_T / 2 + CLAMP_T, zb6 - 7, BLADE_T / 2 + CLAMP_T + 1.5, zb6 + 7, "#d0d4d8", 0.2)
    b += R(BLADE_T / 2 + CLAMP_T + 1.5, zb6 - 4, BLADE_T / 2 + CLAMP_T + 6.5, zb6 + 4, "#d0d4d8", 0.2)
    b += pline([P(0, -BASE_T - 4), P(0, hz + 8)], "#c0392b", 0.3, dash="3,1,1,1")
    b += text(P(0, hz + 10)[0], P(0, hz + 10)[1], "y = 0", 2.8, "middle", fill="#c0392b")
    b += D(RAIL_Y0, zw1 + 35, RAIL_Y1, zw1 + 35, -5, fmt(RAIL_W))
    b += D(RAIL_Y1, hz, 0, hz, -5, fmt(-RAIL_Y1))
    b += D(ya, zr, ya, ztop, 6, fmt(RAIL_H))
    b += D(RAIL_Y0 - PLAY - CHEEK, cz0, RAIL_Y0 - PLAY - CHEEK, ztop + PLAY, 14, fmt(ztop + PLAY - cz0))
    b += D(BLADE_T / 2 + CLAMP_T, cz0, BLADE_T / 2 + CLAMP_T, hz, -8, fmt(hz - cz0))
    b += D(yb, -GROOVE_D, yb, 0, -5, fmt(GROOVE_D))
    b += D(-GROOVE_W / 2, -BASE_T, GROOVE_W / 2, -BASE_T, 5, fmt(GROOVE_W))
    b += D(yb, -BASE_T, yb, 0, -12, fmt(BASE_T))
    b += text(P(yb + 2, T)[0], P(0, T / 2)[1] + 1, "t", 2.6, fill="#555")
    for y, z, lab in [(RAIL_Y0 + RAIL_W / 2, zr + RAIL_H / 2, "R"),
                      (RAIL_Y0 - PLAY - CHEEK / 2, cz0 + 20, "W2"),
                      (RAIL_Y1 + PLAY + CHEEK / 2, cz0 + 60, "W5"),
                      (BLADE_T / 2 + CLAMP_T / 2, cz0 + 60, "W3"),
                      (RAIL_Y0 + 25, ztop + PLAY + CAR_TOP / 2, "W1"), (kx, zw1 + 20, "W4"),
                      (ya + 15, -BASE_T / 2, "G"), (-8, -GROOVE_D / 2 - 0.5, "O")]:
        px, py = P(y, z)
        b += '<circle cx="%.2f" cy="%.2f" r="2.6" fill="#fff" stroke="%s" stroke-width="0.3"/>\n' % (
            px, py, ACCENT)
        b += text(px, py + 0.9, lab, 2.3 if len(lab) > 1 else 2.8, "middle", "b", ACCENT)

    # ── Seitenansicht Klingenseite, von hinten gesehen; x nach rechts = Zugrichtung ──
    sx0 = 170.0
    Q = lambda x, z: (sx0 + x, base_line - z)   # noqa: E731

    def RQ(x0, z0, x1, z1, fill, sw=0.3, dash=None):
        (a, b_), (c, d) = Q(x0, z1), Q(x1, z0)
        ex = ' stroke-dasharray="%s"' % dash if dash else ""
        return prect(a, b_, c - a, d - b_, fill, INK, sw, ex)

    def D2(x0, z0, x1, z1, off, lab):
        a_, c_ = Q(x0, z0), Q(x1, z1)
        return dim(a_[0], a_[1], c_[0], c_[1], off, lab)

    b += text(sx0, 27, "Blade cheek W5, clamp plate W3 removed", 3.3, style="b")
    b += text(sx0, 31, "Ubavu W5 bila bamba W3 · Klingenwange W5 ohne Klemmplatte", 3.0, style="i",
              fill="#3d3d3d")
    b += RQ(-15, -GROOVE_D, CAR_L + 15, 0, rgb(SOFT), 0.2)
    b += RQ(-15, 0, CAR_L + 15, T, rgb(CARDB), 0.2)
    b += RQ(0, cz0, CAR_L, hz, rgb(WOOD))
    b += RQ(0, ztop + PLAY, CAR_L, zw1, "none", 0.2, "1.5,1")
    b += text(Q(4, 0)[0], Q(0, zw1 - 4)[1], "W1 behind", 2.3, fill="#555")
    x_tip = BLADE_X
    bl = blade_solid(x_tip)
    pts = []
    for v in bl.Vertexes:
        if v.Y > 0:
            pts.append((v.X, v.Z))
    cx = sum(p[0] for p in pts) / len(pts)
    cz = sum(p[1] for p in pts) / len(pts)
    pts.sort(key=lambda p: math.atan2(p[1] - cz, p[0] - cx))
    b += pline([Q(x, z) for x, z in pts], INK, 0.25, rgb(STEEL), close=True)
    bolts, pins = blade_marks(x_tip)
    for x, z in bolts:
        px, py = Q(x, z)
        b += '<circle cx="%.2f" cy="%.2f" r="3.2" fill="#d0d4d8" stroke="%s" stroke-width="0.25"/>\n' % (
            px, py, INK)
    for x, z in pins:
        px, py = Q(x, z)
        b += '<circle cx="%.2f" cy="%.2f" r="1" fill="%s"/>\n' % (px, py, INK)
    b += D2(0, hz, CAR_L, hz, -5, fmt(CAR_L))
    b += D2(0, -BLADE_DEPTH, x_tip, -BLADE_DEPTH, 10, fmt(BLADE_X))
    b += D2(CAR_L, cz0, CAR_L, hz, -6, fmt(hz - cz0))
    # Koordinaten der Bohrungen ab linker Unterkante W5
    yy = 37
    b += text(sx0, yy, "holes W5 + W3 from bottom left corner (x | z) · mashimo · Bohrungen:", 2.6,
              fill="#444")
    yy += 3.8
    for i, ((x, z), what) in enumerate(zip(bolts + pins, ("M6", "M6", "pin Ø 3", "pin Ø 3"))):
        b += text(sx0 + (i // 2) * 52, yy + (i % 2) * 3.4,
                  "%s:  %s | %s" % (what, fmt(round(x)), fmt(round(z - cz0))), 2.7)
    b += text(Q(CAR_L, 0)[0], Q(0, -BLADE_DEPTH - 9)[1], "edge forward, tip behind  → pull", 2.6,
              "end", "i")
    b += text(Q(CAR_L, 0)[0], Q(0, -BLADE_DEPTH - 12.5)[1], "makali mbele, ncha nyuma · "
              "Schneide vorn, Spitze hinten", 2.6, "end", "i", "#3d3d3d")

    y = 178
    it = ("The blade lies flat on the blade cheek W5, its back edge against two pins. The clamp plate "
          "W3 presses it with two countersunk M6 bolts and wing nuts. Set the blade so that it goes %s mm into the "
          "strip O. Cut line = blade = %s mm behind the rail. All cheeks float %s mm above the cardboard."
          % (fmt(BLADE_DEPTH), fmt(-RAIL_Y1), fmt(CLEAR)),
          "Kiwembe kinalala kwenye ubavu W5, mgongo wake ukigusa misumari miwili. Bamba W3 linakibana "
          "kwa bolti mbili M6 za kichwa bapa na nati za mabawa. Kiwembe kiingie mm %s ndani ya O. Mstari wa kukata uko "
          "mm %s nyuma ya reli." % (fmt(BLADE_DEPTH), fmt(-RAIL_Y1)),
          "Die Klinge liegt flach an der Klingenwange W5, der Rücken an zwei Stiften. Die Klemmplatte "
          "W3 drückt sie mit zwei Senkschrauben M6 und Flügelmuttern an. Klinge so einstellen, dass sie %s mm in die "
          "Opferleiste O taucht. Schnittlinie = Klinge = %s mm hinter der Schiene. Alle Wangen "
          "schweben %s mm über dem Karton." % (fmt(BLADE_DEPTH), fmt(-RAIL_Y1), fmt(CLEAR)))
    blk, y = tri_block(12, y, it, n=160, size=2.9, lh=3.5)
    b += blk
    if y > 201:
        log("  WARNUNG: Seite Schlitten läuft über (y = %.0f)" % y)
    return b


BUILD = [
    ("Base G: cut the groove %s × %s mm, %s mm from the long front edge (centre), and glue nothing "
     "into it. The sacrificial strip O must fit tightly but can be pulled out." % (
         fmt(GROOVE_W), fmt(GROOVE_D), fmt(-BASE_Y[0])),
     "Ubao G: chonga mfereji %s × %s mm, mm %s kutoka ukingo wa mbele (katikati). Kipande O "
     "kiingie kwa kubana lakini kiweze kutolewa." % (fmt(GROOVE_W), fmt(GROOVE_D), fmt(-BASE_Y[0])),
     "Grundplatte G: Nut %s × %s mm fräsen, Mitte %s mm von der vorderen Längskante. Opferleiste O "
     "stramm einpassen, nicht einleimen." % (fmt(GROOVE_W), fmt(GROOVE_D), fmt(-BASE_Y[0]))),
    ("Rail R: plane it straight and square. Drill the slot for the M10 bolt %s mm from the left "
     "end: Ø 10, 6 mm long (up and down), so that the rail lies flat with or without cardboard."
     % fmt(PIVOT_X - RAIL_X[0]),
     "Reli R: iranda iwe nyoofu na ya mraba. Toboa tundu refu la bolti M10 mm %s kutoka mwisho wa "
     "kushoto: Ø 10, urefu mm 6 (juu-chini)." % fmt(PIVOT_X - RAIL_X[0]),
     "Schiene R: gerade und winklig abrichten. Langloch für M10 %s mm vom linken Ende: Ø 10, 6 mm "
     "lang senkrecht, damit die Schiene mit und ohne Karton flach aufliegt." % fmt(PIVOT_X - RAIL_X[0])),
    ("Carriage W1–W5 (page 3): glue and screw the front cheek W2 under the top W1 and the blade "
     "cheek W5 to the back of W1, so that the carriage slides on the rail without play (%s mm each "
     "side). Drill W5 and W3 together for the bolts and pins (page 3), countersink W5 on the inside so the "
     "bolt heads are flush, glue the pins into W5. Fit the knob W4."
     % fmt(PLAY),
     "Gari W1–W5 (ukurasa 3): gundisha na funga ubavu W2 chini ya W1 na ubavu W5 nyuma ya W1, ili "
     "gari liteleze kwenye reli bila kulegea (mm %s kila upande). Toboa W5 na W3 pamoja kwa bolti na "
     "pini (ukurasa 3), chonga W5 ndani ili vichwa vya bolti visitokeze, gundisha pini kwenye W5. "
     "Funga kitasa W4." % fmt(PLAY),
     "Schlitten W1–W5 (Seite 3): Wange W2 unter die Deckplatte W1 und die Klingenwange W5 hinten an "
     "W1 leimen und schrauben, so dass der Schlitten spielfrei auf der Schiene gleitet (%s mm je "
     "Seite). W5 und W3 zusammen für Schrauben und Stifte bohren (Seite 3), W5 innen senken, so "
     "dass die Schraubenköpfe bündig sind, Stifte in W5 einleimen. Knauf W4 aufleimen." % fmt(PLAY)),
    ("Put the rail with the carriage on the base, back face of the rail %s mm in front of the groove "
     "centre. Screw on the pivot cheeks P (bolt M10) and the fork blocks F, the rail must drop into "
     "the fork without play sideways. Screw the handle H on the right end." % fmt(-RAIL_Y1),
     "Weka reli pamoja na gari juu ya ubao, uso wa nyuma wa reli mm %s mbele ya katikati ya mfereji. "
     "Funga vishikio P (bolti M10) na vizuizi F; reli iingie kwenye uma bila kulegea. Funga mshiko H."
     % fmt(-RAIL_Y1),
     "Schiene mit Schlitten auflegen, Rückseite der Schiene %s mm vor Mitte Nut. Lagerwangen P "
     "(M10) und Fanggabel F anschrauben, die Schiene muss seitlich spielfrei in die Gabel fallen. "
     "Griff H rechts aufschrauben." % fmt(-RAIL_Y1)),
    ("Test cut: lay cardboard over the whole length, lower the rail, pull the carriage. The cut in "
     "the strip O is now the line y = 0. Screw the side stop S at x = 0 exactly square to this line.",
     "Jaribio: weka kadibodi urefu wote, shusha reli, vuta gari. Mkato kwenye O sasa ni mstari y = 0. "
     "Funga kizuizi S kwenye x = 0 kwa pembemraba kamili na mstari huu.",
     "Probeschnitt: Karton über die ganze Länge legen, Schiene ab, Schlitten durchziehen. Der Schnitt "
     "in O ist jetzt die Linie y = 0. Seitenanschlag S bei x = 0 genau rechtwinklig dazu anschrauben."),
    ("Holes: measure every hole from the line y = 0 (table on page 2), mark with a square, drill Ø %s "
     "on the pillar drill. Write the size next to each hole. Pegs D: Ø %s × %s, ends chamfered."
     % (fmt(PEG_D), fmt(PEG_D), fmt(PEG_L)),
     "Matundu: pima kila tundu kutoka mstari y = 0 (jedwali ukurasa 2), weka alama, toboa Ø %s kwa "
     "mashine ya kutoboa. Andika kipimo karibu na kila tundu. Vigingi D: Ø %s × %s."
     % (fmt(PEG_D), fmt(PEG_D), fmt(PEG_L)),
     "Löcher: jedes Loch von der Linie y = 0 aus anreißen (Tabelle Seite 2), auf der Ständerbohrmaschine "
     "Ø %s bohren, Maß daneben schreiben. Stifte D: Ø %s × %s, Enden angefast."
     % (fmt(PEG_D), fmt(PEG_D), fmt(PEG_L))),
    ("Check: cut one strip at every size and measure it. If all sizes are too long or too short by "
     "the same amount, plane the front face of the fence A or glue on a veneer.",
     "Hakiki: kata kipande kimoja kwa kila kipimo na kipime. Vipimo vyote vikizidi au vikipungua "
     "kwa kiasi kilekile, randa uso wa mbele wa A au gundisha kipande chembamba.",
     "Prüfen: bei jedem Maß einen Streifen schneiden und messen. Sind alle um denselben Betrag zu "
     "lang oder zu kurz, die Vorderseite der Anschlagleiste A abhobeln oder ein Furnier aufleimen."),
]

USE = [
    ("Set the fence: put the two pegs D into the holes of the size you need, push the fence A "
     "back against the pegs.",
     "Weka kizuizi: chomeka vigingi viwili D kwenye matundu ya kipimo unachohitaji, sukuma kizuizi "
     "A nyuma hadi kigusane na vigingi.",
     "Anschlag einstellen: die beiden Stifte D in die Löcher des gewünschten Maßes stecken, "
     "Anschlagleiste A nach hinten gegen die Stifte schieben."),
    ("Lift the rail at the handle. Push the cardboard under the rail until it touches the fence. "
     "For short pieces also push it to the left against the side stop S. A whole board sticks out "
     "far in front: put a table of the same height there.",
     "Inua reli kwa mshiko. Sukuma kadibodi chini ya reli hadi iguse kizuizi A. Kwa vipande vifupi "
     "isukume pia kushoto hadi kizuizi S. Karatasi nzima inatokeza mbele sana: weka meza ya urefu "
     "uleule hapo.",
     "Schiene am Griff anheben. Karton unter der Schiene bis an die Anschlagleiste schieben. Kurze "
     "Teile zusätzlich links an den Seitenanschlag S schieben. Ein ganzer Bogen ragt weit nach vorn "
     "über: dort einen gleich hohen Tisch hinstellen."),
    ("Lower the rail, press it down with the left hand. Pull the carriage with the right hand in one "
     "smooth stroke from left to right. Lift the rail, take the piece, push the carriage back to the "
     "left end.",
     "Shusha reli, ibonyeze kwa mkono wa kushoto. Vuta gari kwa mkono wa kulia kwa mvuto mmoja "
     "kutoka kushoto kwenda kulia. Inua reli, chukua kipande, rudisha gari mwisho wa kushoto.",
     "Schiene ablassen und mit der linken Hand andrücken. Schlitten mit der rechten Hand in einem "
     "Zug von links nach rechts ziehen. Schiene anheben, Teil entnehmen, Schlitten nach links zurück."),
    ("Order: first cut the long strips from the board, then cut the strips to length (cutting plan). "
     "Mark each piece with its letter (A, E, U, S, L1 … B5) with a pencil.",
     "Mpangilio: kwanza kata vipande virefu kutoka kwenye karatasi kubwa, kisha vikate kwa urefu "
     "(mpango wa kukata). Andika herufi ya kila kipande (A, E, U, S, L1 … B5) kwa penseli.",
     "Reihenfolge: erst die langen Streifen vom Bogen schneiden, dann die Streifen ablängen "
     "(Schneidplan). Jedes Teil mit Bleistift beschriften (A, E, U, S, L1 … B5)."),
    ("Blade: when the cut tears, snap off one segment with pliers. Replace the strip O when it is "
     "cut deep. Always park the carriage at the left end. Never reach under the lifted rail.",
     "Kiwembe: mkato ukianza kuchanika, vunja kipande kimoja kwa koleo. Badilisha O ikikatwa sana. "
     "Daima weka gari mwisho wa kushoto. Usiingize mkono chini ya reli iliyoinuliwa.",
     "Klinge: Reißt der Schnitt, ein Segment mit der Zange abbrechen. Opferleiste O wechseln, wenn "
     "sie tief eingeschnitten ist. Schlitten immer links parken. Nie unter die angehobene Schiene "
     "greifen."),
]


def write_numbered(b, items, y, n=150, size=3.2, lh=3.9, y_max=200):
    for i, it in enumerate(items):
        lines = lk.step_lines(it, n=n)
        if y + len(lines) * lh > y_max:
            log("  WARNUNG: Text läuft über (Schritt %d)" % (i + 1))
        b += '<circle cx="16" cy="%.2f" r="3" fill="%s"/>\n' % (y - 1.2, ACCENT)
        b += text(16, y, str(i + 1), 3.4, "middle", "b", "#fff")
        prev = None
        for ln, st, col in lines:
            if prev is not None and prev != col:
                y += 0.5
            b += text(22, y, ln, size, style=st, fill=col)
            y += lh
            prev = col
        y += 2.2
    return b, y


def page_build():
    b = header("Building the jig", "Kutengeneza kifaa", "Bau der Schneidlade", 4, 0)
    b, y = write_numbered(b, BUILD, 25, n=160, size=3.0, lh=3.6)
    return b


def page_use(parts_use):
    b = header("Using the jig", "Kutumia kifaa", "Bedienung", 5, 0)
    iso = [(None, s, c) for n, k, s, c in parts_use if k not in ("M10",)]
    b += lk.iso_svg(iso, 175, 22, 110, 70, labels=False)
    b, y = write_numbered(b, USE[:3], 26, n=88)
    b, y = write_numbered_from(b, USE[3:], max(y, 100), 4)
    return b


def write_numbered_from(b, items, y, first, n=150):
    for i, it in enumerate(items):
        b += '<circle cx="16" cy="%.2f" r="3" fill="%s"/>\n' % (y - 1.2, ACCENT)
        b += text(16, y, str(first + i), 3.4, "middle", "b", "#fff")
        prev = None
        for ln, st, col in lk.step_lines(it, n=n):
            if prev is not None and prev != col:
                y += 0.5
            b += text(22, y, ln, 3.2, style=st, fill=col)
            y += 3.9
            prev = col
        y += 2.6
    if y > 198:
        log("  WARNUNG: Bedienungsseite läuft über (y = %.0f)" % y)
    return b, y


def page_plan(plan):
    bu, bv = lk.BOARD
    b = header("Cutting plan per board", "Mpango wa kukata kwa kila karatasi",
               "Schneidplan je Bogen", 6, 0)
    s = min(150 / bu, 160 / bv)
    ox, oy = 14, 26
    # Bogen: u nach rechts, v nach unten; Wellen = senkrechte Striche (entlang v)
    b += lk.rect_svg(ox, oy, bu * s, bv * s, "#efe3cc", INK, 0.3, True, 4.0)
    x = ox + TRIM * s
    for i, st in enumerate(plan["bstrips"]):
        w = plan["wb"] * s
        b += prect(x, oy + TRIM * s, w, plan["Vv"] * s, rgb(lk.CARD_OUT), INK, 0.25)
        yy = oy + TRIM * s
        for ln, k in st:
            b += prect(x, yy, w, ln * s, "none", INK, 0.15)
            if ln * s > 4:
                b += text(x + w / 2, yy + ln * s / 2 + 1, k, 2.4, "middle", "b", ACCENT)
            yy += ln * s
        x += w
    yy = oy + TRIM * s
    for w, st in plan["wstrips"]:
        b += prect(x, yy, plan["ru"] * s, w * s, rgb(lk.CARD), INK, 0.25)
        xx = x
        for ln, k in st:
            b += prect(xx, yy, ln * s, w * s, "none", INK, 0.15)
            b += text(xx + ln * s / 2, yy + w * s / 2 + 1, k, 2.2, "middle", "b", "#fff")
            xx += ln * s
        yy += w * s
    b += text(ox, oy + bv * s + 5, "board %s × %s mm, flutes along %s (vertical lines) · %d boxes per "
              "board" % (fmt(bu), fmt(bv), fmt(bv), plan["n"]), 2.8, style="i")
    b += text(ox, oy + bv * s + 9, "karatasi %s × %s · masanduku %d kwa kila karatasi · Bogen %s × %s, "
              "%d Kästen je Bogen" % (fmt(bu), fmt(bv), plan["n"], fmt(bu), fmt(bv), plan["n"]), 2.8,
              style="i", fill="#3d3d3d")
    # Liste rechts
    tx, y = 175, 26
    b += text_runs(tx, y, [("1  ", "b", ACCENT), ("trim · kata ukingo · Rand", "b", INK_T)], 3.4)
    y += 4.4
    b += text(tx + 5, y, "%s mm off one long and one short edge" % fmt(TRIM), 2.9)
    y += 7
    b += text_runs(tx, y, [("2  ", "b", ACCENT), ("bottom strips · vitako · Bodenstreifen", "b", INK_T)],
                   3.4)
    y += 4.4
    b += text(tx + 5, y, "fence %s: %d × %s mm (cut along the flutes)" % (
        fmt(plan["wb"]), len(plan["bstrips"]), fmt(plan["Vv"])), 2.9)
    y += 7
    b += text_runs(tx, y, [("3  ", "b", ACCENT), ("wall strips · kuta · Wandstreifen", "b", INK_T)], 3.4)
    y += 4.4
    cnt = {}
    for w, _ in plan["wstrips"]:
        cnt[w] = cnt.get(w, 0) + 1
    for w in sorted(cnt, reverse=True):
        b += text(tx + 5, y, "fence %s: %d × %s mm (across the flutes)" % (fmt(w), cnt[w],
                                                                           fmt(plan["ru"])), 2.9)
        y += 4.0
    y += 3
    b += text_runs(tx, y, [("4  ", "b", ACCENT), ("cut to length · kata urefu · ablängen", "b", INK_T)],
                   3.4)
    y += 4.4
    rows = {}
    for st in plan["bstrips"]:
        key = (plan["wb"], tuple(sorted([(round(l, 2), k) for l, k in st], reverse=True)))
        rows[key] = rows.get(key, 0) + 1
    for w, st in plan["wstrips"]:
        key = (w, tuple(sorted([(round(l, 2), k) for l, k in st], reverse=True)))
        rows[key] = rows.get(key, 0) + 1
    for (w, st), c in sorted(rows.items(), key=lambda t: (-t[0][0], t[0][1])):
        line = "%d × strip %s:  " % (c, fmt(w)) + "  ".join("%s %s" % (k, fmt(l)) for l, k in st)
        for ln in wrap(line, 62):
            b += text(tx + 5, y, ln, 2.7)
            y += 3.5
        y += 0.6
    y += 3
    bu_, bv_ = lk.BOARD
    need = int(math.ceil(lk.N_BOXES * (1 + lk.SCRAP)))
    boards = int(math.ceil(need / float(plan["n"])))
    for it in (("Series: %d boxes (+%d %% scrap) = %d → %d boards %s × %s." % (
            lk.N_BOXES, lk.SCRAP * 100, need, boards, fmt(bu_), fmt(bv_)),
                "Jumla: masanduku %d (+%d %%) = %d → karatasi %d." % (lk.N_BOXES, lk.SCRAP * 100, need,
                                                                     boards),
                "Serie: %d Kästen (+%d %% Ausschuss) = %d → %d Bögen." % (lk.N_BOXES, lk.SCRAP * 100,
                                                                        need, boards)),
               ("Fence size for each piece = its length in this list. The cut-off rest of a strip "
                "is scrap.",
                "Kipimo cha kizuizi = urefu wa kipande kwenye orodha hii.",
                "Anschlagmaß = Länge des Teils in dieser Liste. Reststücke sind Abfall.")):
        blk, y = tri_block(tx, y, it, n=60, size=2.8, lh=3.4)
        b += blk
        y += 1.5
    if y > 200:
        log("  WARNUNG: Schneidplan läuft über (y = %.0f)" % y)
    return b, boards


def write_pdf(pages):
    os.makedirs(OUT, exist_ok=True)
    n = len(pages)
    svgs = []
    for i, b in enumerate(pages):
        b = b.replace(">%d / 0<" % (i + 1), ">%d / %d<" % (i + 1, n))
        p = os.path.join(OUT, "bauplan-%d.svg" % (i + 1))
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(lk.svg_doc(297, 210, b))
        svgs.append(p)
    lk.svgs_to_pdf(svgs, os.path.join(OUT, "bauplan.pdf"))


def build_document(parts):
    doc = App.newDocument("Schneidlade")
    for n, k, s, c in parts:
        o = doc.addObject("Part::Feature", n.replace(" ", "_").replace("(", "").replace(")", ""))
        o.Shape = s
        o.Label = "%s %s" % (k, n)
    doc.recompute()
    doc.saveAs(os.path.join(OUT, "schneidlade.FCStd"))
    import Import
    Import.export(doc.Objects, os.path.join(OUT, "schneidlade.step"))


def main():
    os.makedirs(OUT, exist_ok=True)
    log("Schneidlade für Lernkasten, Karton t = %s mm" % fmt(T))
    ms = measures()
    log("  Anschlagmaße: " + ", ".join("%s (%s)" % (fmt(d), "/".join(u)) for d, u in ms.items()))
    parts = build()
    check(parts)
    plan = best_plan()
    log("  Schneidplan: %d Kästen je Bogen %s, %d Bodenstreifen, %d Wandstreifen à %s mm, "
        "Wandstreifen belegen %s von %s mm"
        % (plan["n"], lk.BOARD, len(plan["bstrips"]), len(plan["wstrips"]), fmt(plan["ru"]),
           fmt(plan["used_v"]), fmt(plan["Vv"])))
    # Stückzahlen im Plan prüfen
    walls, bottoms = pieces_per_box()
    got = {}
    for st in plan["bstrips"]:
        for _, k in st:
            got[k] = got.get(k, 0) + 1
    for _, st in plan["wstrips"]:
        for _, k in st:
            got[k] = got.get(k, 0) + 1
    exp = {}
    for _, _, k in walls + bottoms:
        exp[k] = exp.get(k, 0) + plan["n"]
    assert got == exp, (got, exp)
    log("  Teile im Schneidplan vollständig: OK")
    use_parts = build(cardboard=True, car_x=500)
    pages = [page_overview(parts), page_top(hole_positions()), page_section(), page_build(),
             page_use(use_parts)]
    pp, boards = page_plan(plan)
    pages.append(pp)
    log("  %d Bögen für die Serie" % boards)
    write_pdf(pages)
    build_document(parts)
    log("Fertig: " + OUT)


if not os.environ.get("_SCHNEIDLADE_RUNNING"):
    os.environ["_SCHNEIDLADE_RUNNING"] = "1"
    main()
