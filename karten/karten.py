#!/usr/bin/env python3
"""Lernkarten DIN A7 auf DIN A4, doppelseitig, zum Ausschneiden.

Eingabe ist eine Anki-Textdatei (Basic: Vorderseite, Rückseite, Tags; Tab-getrennt,
HTML erlaubt: <br>, <b>, <i>). Sie lässt sich unverändert in Anki importieren.

Je A4-Blatt 8 Karten (2 Spalten × 4 Reihen à 105 × 74 mm, ohne Rand). Ungerade
Seiten tragen die Fragen und die Schneidlinien, gerade Seiten die Antworten,
links/rechts gespiegelt für Duplexdruck über die lange Kante. Jede Karte hat
einen eigenen Rahmen, 7 mm vom Kartenrand, damit er auch bei Druckerrand und
schiefem Schnitt vollständig bleibt.

    ./karten.py                    # leitner.txt -> build/leitner.pdf
    ./karten.py datei.txt          # datei.txt   -> build/datei.pdf
    ./karten.py --blanko 1         # zusätzlich build/blanko.pdf, 1 Blatt leere Karten

Drucken: A4, tatsächliche Größe (100 %, nicht „an Seite anpassen“), beidseitig,
lange Kante.
"""

import argparse
import datetime
import html
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

CARD_W, CARD_H = 105.0, 74.0     # DIN A7 quer, mm
COLS, ROWS = 2, 4                # 2 × 105 = 210, 4 × 74 = 296 (A4: 210 × 297)
PAGE_W, PAGE_H = 210.0, 297.0
FRAME = 7.0                      # Rahmen-Abstand vom Kartenrand
PAD = 4.0                        # Text-Abstand vom Rahmen
LABEL = 6.0                      # Kopfzeile in der Karte (Tag, Nummer)
FOOT_Y = 5.0                     # Fußzeile des Bogens, Abstand Papierkante
SIZES = "20,18,16,14,13,12,11,10,9,8"  # Schriftgrößen in pt, größte zuerst

PREAMBLE = r"""\documentclass{article}
\usepackage[paperwidth=210mm,paperheight=297mm,margin=0mm]{geometry}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[ngerman]{babel}
\usepackage{lmodern}
\usepackage{tikz}
\pagestyle{empty}
\setlength{\parindent}{0pt}
\newsavebox\cardbox
\newlength\cardtextw
\newlength\cardtexth
\newif\iffitdone
\makeatletter
%% #1 Breite, #2 Höhe, #3 Text: größte Schrift aus \fitsizes, die passt
\newcommand\fittext[3]{%
  \setlength\cardtextw{#1}\setlength\cardtexth{#2}\fitdonefalse
  \@for\fit@s:=\fitsizes\do{%
    \iffitdone\else
      \sbox\cardbox{\parbox{\cardtextw}{\centering
        \fontsize{\fit@s}{\fpeval{1.25*\fit@s}}\selectfont #3\par}}%
      \ifdim\dimexpr\ht\cardbox+\dp\cardbox\relax>\cardtexth\else\fitdonetrue\fi
    \fi}%
  \iffitdone\else\PackageWarning{karten}{Text passt nicht auf die Karte}\fi
  \usebox\cardbox}
\makeatother
"""


def log(msg):
    print(msg, file=sys.stderr)


def tex_escape(s):
    rep = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#",
           "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
           "^": r"\textasciicircum{}"}
    return "".join(rep.get(c, c) for c in s)


def html_to_tex(s):
    """Anki-HTML (nur <br>, <b>, <i>, Entities) nach LaTeX."""
    out = []
    for part in re.split(r"(<[^>]+>)", s):
        tag = part.lower().replace(" ", "")
        if tag in ("<br>", "<br/>"):
            out.append(r"\\")
        elif tag in ("<b>", "<strong>"):
            out.append(r"\textbf{")
        elif tag in ("<i>", "<em>"):
            out.append(r"\emph{")
        elif tag in ("</b>", "</strong>", "</i>", "</em>"):
            out.append("}")
        elif tag.startswith("<"):
            raise ValueError("HTML-Tag nicht unterstützt: %s" % part)
        else:
            out.append(tex_escape(html.unescape(part)))
    return "".join(out)


def read_anki(path):
    """Liefert [(vorne, hinten, tags)] aus einer Anki-Textdatei."""
    sep, tag_col, cards = "\t", None, []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.rstrip("\n")
            if line.startswith("#"):
                key, _, val = line[1:].partition(":")
                if key == "separator":
                    sep = {"tab": "\t", "comma": ",", "semicolon": ";"}.get(val, val)
                elif key == "tags column":
                    tag_col = int(val) - 1
                continue
            if not line.strip():
                continue
            f_ = line.split(sep)
            if len(f_) < 2:
                raise ValueError("%s:%d: weniger als zwei Felder" % (path, n))
            tags = f_[tag_col] if tag_col is not None and tag_col < len(f_) else ""
            cards.append((f_[0], f_[1], tags))
    return cards


def git_info(path):
    """Kurz-Hash und Datum des letzten Commits der Datei, '+' bei Änderungen."""
    rel = os.path.relpath(path, HERE)

    def git(*a):
        return subprocess.run(("git",) + a, cwd=HERE, capture_output=True,
                              text=True).stdout.strip()
    h = git("log", "-1", "--format=%h", "--", rel)
    d = git("log", "-1", "--format=%cd", "--date=format:%d.%m.%Y", "--", rel)
    dirty = subprocess.run(("git", "diff", "--quiet", "HEAD", "--", rel), cwd=HERE).returncode
    if not h:
        return "ohne git", datetime.date.today().strftime("%d.%m.%Y")
    if dirty:
        return h + "+", datetime.date.today().strftime("%d.%m.%Y")
    return h, d


def card_origin(i, back):
    """Linke untere Ecke von Karte i (0..7) auf dem Bogen, in mm."""
    col, row = i % COLS, i // COLS
    if back:
        col = COLS - 1 - col
    return col * CARD_W, PAGE_H - (row + 1) * CARD_H


def card_tex(x, y, text, left, right):
    tw = CARD_W - 2 * (FRAME + PAD)
    th = CARD_H - 2 * (FRAME + PAD) - LABEL
    cx = x + CARD_W / 2
    cy = y + FRAME + PAD + th / 2
    s = [r"\draw[line width=0.6pt, rounded corners=2mm] (%.2fmm,%.2fmm) rectangle (%.2fmm,%.2fmm);"
         % (x + FRAME, y + FRAME, x + CARD_W - FRAME, y + CARD_H - FRAME)]
    ly = y + CARD_H - FRAME - PAD / 2
    if left:
        s.append(r"\node[anchor=north west, inner sep=0pt, text=black!55, font=\fontsize{7}{8}\selectfont]"
                 r" at (%.2fmm,%.2fmm) {%s};" % (x + FRAME + PAD / 2, ly, left))
    if right:
        s.append(r"\node[anchor=north east, inner sep=0pt, text=black!55, font=\fontsize{7}{8}\selectfont]"
                 r" at (%.2fmm,%.2fmm) {%s};" % (x + CARD_W - FRAME - PAD / 2, ly, right))
    if text:
        s.append(r"\node[inner sep=0pt] at (%.2fmm,%.2fmm) {\fittext{%.2fmm}{%.2fmm}{%s}};"
                 % (cx, cy, tw, th, text))
    return s


def page_tex(cards, back, cutlines, foot):
    s = [r"\begin{tikzpicture}[remember picture, overlay, shift={(current page.south west)}]"]
    if cutlines:
        for c in range(COLS + 1):
            s.append(r"\draw[black!40, line width=0.2pt] (%.2fmm,0) -- (%.2fmm,%.2fmm);"
                     % (c * CARD_W, c * CARD_W, PAGE_H))
        for r in range(ROWS + 1):
            yy = PAGE_H - r * CARD_H
            s.append(r"\draw[black!40, line width=0.2pt] (0,%.2fmm) -- (%.2fmm,%.2fmm);"
                     % (yy, PAGE_W, yy))
    for i, (text, left, right) in enumerate(cards):
        x, y = card_origin(i, back)
        s += card_tex(x, y, text, left, right)
    fl, fc, fr = foot
    style = r"inner sep=0pt, text=black!45, font=\ttfamily\fontsize{5}{6}\selectfont"
    s.append(r"\node[anchor=base west, %s] at (%.2fmm,%.2fmm) {%s};"
             % (style, FRAME + PAD / 2, FOOT_Y, fl))
    s.append(r"\node[anchor=base, %s] at (%.2fmm,%.2fmm) {%s};" % (style, PAGE_W / 2, FOOT_Y, fc))
    s.append(r"\node[anchor=base east, %s] at (%.2fmm,%.2fmm) {%s};"
             % (style.replace(r"\ttfamily", ""), PAGE_W - FRAME - PAD / 2, FOOT_Y, fr))
    s.append(r"\end{tikzpicture}")
    s.append(r"\null\newpage")
    return "\n".join(s)


def build(sheets, src, out_pdf):
    """sheets: Liste von (vorderseiten, rückseiten), je bis zu 8 (text, links, rechts)."""
    h, d = git_info(src)
    name = tex_escape(os.path.relpath(src, os.path.dirname(HERE)))
    n_pages = 2 * len(sheets)
    body = []
    for k, (front, back) in enumerate(sheets):
        for side, cards in ((0, front), (1, back)):
            p = 2 * k + side + 1
            foot = (name, "%s, %s" % (tex_escape(h), d), "Seite %d/%d" % (p, n_pages))
            body.append(page_tex(cards, side == 1, side == 0, foot))
    tex = (PREAMBLE + "\\newcommand\\fitsizes{%s}\n\\begin{document}\n%s\n\\end{document}\n"
           % (SIZES, "\n".join(body)))

    tmp = tempfile.mkdtemp(prefix="karten-")
    try:
        with open(os.path.join(tmp, "k.tex"), "w", encoding="utf-8") as f:
            f.write(tex)
        for _ in range(2):  # remember picture braucht zwei Läufe
            r = subprocess.run(["pdflatex", "-interaction=nonstopmode", "-halt-on-error", "k.tex"],
                               cwd=tmp, capture_output=True, text=True)
            if r.returncode:
                sys.exit(r.stdout[-3000:])
        warn = re.findall(r"Package karten Warning: .*", open(os.path.join(tmp, "k.log")).read())
        if warn:
            log("  WARNUNG: %d Karte(n) mit zu viel Text (kleinste Schrift reicht nicht)" % len(warn))
        os.makedirs(os.path.dirname(out_pdf), exist_ok=True)
        shutil.copy(os.path.join(tmp, "k.pdf"), out_pdf)
    finally:
        shutil.rmtree(tmp)
    log("%s: %d Bögen, %d Seiten (%s, %s)" % (os.path.relpath(out_pdf), len(sheets), n_pages, h, d))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("anki", nargs="?", default=os.path.join(HERE, "leitner.txt"))
    ap.add_argument("--blanko", type=int, default=0, metavar="N",
                    help="zusätzlich N Bögen leere Karten nach build/blanko.pdf")
    a = ap.parse_args()

    src = os.path.abspath(a.anki)
    cards = read_anki(src)
    per = COLS * ROWS
    sheets = []
    for k in range(0, len(cards), per):
        front, back = [], []
        for j, (q, ans, tags) in enumerate(cards[k:k + per]):
            nr = "Nr.~%d" % (k + j + 1)
            tag = tex_escape(tags.replace("::", " · ").strip())
            front.append((html_to_tex(q), tag, nr))
            back.append((html_to_tex(ans), tag, nr))
        sheets.append((front, back))
    base = os.path.splitext(os.path.basename(src))[0]
    build(sheets, src, os.path.join(HERE, "build", base + ".pdf"))

    if a.blanko:
        empty = [("", "", "")] * per
        build([(empty, empty)] * a.blanko, os.path.abspath(__file__),
              os.path.join(HERE, "build", "blanko.pdf"))


if __name__ == "__main__":
    main()
