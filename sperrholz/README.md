# Lernkasten DIN A7 – NgarumaVTC

Leitner-Lernkasten für DIN-A7-Karteikarten (105 × 74 mm, quer stehend) mit fünf Fächern
aus 6 mm Sperrholz, gefertigt auf einer SCM-CNC.

- **Fräsen und Material:** M+M Fräsdienstleistungen, Kappeln
- **Schleifen und Verleimen:** Ngaruma, ohne CNC (siehe `build/montage.pdf`, Englisch und Kiswahili)
- **Serie:** 120 Kästen

## Maße

| | |
|---|---|
| Außenmaß | 386 × 121 × 65 mm |
| Lichte Breite | 109 mm (Karte 105 mm) |
| Fächer, lichte Länge | 25 / 40 / 60 / 90 / 135 mm (≈ 100 / 160 / 240 / 360 / 540 Karten) |
| Trennwände | 50 mm über dem Innenboden, Karten ragen 24 mm heraus |
| Boden | Unterkante 8 mm über dem Tisch |

## Teile pro Kasten

| | Teil | Stück | Maß (Hüllrechteck) |
|---|---|---|---|
| A | Seitenwand | 2 | 386 × 65 |
| B | Stirnwand (mit Griffmulde) | 2 | 121 × 65 |
| C | Boden | 1 | 386 × 121 |
| D | Trennwand (mit Griffmulde) | 4 | 121 × 56 |

Die Ecken sind mit Fingerzinken verbunden (5 Bänder). Boden und Trennwände stecken mit
durchgehenden Zapfen in Schlitzen. Alles sind Durchgangsschnitte, eine Aufspannung genügt.
Jede Innenecke hat einen Dogbone-Freistich (r = 3,05 mm für einen Fräser mit Ø 6 mm).
Die Teile richten sich beim Verleimen selbst rechtwinklig aus.

## Erzeugen

```sh
cd sperrholz
freecadcmd lernkasten.py        # ca. 1–2 min
```

Im Verzeichnis `sperrholz/` aufrufen: `freecadcmd` setzt nicht immer `__file__`,
dann landet die Ausgabe in `./build/` des aktuellen Verzeichnisses.

Die Parameter stehen oben in `lernkasten.py`. Das Skript prüft selbst, dass sich keine Teile
überschneiden, dass alle DXF-Konturen geschlossen sind und dass im Plattennest die Abstände
eingehalten werden. Schlägt eine Prüfung fehl, bricht es ab.

| Datei in `build/` | Inhalt |
|---|---|
| `lernkasten.FCStd` | FreeCAD: Zusammenbau, flache Teile, Parameter-Tabelle |
| `lernkasten.step` | Zusammenbau als STEP |
| `dxf/A_seitenwand.dxf` … | Einzelteile |
| `zuschnitt.dxf` / `.pdf` | ein Kastensatz |
| `platte.dxf` / `.pdf` | volle Platte 2500 × 1250 (16 Kästen) |
| `montage.pdf` | Montageanleitung Englisch / Kiswahili |

DXF: R12, Einheit mm. Layer `AUSSEN` für Außenkonturen, `INNEN` für Schlitze (zuerst fräsen),
`INFO` für Beschriftung und Plattenrand (nicht fräsen).

## Vor der Serie (Absprache mit M+M)

1. **Materialstärke messen.** „6 mm“ Birke-Multiplex misst oft 6,2 bis 6,5 mm. Das Messmaß
   in `T` eintragen und neu erzeugen. Alle Zapfen, Schlitze und Zinken passen sich an.
2. **Probekasten fräsen** und trocken zusammenstecken. Klemmt er, `C` (Spiel, jetzt 0,15 mm)
   erhöhen; ist er zu locker, verringern.
3. **Plattenformat** in `SHEET` an den Einkauf anpassen (z. B. 1525 × 1525 für Baltic Birch).
   Das Skript rechnet aus, wie viele Kästen auf eine Platte passen.
4. Kleine Teile (Trennwände 121 × 56 mm) brauchen auf dem Vakuumtisch eventuell
   Haltestege oder einen Onion-Skin-Schnitt.
5. Im Plattennest sind Teile teils um 90° gedreht. Soll die Faserrichtung einheitlich sein,
   im Aufruf `MaxRects.insert` `rot_ok=False` setzen. Dann passen weniger Kästen auf die Platte.

Bedarf bei 2500 × 1250: 16 Kästen pro Platte. 120 Kästen plus 5 % Ausschuss sind 126 Stück,
also **8 Platten**.

Die Kiswahili-Texte der Montageanleitung sollte jemand vor Ort gegenlesen.
