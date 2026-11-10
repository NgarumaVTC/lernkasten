# Lernkasten DIN A7 aus Wellpappe – NgarumaVTC

Leitner-Lernkasten für DIN-A7-Karteikarten (105 × 74 mm, quer stehend) mit fünf Fächern aus
brauner Wellpappe, geklebt mit Sprühkleber und Winkeln aus Karteikartenpapier (KKP 205 g).

## Aufbau

1. **Fünf Innenkästen**, oben offen, alle gleich breit und hoch, verschieden tief. Jeder Kasten hat einen Boden,
   2 Längsseiten (sie stehen auf dem Boden) und 2 Stirnwände (zwischen den Längsseiten).
   Die Kanten werden **außen** mit KKP-Winkeln verklebt: 4 senkrechte Ecken und 4 Bodenkanten.
2. Die Innenkästen werden in einer Reihe **aneinandergeklebt**. Zwei Stirnwände nebeneinander ergeben die Trennwand.
3. Der **Außenkasten** hat keine Winkel. Er wird flächig auf den Block gesprüht, zuerst der Boden unter den Block,
   dann die Stirnwände an die Enden, zuletzt die Längsseiten über alles.

So verdecken die Nachbarkästen und der Außenkasten die KKP-Winkel weitgehend.
In allen Wänden laufen die Wellen **senkrecht**, von oben sieht man also in die Wellen. In den Böden laufen sie längs.

## Maße (t = 3 mm)

| | |
|---|---|
| Außenmaß | 386 × 121 × 50 mm |
| Lichte Breite / Höhe | 109 mm (Karte 105) / 44 mm, die Karte ragt 30 mm heraus |
| Fächer, lichte Länge | 25 / 40 / 60 / 90 / 135 mm (≈ 100 / 160 / 240 / 360 / 540 Karten) |
| Trennwände | 2 t = 6 mm |

## Teile pro Kasten (t = 3 mm; quer × längs der Welle)

| | Teil | Stück | Maß |
|---|---|---|---|
| A | Außen-Längsseite | 2 | 386 × 50 |
| E | Außen-Stirnwand | 2 | 115 × 50 |
| U | Außenboden | 1 | 115 × 380 |
| S | Stirnwand innen | 10 | 109 × 44 |
| L1–L5 | Längsseite Kasten n | je 2 | 31 / 46 / 66 / 96 / 141 × 44 |
| B1–B5 | Boden Kasten n | je 1 | 115 × 31 / 46 / 66 / 96 / 141 |
| K | KKP-Winkel, Streifen 30 mm, mittig gefalzt | 40 | 4 × 47, 2 × Kastenlänge, 2 × 115 je Kasten |

## Erzeugen

```sh
cd karton
freecadcmd lernkasten.py                  # ca. 10 s
LERNKASTEN_T=4 freecadcmd lernkasten.py   # andere Kartonstärke
```

Die Parameter stehen oben in `lernkasten.py`, darunter `T`, `H`, `FACH`, `ANGLE_LEG`, `BOARD` und `N_BOXES`.
Das Skript prüft selbst, dass sich keine Teile überschneiden, dass jedes Teil ein anderes berührt und dass der Hohlraum
genau den Fächern entspricht. Außerdem prüft es, ob alle DXF-Konturen geschlossen sind und ob das Nest Abstände und
Ränder einhält.

| Datei in `build/` | Inhalt |
|---|---|
| `lernkasten.FCStd` / `.step` | Zusammenbau, Parameter-Tabelle |
| `dxf/<teil>.dxf` | Einzelteile (Layer `AUSSEN` schneiden, `INFO` = Wellenpfeil) |
| `zuschnitt.pdf` / `.dxf` | Teileliste, Satzskizze, KKP-Winkel, Bedarf für die Serie |
| `bogen.pdf` / `.dxf` | Nest auf einem Wellpappbogen (`BOARD`, Wellen parallel zur zweiten Seite) |
| `montage.pdf` | Anleitung Englisch / Kiswahili mit Zuschnittliste |

Im Nest werden die Teile nicht gedreht, damit die Wellenrichtung stimmt. Bei 1200 × 800 passen 3 Kästen auf einen Bogen.
Für 120 Kästen plus 5 % Ausschuss sind das **42 Bögen**. Dazu kommen etwa 1,4 Bogen KKP A4 je Kasten.

## Vor der Serie

1. **Kartonstärke messen** und in `T` eintragen, dann neu erzeugen. Alle Maße passen sich an.
2. **Probekasten** bauen. Passt die Karte in der Breite nicht leicht hinein, `PLAY_W` erhöhen.
3. `BOARD` an das Bogenformat anpassen, das man tatsächlich bekommt.

Die Kiswahili-Texte der Montageanleitung sollte jemand vor Ort gegenlesen.
