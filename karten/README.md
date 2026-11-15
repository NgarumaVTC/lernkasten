# Lernkarten DIN A7 zum Ausschneiden

`karten.py` setzt Lernkarten im Format DIN A7 (105 × 74 mm, quer) auf DIN-A4-Bögen,
doppelseitig: 8 Karten je Blatt, Vorderseite Frage, Rückseite Antwort.

| Datei | Inhalt |
|---|---|
| [`leitner.txt`](leitner.txt) | 40 Karten zum Leitner-Prinzip, nach [`../lernkasten_anleitung.org`](../lernkasten_anleitung.org) |
| [`build/leitner.pdf`](build/leitner.pdf) | 5 Bögen, 10 Seiten |
| [`build/blanko.pdf`](build/blanko.pdf) | 1 Bogen leere Karten (Rahmen, Schneidlinien) |

## Zwischenformat: Anki

Die Kartentexte stehen als Anki-Textdatei (Notiztyp *Basic*, Tab-getrennt:
Vorderseite, Rückseite, Tags). Sie lässt sich unverändert in Anki importieren
(*Datei → Importieren*), landet dort im Stapel `Lernkasten::Leitner-Prinzip`.
Erlaubtes HTML: `<br>`, `<b>`, `<i>`.

Eigene Karten: neue Datei im selben Format anlegen und `./karten.py datei.txt`
aufrufen, Ausgabe `build/datei.pdf`. Die Schriftgröße passt sich an (20 pt bis
8 pt); passt ein Text auch in 8 pt nicht, warnt das Skript.

## Bauen

    ./karten.py --blanko 1

Braucht Python 3 und pdflatex mit `lmodern`, `tikz`, `babel`.
Fußzeile jedes Bogens: Quelldatei | git-Hash und Datum des letzten Commits der
Quelle (`+` bei uncommitteten Änderungen) | Seite x/y. Sie steht im Randstreifen
der unteren Kartenreihe, außerhalb der Kartenrahmen.

## Drucken und Schneiden

- A4, **tatsächliche Größe** (100 %), nicht „an Seite anpassen“.
- **Beidseitig, Spiegelung an der langen Kante.** Die Rückseiten sind dafür links/rechts
  vertauscht. Erst einen Bogen probedrucken und gegen das Licht halten.
- Die Karten füllen das Blatt ohne Rand. Schneidlinien (grau) nur auf der
  Vorderseite: eine senkrechte, drei waagerechte. Die äußeren Linien fallen in den
  Druckerrand, dort ist die Papierkante der Schnitt. Es bleibt 1 mm Abfall an der
  Unterkante (4 × 74 = 296 mm).
- Jede Karte hat einen eigenen Rahmen 7 mm innerhalb der Schnittkante, so bleibt
  er bei Druckerrand und leichtem Versatz der Rückseite vollständig.
- Nummer oben rechts auf beiden Seiten: zum Prüfen, ob Vorder- und Rückseite
  zusammenpassen.
- Papier: 160–200 g/m² gehen durch die meisten Drucker und sind steif genug für
  den Kasten.
