# Kikister — DIY Hitster voor Kiki

Een eigen Hitster-spel, met QR codes die je telefoon doorsturen naar Spotify zonder dat de titel/artiest in de preview verschijnt. Werkt zoals het echte spel: scannen, raden, omdraaien.

**Jouw site:** https://roschokm.github.io/hitster/
**Repo:** https://github.com/roschokm/hitster

## Hoe het werkt

1. Elke QR code wijst naar een korte, nietszeggende URL op jouw eigen site, bijvoorbeeld:
   `https://roschokm.github.io/hitster/?s=j3w`
2. De pagina kijkt naar de code `j3w`, zoekt het bijbehorende Spotify-nummer op in `songs.json`, en stuurt direct door naar Spotify.
3. De camera-preview laat alleen de korte URL zien — geen titel, geen artiest, geen plaatje. Pure puzzel.

## Setup

De repo `roschokm/hitster` bestaat al. Wat nog moet:

### Stap 1 — Upload de bestanden
Upload de inhoud van deze map naar de repo (via **Add file → Upload files** op github.com, of via GitHub Desktop / `git push`):
- `index.html` *(essentieel — de redirect-pagina)*
- `songs.json` *(essentieel — de songdatabase)*
- `README.md`
- `add_song.py` en `config.json` *(handig, maar mogen ook lokaal blijven)*
- `qr/` en `cards/` *(optioneel — afbeeldingen voor de speelkaartjes)*

### Stap 2 — Zet GitHub Pages aan
- Ga in de repo naar **Settings → Pages** (links in de zijbalk)
- Onder *Source*: kies **Deploy from a branch**
- Branch: **main**, folder: **/ (root)** → klik **Save**
- Wacht 1–2 minuten. Bovenaan verschijnt: *Your site is live at* `https://roschokm.github.io/hitster/`

### Stap 3 — Test
Scan de bestaande QR code in `qr/j3w_roxy_dekker_spijt.png`, of open in je browser:
```
https://roschokm.github.io/hitster/?s=j3w
```
Je moet doorgestuurd worden naar "Spijt" van Roxy Dekker in Spotify.

### Stap 4 — Script-config (alleen nodig op je computer)
De basis-URL is al ingesteld in `config.json` op `https://roschokm.github.io/hitster/`. Mocht je die ooit willen wijzigen:

```bash
python add_song.py --set-base-url https://roschokm.github.io/hitster/
```

## Nummers toevoegen

### Eén nummer
```bash
python add_song.py "Titel" "Artiest" 2024 https://open.spotify.com/track/0RHUZb0zXTARrtYjstHYcP
```

Het script doet drie dingen:
- voegt het nummer toe aan `songs.json`
- maakt een QR code in `qr/`
- maakt een voor- en achterkant van het speelkaartje in `cards/`

### Bulk via CSV
Maak een bestand `nummers.csv` met deze kolommen:
```csv
title,artist,year,spotify
Spijt,Roxy Dekker,2024,https://open.spotify.com/track/0RHUZb0zXTARrtYjstHYcP
Don't Stop Believin',Journey,1981,https://open.spotify.com/track/4bHsxqR3GMrXTxEPLuK5ue
```
Dan:
```bash
python add_song.py --csv nummers.csv
```

### Na elke wijziging
Upload de bijgewerkte `songs.json` (en eventueel nieuwe QR/kaart-afbeeldingen) opnieuw naar https://github.com/roschokm/hitster. Tip: installeer **GitHub Desktop** als je niet wilt slepen — dan synct hij automatisch.

## Spelregels (zoals echte Hitster)

- Eerste speler legt een willekeurig kaartje midden op tafel (jaartal-kant boven).
- Volgende speler trekt een kaart, scant de QR, luistert naar het nummer, en legt het kaartje *vóór* of *ná* de bestaande kaarten op de juiste plek in de tijdlijn.
- Draai om: klopt het jaartal? Ja → kaart blijft liggen. Nee → kaart gaat weg.
- Wie als eerste 10 kaarten correct op de tijdlijn heeft, wint.

## Privacy-tip

De repo `roschokm/hitster` is publiek, wat nodig is voor gratis GitHub Pages. Iemand die de URL googelt kan dus theoretisch in `songs.json` zien welke nummers in het spel zitten. Voor een familie-spel met Kiki maakt dat niets uit, maar als je dat liever afschermt zijn er twee opties:
- Hernoem de repo naar iets minder voor de hand liggends (bijv. `k-app` of een random naam)
- Gebruik Netlify Drop in plaats van GitHub Pages — die geeft je een willekeurige URL als `https://magical-cuchufli-12abc3.netlify.app`

## Bestanden in deze map

| Bestand | Wat het doet |
|---|---|
| `index.html` | De redirect-pagina (statisch, geen server nodig) |
| `songs.json` | Lijst van codes → Spotify track-ids |
| `config.json` | Bewaart jouw site-URL voor het script |
| `add_song.py` | Helper om nummers + QR codes + kaartjes te genereren |
| `qr/` | De gegenereerde QR codes (PNG) |
| `cards/` | Voor- en achterkanten van de speelkaartjes (PNG) |

## Veelgestelde vragen

**Werkt dit zonder internet?**
Nee — de QR code wijst naar je site, en de site stuurt door naar Spotify. Je hebt dus wifi/4G nodig tijdens het spelen. Wel kun je de Spotify-nummers offline beschikbaar maken in de Spotify-app (Premium).

**Wat als Spotify niet automatisch opent?**
De pagina probeert eerst `spotify:track:...` (app-link), en valt na ~1 seconde terug op `https://open.spotify.com/track/...` (web). Werkt op iPhone en Android.

**Kan ik een ander streaming-platform gebruiken?**
Ja — pas `index.html` aan om bijvoorbeeld naar YouTube Music of Apple Music te wijzen. De redirect-logica is in JavaScript van een paar regels.
