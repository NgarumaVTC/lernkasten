#!/bin/sh
# Baut build/lernkasten_anleitung.pdf aus lernkasten_anleitung.org.
# Fußzeile: Quelldatei | git-Hash des letzten Commits der Quelle, Datum | Seite x/y.
# Ein "+" hinter dem Hash heißt: Quelle hat uncommittete Änderungen.
set -e
cd "$(dirname "$0")"
SRC=lernkasten_anleitung.org
TMP=build/tmp
rm -rf "$TMP"; mkdir -p "$TMP"
cp "$SRC" "$TMP/"

HASH=$(git log -1 --format=%h -- "$SRC")
DATE=$(git log -1 --format=%cd --date=format:%d.%m.%Y -- "$SRC")
git diff --quiet HEAD -- "$SRC" || { HASH="$HASH+"; DATE=$(date +%d.%m.%Y); }
printf '\\newcommand\\githash{%s}\\newcommand\\gitdate{%s}\n' "$HASH" "$DATE" > "$TMP/gitinfo.tex"

(cd "$TMP" && emacs --batch "$SRC" -f org-latex-export-to-pdf >/dev/null 2>&1) \
  || { echo "Export fehlgeschlagen, siehe $TMP/*.log" >&2; exit 1; }
mv "$TMP/${SRC%.org}.pdf" build/
rm -rf "$TMP"
echo "build/${SRC%.org}.pdf ($HASH, $DATE)"
