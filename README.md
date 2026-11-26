# Lernkasten DIN A7 – NgarumaVTC

Leitner-Lernkasten für DIN-A7-Karteikarten (105 × 74 mm, quer stehend) mit fünf Fächern, Serie von 120 Stück.
Aus brauner Wellpappe, geklebt mit Weißleim (Holzleim) und Winkeln aus Kopierpapier (80 g/m², A4).
Die Winkel übertragen nur Zug und Schub, dafür reicht normales Papier.

## Aufbau

1. **Fünf Innenkästen**, oben offen, alle gleich breit und hoch, verschieden tief. Jeder Kasten hat einen Boden,
   2 Längsseiten (sie stehen auf dem Boden) und 2 Stirnwände (zwischen den Längsseiten).
   Die Kanten werden **außen** mit Papierwinkeln verklebt: 4 senkrechte Ecken und 4 Bodenkanten.
2. Die Innenkästen werden in einer Reihe **aneinandergeklebt**. Zwei Stirnwände nebeneinander ergeben die Trennwand.
3. Der **Außenkasten** hat keine Winkel. Er wird mit Weißleim in Streifen auf den Block geklebt, nicht vollflächig,
   damit die Pappe nicht durchfeuchtet: zuerst der Boden unter den Block, dann die Stirnwände an die Enden,
   zuletzt die Längsseiten über alles. Beim Trocknen beschweren.

So verdecken die Nachbarkästen und der Außenkasten die Papierwinkel weitgehend.
In allen Wänden laufen die Wellen **senkrecht**, von oben sieht man also in die Wellen. In den Böden laufen sie längs.

## Maße (t = 4 mm)

| | |
|---|---|
| Außenmaß | 398 × 125 × 50 mm |
| Lichte Breite / Höhe | 109 mm (Karte 105) / 42 mm, die Karte ragt 32 mm heraus |
| Fächer, lichte Länge | 25 / 40 / 60 / 90 / 135 mm (≈ 100 / 160 / 240 / 360 / 540 Karten) |
| Trennwände | 2 t = 8 mm |

## Teile pro Kasten (t = 4 mm; quer × längs der Welle)

| | Teil | Stück | Maß |
|---|---|---|---|
| A | Außen-Längsseite | 2 | 398 × 50 |
| E | Außen-Stirnwand | 2 | 117 × 50 |
| U | Außenboden | 1 | 117 × 390 |
| S | Stirnwand innen | 10 | 109 × 42 |
| L1–L5 | Längsseite Kasten n | je 2 | 33 / 48 / 68 / 98 / 143 × 42 |
| B1–B5 | Boden Kasten n | je 1 | 117 × 33 / 48 / 68 / 98 / 143 |
| K | Papierwinkel, Streifen 30 mm, mittig gefalzt | 40 | 4 × 46, 2 × Kastenlänge, 2 × 117 je Kasten |

## Erzeugen

```sh
freecadcmd lernkasten.py                  # ca. 10 s
LERNKASTEN_T=3 freecadcmd lernkasten.py   # andere Kartonstärke
```

Die Parameter stehen oben in `lernkasten.py`, darunter `T`, `H`, `FACH`, `ANGLE_LEG`, `BOARD` und `N_BOXES`.
Das Skript prüft selbst, dass sich keine Teile überschneiden, dass jedes Teil ein anderes berührt und dass der Hohlraum
genau den Fächern entspricht. Außerdem prüft es, ob alle DXF-Konturen geschlossen sind und ob das Nest Abstände und
Ränder einhält.

| Datei in `build/` | Inhalt |
|---|---|
| `lernkasten_anleitung.pdf` | Anleitung für die Schülerinnen (siehe unten) |
| `lernkasten.FCStd` / `.step` | Zusammenbau, Parameter-Tabelle |
| `dxf/<teil>.dxf` | Einzelteile (Layer `AUSSEN` schneiden, `INFO` = Wellenpfeil) |
| `zuschnitt.pdf` / `.dxf` | Teileliste, Satzskizze, Papierwinkel, Bedarf für die Serie |
| `bogen.pdf` / `.dxf` | Nest auf einem Wellpappbogen (`BOARD`, Wellen parallel zur zweiten Seite) |
| `montage.pdf` | Anleitung Englisch / Kiswahili / Deutsch mit Zuschnittliste |
| `schneidlade/bauplan.pdf` | Bauplan der Schneidlade, Schneidplan je Bogen (siehe unten) |
| `schneidlade/schneidlade.FCStd` / `.step` | Modell der Schneidlade |

Im Nest werden die Teile nicht gedreht, damit die Wellenrichtung stimmt. Bei 1200 × 800 passen 3 Kästen auf einen Bogen.
Für 120 Kästen plus 5 % Ausschuss sind das **42 Bögen**. Dazu kommen etwa 1,6 Blatt Kopierpapier A4 je Kasten (knapp 200 Blatt für die Serie).

## Vor der Serie

1. **Kartonstärke nachmessen** (angesetzt sind 4 mm) und bei Abweichung `T` ändern, dann neu erzeugen. Alle Maße passen sich an.
2. **Probekasten** bauen. Passt die Karte in der Breite nicht leicht hinein, `PLAY_W` erhöhen.
3. `BOARD` an das Bogenformat anpassen, das man tatsächlich bekommt.

Die Kiswahili-Texte der Montageanleitung und des Bauplans sollte jemand vor Ort gegenlesen.

## Schneidlade

Die Tischlerlehrlinge in Ngaruma bauen unter Anleitung ihres Meisters eine Schneidvorrichtung aus Holz und
schneiden damit die Kartons für ihre Mitschüler. Geklebt wird nach `montage.pdf`.

```sh
freecadcmd schneidlade.py                 # ca. 20 s, nimmt T usw. aus lernkasten.py
```

Aufbau: Auf einer Grundplatte (Sperrholz 18 mm) liegt eine Hartholzschiene. Sie ist links drehbar gelagert
und fällt rechts in eine Fanggabel. Auf der Schiene läuft ein Schlitten mit einer 18-mm-Abbrechklinge unter
45°, die in eine austauschbare Opferleiste taucht. Hinter der Schnittlinie liegt eine Anschlagleiste. Zwei
Steckstifte halten sie, und für jedes Anschlagmaß gibt es ein eigenes Lochpaar. So muss beim Schneiden
niemand messen. Ein Seitenanschlag sorgt für rechtwinklige Ablängschnitte.

Alle Teile sind Rechtecke, also wird in zwei Gängen geschnitten: erst Streifen vom Bogen, dann Ablängen.
Die Anschlagmaße ergeben sich aus den Teilemaßen, bei t = 4 mm sind es 33, 42, 48, 50, 68, 98, 109, 117,
143, 390 und 398 mm. Der Schneidplan ist ein reiner Streifenplan, damit jeder Schnitt durchgeht. Bei
1200 × 800 ergibt er wie das Nest 3 Kästen je Bogen.

Das Skript prüft:

- dass sich keine Teile überschneiden
- dass die Klinge durch den Karton bis in die Opferleiste reicht, aber nicht in die Grundplatte
- den Klingenweg über die ganze Schnittlänge `CUT_MAX`
- die Lochabstände
- dass der Schneidplan alle Teile enthält

Der Bauplan hat 6 Seiten im Querformat A4, auf Englisch, Kiswahili und Deutsch:

1. Holzliste und Beschläge
2. Draufsicht mit Lochtabelle
3. Schlitten im Maßstab 1 : 1
4. Bau
5. Bedienung
6. Schneidplan

Die Löcher werden erst nach einem Probeschnitt angerissen, und zwar von der echten Schnittlinie aus.
Klingen (Abbrechklingen 18 mm) bringen wir aus Deutschland mit.

## Anleitung für die Schülerinnen

[`lernkasten_anleitung.org`](lernkasten_anleitung.org): wie man mit dem Lernkasten lernt (Leitner-Prinzip, Lernplan, Blankokarten im Unterricht, offene Fragen klären), in einfacher Sprache ab Klasse 5. PDF in [`build/lernkasten_anleitung.pdf`](build/lernkasten_anleitung.pdf), gebaut mit `./build_anleitung.sh`.

## Lernkarten

[`karten/`](karten/README.md): Lernkarten DIN A7 doppelseitig auf A4 zum Ausschneiden, Inhalt als Anki-Textdatei. Dabei 40 Karten zum Leitner-Prinzip und ein Bogen Blankokarten.
