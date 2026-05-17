#!/usr/bin/env python3
"""
Voeg een nummer toe aan de Kikister-database en genereer:
  - QR code met de redirect-URL (kort, geen verraderlijke preview)
  - Speelkaartje voorkant (alleen QR + "KIKISTER")
  - Speelkaartje achterkant (jaar, titel, artiest)

Gebruik:
  # 1) Configureer eenmalig de basis-URL waarop jouw site draait:
  python add_song.py --set-base-url https://JOUWNAAM.github.io/kikister/

  # 2) Voeg een nummer toe (Spotify-URL of track-id mag):
  python add_song.py "Spijt" "Roxy Dekker" 2024 https://open.spotify.com/track/0RHUZb0zXTARrtYjstHYcP

  # 3) Bulk vanuit CSV (kolommen: title,artist,year,spotify):
  python add_song.py --csv nummers.csv
"""
from __future__ import annotations
import argparse, csv, json, os, random, re, string, sys
from pathlib import Path

try:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    sys.exit("Installeer eerst: pip install qrcode[pil] pillow")

ROOT = Path(__file__).parent.resolve()
SONGS_PATH = ROOT / "songs.json"
CONFIG_PATH = ROOT / "config.json"
QR_DIR = ROOT / "qr"
CARDS_DIR = ROOT / "cards"
QR_DIR.mkdir(exist_ok=True)
CARDS_DIR.mkdir(exist_ok=True)


def load_json(p: Path, default):
    if not p.exists(): return default
    return json.loads(p.read_text())

def save_json(p: Path, data):
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False))

def extract_track_id(s: str) -> str:
    s = s.strip()
    m = re.search(r"track[/:]([A-Za-z0-9]+)", s)
    if m: return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9]{22}", s): return s
    raise ValueError(f"Kan track-id niet vinden in: {s}")

def short_code(existing: set, n=3) -> str:
    alphabet = string.ascii_lowercase + string.digits
    while True:
        c = "".join(random.choices(alphabet, k=n))
        if c not in existing: return c

# === Kikister kleurpalet (zelfde als index.html) ===
PAARS       = "#6e3bb3"
BLAUW       = "#2da6df"
GROEN       = "#56b948"
GROEN_DK    = "#1b4d10"
ROOD        = "#dc2828"
ROOD_DK     = "#6e0e0e"
GEEL        = "#f0c800"
ORANJE      = "#f06430"
CYAAN       = "#39c5d8"
ROZE        = "#d8327a"
DBLAUW      = "#1f3da8"
PAPIER      = "#fdfaf0"

def get_font(size: int, bold=True):
    """Chunky display-font voor de kid-style look."""
    candidates_bold = [
        "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    candidates_reg = [
        "/usr/share/fonts/truetype/google-fonts/Poppins-Medium.ttf",
        "/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for c in (candidates_bold if bold else candidates_reg):
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()

def draw_marker_text(d, xy, text, fill, font, anchor="mm", outline=None, offset=3):
    """Tekent tekst met een 'marker'-outline: donkere kopie iets onder, dan felle kleur er over."""
    if outline:
        d.text((xy[0]+offset, xy[1]+offset), text, fill=outline, font=font, anchor=anchor)
    d.text(xy, text, fill=fill, font=font, anchor=anchor)

def fit_font(text, max_width: int, max_size: int, min_size: int = 22, bold: bool = True):
    """Vind de grootste font-size waarbij `text` in `max_width` past."""
    for size in range(max_size, min_size - 1, -2):
        f = get_font(size, bold=bold)
        try:
            w = f.getlength(text) if hasattr(f, "getlength") else f.getsize(text)[0]
        except Exception:
            w = max_width + 1
        if w <= max_width:
            return f
    return get_font(min_size, bold=bold)

def draw_notebook_bg(img):
    """Geef de achtergrond de 'schoolschrift'-lijntjes."""
    W, H = img.size
    d = ImageDraw.Draw(img)
    line_color = "#c5dff0"
    for y in range(60, H, 70):
        d.line([(0, y), (W, y)], fill=line_color, width=2)

# === Geschilderde kleurblob-achtergrond, geïnspireerd op Kiki's tekening ===
# Per blob: (kleur, lijst van (x,y) punten in 1200x1200 coords).
# De volgorde bepaalt welk vlak bovenop ligt.
PAINTED_BLOBS = [
    # paarse hoek linksboven
    (PAARS, [(0,0),(460,0),(440,60),(400,140),(330,180),(220,210),(80,200),(0,180)]),
    # blauw breed bovenstuk rechts
    (BLAUW, [(420,0),(1200,0),(1200,360),(1100,340),(980,380),(820,340),(700,400),(560,330),(420,360),(380,140)]),
    # rode brede band onder header (vlak waar 4+ op valt)
    (ROOD,  [(0,200),(220,260),(440,230),(660,280),(900,250),(1100,300),(1200,260),(1200,420),(0,440)]),
    # cyaan blob links voor 'Kids'
    (CYAAN, [(30,360),(220,340),(380,430),(420,540),(300,610),(120,600),(40,520),(0,440)]),
    # groene blob rechts voor 'Bij'
    (GROEN, [(600,380),(900,370),(1100,420),(1160,520),(1000,580),(820,560),(680,520),(620,460)]),
    # paars blob midden
    (PAARS, [(380,540),(600,560),(800,640),(770,760),(580,780),(420,720),(360,640)]),
    # groen blob links-onder (achter KIKI)
    (GROEN, [(0,540),(180,560),(400,640),(440,800),(280,880),(80,860),(0,720)]),
    # rood blok rechts onder
    (ROOD,  [(720,640),(1200,640),(1200,1100),(450,1100),(420,980),(580,880),(740,820),(770,720)]),
    # groen blob rechtsonder
    (GROEN, [(900,1000),(1200,1000),(1200,1200),(800,1200),(820,1100)]),
    # rood onderkant links
    (ROOD,  [(0,900),(220,920),(420,1000),(500,1100),(420,1200),(0,1200)]),
]

def paint_background(img):
    """Schildert de organische gekleurde achtergrond op img."""
    d = ImageDraw.Draw(img)
    W, H = img.size
    for color, pts in PAINTED_BLOBS:
        scaled = [(int(x * W / 1200), int(y * H / 1200)) for (x,y) in pts]
        d.polygon(scaled, fill=color)

def draw_age_badge(img, xy=None):
    """De '4+' badge rechtsboven."""
    W, H = img.size
    d = ImageDraw.Draw(img)
    cx, cy = xy if xy else (W - 90, 70)
    f = get_font(80, bold=True)
    draw_marker_text(d, (cx, cy), "4+", fill=ROOD, outline=ROOD_DK, font=f, anchor="mm", offset=4)

def draw_corner_doodles(d, W, H):
    """Gele zigzag-krullen aan de zijkant (zoals in Kiki's nieuwe tekening, buiten de geschilderde area)."""
    # Op deze versie zit het 'papier' alleen om het kaartje heen; we tekenen de krullen
    # subtiel op de buitenrand van het canvas zelf is niet zinvol omdat de hele kaart geschilderd is.
    # In plaats daarvan: gele scribble-accenten over de geschilderde blobs.
    import math
    def squiggle(cx, cy, scale=1.0, rot=0, color=GEEL):
        pts = []
        for i in range(5):
            x = (i - 2) * 28 * scale
            y = ((-1)**i) * 16 * scale
            r = math.radians(rot)
            xr = x * math.cos(r) - y * math.sin(r)
            yr = x * math.sin(r) + y * math.cos(r)
            pts.append((cx + xr, cy + yr))
        for i in range(len(pts)-1):
            d.line([pts[i], pts[i+1]], fill=color, width=10)
    squiggle(80, 260, scale=1.2, rot=-12)
    squiggle(60, 700, scale=1.0, rot=10)
    squiggle(W-90, 480, scale=1.1, rot=15)
    squiggle(W-80, 950, scale=1.0, rot=-10)

def draw_doodles(d, W, H):
    """Marker-krullen aan de zijkant — slordig getekend zoals in Kiki's tekening."""
    import math
    def squiggle(cx, cy, color, scale=1.0, rot=0):
        # Een paar zigzag lijntjes
        pts = []
        for i in range(5):
            x = (i - 2) * 24 * scale
            y = ((-1)**i) * 14 * scale
            # rotate
            r = math.radians(rot)
            xr = x * math.cos(r) - y * math.sin(r)
            yr = x * math.sin(r) + y * math.cos(r)
            pts.append((cx + xr, cy + yr))
        for i in range(len(pts)-1):
            d.line([pts[i], pts[i+1]], fill=color, width=8)
    squiggle(60, 220, GEEL, scale=1.2, rot=-10)
    squiggle(60, 600, GEEL, scale=1.0, rot=8)
    squiggle(60, 980, GEEL, scale=1.1, rot=-5)
    squiggle(W-60, 320, GEEL, scale=1.0, rot=15)
    squiggle(W-60, 780, GEEL, scale=1.1, rot=-12)

def make_qr(url: str, out: Path):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=20, border=4)
    qr.add_data(url); qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").convert("RGB").save(out)

def _draw_card_top_branding(img):
    """HITSTER bovenaan + 4+ badge + KIKI Schoenmakers — bovenop de geschilderde achtergrond."""
    W, _ = img.size
    d = ImageDraw.Draw(img)
    # HITSTER (chunky groene letters over de paars/blauwe blobs)
    f = get_font(130, bold=True)
    draw_marker_text(d, (W//2, 130), "HITSTER",
                     fill=GROEN, outline=GROEN_DK, font=f, anchor="mm", offset=5)
    # 4+ badge rechtsboven
    f_age = get_font(72, bold=True)
    draw_marker_text(d, (W-90, 90), "4+", fill=ROOD, outline=ROOD_DK, font=f_age, anchor="mm", offset=4)

def make_card_front(qr_img: Path, out: Path):
    """Voorkant: geschilderde achtergrond, HITSTER bovenaan, witte QR in het midden, scan-tagline onder."""
    W = H = 1200
    img = Image.new("RGB", (W, H), PAPIER)
    # 1) Geschilderde kleurblob-achtergrond
    paint_background(img)
    d = ImageDraw.Draw(img)
    # 2) Gele krullen over de blobs
    draw_corner_doodles(d, W, H)
    # 3) HITSTER + 4+ bovenaan
    _draw_card_top_branding(img)
    # 4) Wit kader in het midden waarin de QR-code staat (zodat 'ie altijd scant)
    qr = Image.open(qr_img).resize((720, 720), Image.LANCZOS)
    qx, qy = (W - 720) // 2, 340
    # Schaduw + witte achtergrond + zwarte rand
    d.rectangle([(qx-30, qy-30), (qx+750, qy+750)], fill="white", outline="#222", width=5)
    img.paste(qr, (qx, qy))
    # 5) Tagline onderaan
    f_tag = get_font(54, bold=True)
    draw_marker_text(d, (W//2, 1130), "scan om te spelen!", fill="white", outline=DBLAUW, font=f_tag, anchor="mm", offset=4)
    img.save(out)

def make_card_back(title: str, artist: str, year, out: Path):
    """Achterkant: geschilderde achtergrond, HITSTER boven, GROOT jaartal in een witte ovaal, titel + artiest onder."""
    W = H = 1200
    img = Image.new("RGB", (W, H), PAPIER)
    paint_background(img)
    d = ImageDraw.Draw(img)
    draw_corner_doodles(d, W, H)
    _draw_card_top_branding(img)

    # Witte "spotlight"-ovaal achter het jaartal voor leesbaarheid
    d.ellipse([(120, 360), (W-120, 760)], fill="#fdfaf0", outline="#222", width=5)

    # GROOT jaartal in donkerblauw
    f_year = get_font(340, bold=True)
    draw_marker_text(d, (W//2, 560), str(year), fill=DBLAUW, outline="#0a1d4d", font=f_year, anchor="mm", offset=8)

    # Wit/cream band voor titel + artiest — font wordt automatisch kleiner als 't niet past
    d.rectangle([(80, 820), (W-80, 1010)], fill="#fdfaf0", outline="#222", width=4)
    text_max_w = (W - 80*2) - 40   # binnen de band, met wat padding
    f_title = fit_font(title, max_width=text_max_w, max_size=82, min_size=32, bold=True)
    draw_marker_text(d, (W//2, 880), title, fill=PAARS, outline="#3a1f6b", font=f_title, anchor="mm")
    f_artist = fit_font(artist, max_width=text_max_w, max_size=64, min_size=26, bold=True)
    draw_marker_text(d, (W//2, 965), artist, fill=ROZE, outline="#8a1f4a", font=f_artist, anchor="mm")

    # Branding onderaan
    f_brand = get_font(46, bold=True)
    draw_marker_text(d, (W//2, 1140), "KIKI Schoenmakers", fill="white", outline=CYAAN, font=f_brand, anchor="mm", offset=3)
    img.save(out)

def _entry_track_id(v):
    """songs.json mag oude (string) of nieuwe (object) entries bevatten."""
    if isinstance(v, str): return v
    if isinstance(v, dict): return v.get("spotify")
    return None

def add_song(title: str, artist: str, year, spotify: str, base_url: str):
    spotify = (spotify or "").strip()
    track_id = extract_track_id(spotify) if spotify else None
    db = load_json(SONGS_PATH, {})
    # Zoek of dit nummer al bestaat — op spotify-id óf op title+artist
    code = None
    for k, v in db.items():
        if k.startswith("_"): continue
        if isinstance(v, dict):
            same_track = track_id and _entry_track_id(v) == track_id
            same_meta  = (v.get("title","").lower() == title.lower()
                          and v.get("artist","").lower() == artist.lower())
            if same_track or same_meta:
                print(f"Al aanwezig als code {k!r} — entry & bestanden worden bijgewerkt.")
                code = k
                break
    if code is None:
        used = {k for k in db.keys() if not k.startswith("_")}
        code = short_code(used)

    # Schrijf altijd in de nieuwe objectvorm. Spotify-id is optioneel.
    entry = {
        "title":  title,
        "artist": artist,
        "year":   int(year) if str(year).isdigit() else year,
    }
    if track_id:
        entry["spotify"] = track_id
    db[code] = entry
    save_json(SONGS_PATH, db)

    redirect = f"{base_url.rstrip('/')}/?s={code}"
    safe = re.sub(r"[^a-z0-9]+", "_", f"{artist}_{title}".lower()).strip("_")[:60]
    qr_path = QR_DIR / f"{code}_{safe}.png"
    front = CARDS_DIR / f"{code}_{safe}_front.png"
    back  = CARDS_DIR / f"{code}_{safe}_back.png"

    make_qr(redirect, qr_path)
    make_card_front(qr_path, front)
    make_card_back(title, artist, year, back)

    print(f"OK  [{code}] {title} — {artist} ({year})")
    print(f"     URL: {redirect}")
    print(f"     QR:  {qr_path.name}")
    print(f"     Cards: {front.name}, {back.name}")

def make_print_sheets(out_pdf: str = "print_sheets.pdf"):
    """
    Bouw A4-printvellen waarbij elke 'card pair' bestaat uit:
       - bovenste helft: voorkant (normaal)
       - onderste helft: achterkant (180° gedraaid)
    Knip de pair uit, vouw langs de middenlijn, lijm de binnenkant, klaar.
    Geschikt voor enkelzijdige printers.
    """
    db = load_json(SONGS_PATH, {})
    entries = [(k, v) for k, v in db.items()
               if not k.startswith("_")
               and isinstance(v, dict)
               and not v.get("noPreview")]
    skipped = [(k, v) for k, v in db.items()
               if not k.startswith("_")
               and isinstance(v, dict)
               and v.get("noPreview")]
    if skipped:
        print(f"Overgeslagen ({len(skipped)} zonder preview):")
        for k, v in skipped:
            print(f"  [{k}] {v.get('title')} — {v.get('artist')}")

    # A4 op 300 DPI = 2480 x 3508 pixels
    PAGE_W, PAGE_H = 2480, 3508
    CARD = 760   # ~65 mm bij 300 DPI
    COLS, ROWS = 3, 2
    pair_w, pair_h = CARD, CARD * 2
    grid_w, grid_h = COLS * pair_w, ROWS * pair_h
    margin_x = (PAGE_W - grid_w) // 2
    margin_y = (PAGE_H - grid_h) // 2
    per_page = COLS * ROWS

    pages = []
    for page_start in range(0, len(entries), per_page):
        page = Image.new("RGB", (PAGE_W, PAGE_H), "white")
        d = ImageDraw.Draw(page)

        # Kop bovenaan met aantal kaartjes
        try:
            f_head = ImageFont.truetype("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf", 36)
        except Exception:
            f_head = ImageFont.load_default()
        pg_num = page_start // per_page + 1
        total_pages = (len(entries) + per_page - 1) // per_page
        d.text((margin_x, 60), f"Kikister printvel {pg_num}/{total_pages} — knip, vouw langs de stippellijn, lijm binnenkant.",
               fill="#444", font=f_head)

        for i in range(per_page):
            idx = page_start + i
            if idx >= len(entries):
                break
            code, info = entries[idx]
            col = i % COLS
            row = i // COLS
            x = margin_x + col * pair_w
            y = margin_y + row * pair_h

            safe = re.sub(r"[^a-z0-9]+", "_", f"{info['artist']}_{info['title']}".lower()).strip("_")[:60]
            front_path = CARDS_DIR / f"{code}_{safe}_front.png"
            back_path  = CARDS_DIR / f"{code}_{safe}_back.png"
            if not front_path.exists() or not back_path.exists():
                print(f"WARN: bestanden missen voor {code} ({info.get('title')})")
                continue

            front_img = Image.open(front_path).convert("RGB").resize((CARD, CARD), Image.LANCZOS)
            back_img  = Image.open(back_path).convert("RGB").resize((CARD, CARD), Image.LANCZOS).rotate(180)
            page.paste(front_img, (x, y))
            page.paste(back_img,  (x, y + CARD))

            # Vouwlijn (stippellijn op de middenlijn van de pair)
            fold_y = y + CARD
            for fx in range(x, x + CARD, 30):
                d.line([(fx, fold_y), (fx + 14, fold_y)], fill="#888", width=2)
            # Schaarsymbool aan de linkerkant van de vouwlijn
            sx, sy = x - 30, fold_y
            d.line([(sx, sy-8), (sx+18, sy-2)], fill="#888", width=2)
            d.line([(sx, sy+8), (sx+18, sy+2)], fill="#888", width=2)

            # Snijrand rondom de pair
            d.rectangle([x, y, x + CARD - 1, y + CARD * 2 - 1], outline="#bbb", width=2)

        # Voet
        try:
            f_foot = ImageFont.truetype("/usr/share/fonts/truetype/google-fonts/Poppins-Regular.ttf", 28)
        except Exception:
            f_foot = ImageFont.load_default()
        d.text((margin_x, PAGE_H - 90),
               "Tip: print op stevig papier of plak op karton. Vouw onderkant naar achter, lijm binnenin.",
               fill="#666", font=f_foot)
        pages.append(page)

    if not pages:
        print("Geen nummers gevonden om af te drukken.")
        return None

    out_path = ROOT / out_pdf
    pages[0].save(out_path, save_all=True, append_images=pages[1:], resolution=300.0)
    print(f"OK  {len(entries)} kaartjes verdeeld over {len(pages)} A4-vel(len) → {out_path.name}")
    return out_path

def cmd():
    cfg = load_json(CONFIG_PATH, {})
    ap = argparse.ArgumentParser(description="Voeg nummers toe aan Kikister")
    ap.add_argument("--set-base-url", help="Sla de basis-URL van je site op (bv. https://naam.github.io/kikister/)")
    ap.add_argument("--csv", help="CSV met kolommen: title,artist,year,spotify")
    ap.add_argument("--print-sheets", action="store_true",
                    help="Genereer A4 PDF met fold-in-half kaartjes voor enkelzijdige printer")
    ap.add_argument("title", nargs="?")
    ap.add_argument("artist", nargs="?")
    ap.add_argument("year", nargs="?")
    ap.add_argument("spotify", nargs="?")
    args = ap.parse_args()

    if args.set_base_url:
        cfg["base_url"] = args.set_base_url
        save_json(CONFIG_PATH, cfg)
        print(f"Basis-URL opgeslagen: {cfg['base_url']}")
        return

    if args.print_sheets:
        make_print_sheets()
        return

    base = cfg.get("base_url")
    if not base:
        sys.exit("Stel eerst je basis-URL in:  python add_song.py --set-base-url https://...")

    if args.csv:
        with open(args.csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                add_song(row["title"], row["artist"], row["year"], row["spotify"], base)
        return

    if not all([args.title, args.artist, args.year]):
        ap.error("Geef tenminste title, artist en year op (spotify is optioneel), of gebruik --csv.")
    add_song(args.title, args.artist, args.year, args.spotify or "", base)

if __name__ == "__main__":
    cmd()
