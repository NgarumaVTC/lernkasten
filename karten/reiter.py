#!/usr/bin/env python3
"""Fünf Reiterkarten 1–5 für die mobile Lernbox, auf einem A4-Bogen, einseitig.

Körper DIN A7 quer (105 × 74 mm), darüber ein 10 mm hoher Reiter. Die fünf Reiter
teilen sich die lange Seite lückenlos (je 21 mm), ihre Flanken sind schräg und
ausgerundet. Gesamthöhe 84 mm, die Box fasst 88 mm.

Auf dem Bogen liegen links drei Karten quer, rechts zwei um 90° gedreht. Jede hat
ihren vollständigen Umriss, Abstand zur Nachbarkarte und zum Papierrand.

    ./reiter.py                    # -> build/reiter.pdf

Drucken: A4, tatsächliche Größe (100 %), einseitig.
"""

import math
import os
import shutil
import subprocess
import sys
import tempfile

from karten import CARD_H, CARD_W, HERE, PAGE_H, PAGE_W, PREAMBLE, git_info, tex_escape

TAB_H = 10.0                     # Reiterhöhe
TAB_N = 5
TAB_W = CARD_W / TAB_N           # 21 mm
FULL_H = CARD_H + TAB_H          # 84 mm
TAB_SLANT = 2.5                  # Flanke: Versatz oben gegenüber dem Reiterfuß
TAB_R = 2.0                      # Radius der Ausrundungen am Reiter
GAP = 4.0                        # Abstand zwischen den Karten
MARGIN = (PAGE_W - CARD_W - GAP - FULL_H) / 2   # Rand links und rechts, 8,5 mm
DIGIT_PT = 28
FOOT_Y = 8.0
CUT = r"\draw[black!55, line width=0.25pt]"


def outline(i):
    """Umriss von Karte i in Kartenkoordinaten: [(x, y, ausgerundet)], gegen den Uhrzeigersinn."""
    a, b = i * TAB_W, (i + 1) * TAB_W
    top = CARD_H
    pts = [(0, 0, False), (CARD_W, 0, False)]
    if i < TAB_N - 1:
        pts.append((CARD_W, top, False))
    pts += [(b, top, True), (b - TAB_SLANT, top + TAB_H, True),
            (a + TAB_SLANT, top + TAB_H, True), (a, top, True)]
    if i > 0:
        pts.append((0, top, False))
    return pts


def path_tex(pts, place):
    """TikZ-Pfad; ausgerundete Ecken als Kreisbogen (kubische Bézierkurve)."""
    def P(x, y):
        return "(%.3fmm,%.3fmm)" % place(x, y)

    s = P(pts[0][0], pts[0][1])
    for k in range(1, len(pts)):
        x0, y0, _ = pts[k - 1]
        x1, y1, rounded = pts[k]
        x2, y2, _ = pts[(k + 1) % len(pts)]
        if not rounded:
            s += " -- " + P(x1, y1)
            continue
        l0, l2 = math.hypot(x0 - x1, y0 - y1), math.hypot(x2 - x1, y2 - y1)
        ux, uy = (x0 - x1) / l0, (y0 - y1) / l0
        vx, vy = (x2 - x1) / l2, (y2 - y1) / l2
        alpha = math.acos(ux * vx + uy * vy)
        d = TAB_R / math.tan(alpha / 2)
        h = 4 / 3 * math.tan((math.pi - alpha) / 4) * TAB_R
        s += " -- %s .. controls %s and %s .. %s" % (
            P(x1 + ux * d, y1 + uy * d), P(x1 + ux * (d - h), y1 + uy * (d - h)),
            P(x1 + vx * (d - h), y1 + vy * (d - h)), P(x1 + vx * d, y1 + vy * d))
    return s + " -- cycle"


def placement(i):
    """Abbildung Kartenkoordinaten -> Bogen und Drehwinkel der Ziffer."""
    if i < 3:                                 # links, quer, Reiter oben
        y0 = (PAGE_H - 3 * FULL_H - 2 * GAP) / 2 + (2 - i) * (FULL_H + GAP)
        return (lambda x, y: (MARGIN + x, y0 + y)), 0
    x0 = MARGIN + CARD_W + GAP                # rechts, 90° gedreht, Reiter nach rechts
    y0 = (PAGE_H - 2 * CARD_W - GAP) / 2 + (4 - i) * (CARD_W + GAP)
    return (lambda x, y: (x0 + y, y0 + CARD_W - x)), -90


def card_tex(i):
    """Karte i (0..4): Umriss als Schnittlinie und Ziffer im Reiter."""
    place, angle = placement(i)
    cx, cy = place((i + 0.5) * TAB_W, CARD_H + TAB_H / 2)
    return [CUT + " %s;" % path_tex(outline(i), place),
            r"\node[inner sep=0pt, rotate=%d, font=\fontsize{%d}{%d}\selectfont] at (%.3fmm,%.3fmm) {%d};"
            % (angle, DIGIT_PT, DIGIT_PT, cx, cy, i + 1)]


def main():
    src = os.path.abspath(__file__)
    h, d = git_info(src)
    s = [r"\begin{tikzpicture}[remember picture, overlay, shift={(current page.south west)}]"]
    for i in range(TAB_N):
        s += card_tex(i)
    style = r"inner sep=0pt, text=black!45, font=\ttfamily\fontsize{5}{6}\selectfont"
    s.append(r"\node[anchor=base west, %s] at (%.2fmm,%.2fmm) {karten/reiter.py};"
             % (style, MARGIN, FOOT_Y))
    s.append(r"\node[anchor=base, %s] at (%.2fmm,%.2fmm) {%s, %s};"
             % (style, PAGE_W / 2, FOOT_Y, tex_escape(h), d))
    s.append(r"\end{tikzpicture}\null")
    tex = PREAMBLE + "\\begin{document}\n%s\n\\end{document}\n" % "\n".join(s)

    out = os.path.join(HERE, "build", "reiter.pdf")
    tmp = tempfile.mkdtemp(prefix="reiter-")
    try:
        with open(os.path.join(tmp, "r.tex"), "w", encoding="utf-8") as f:
            f.write(tex)
        for _ in range(2):  # remember picture braucht zwei Läufe
            r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "r.tex"],
                               cwd=tmp, capture_output=True, text=True)
            if r.returncode:
                sys.exit(r.stdout[-3000:])
        shutil.copy(os.path.join(tmp, "r.pdf"), out)
    finally:
        shutil.rmtree(tmp)
    print("%s: %d Reiter, %.0f × %.0f mm" % (os.path.relpath(out), TAB_N, CARD_W, FULL_H),
          file=sys.stderr)


if __name__ == "__main__":
    main()
