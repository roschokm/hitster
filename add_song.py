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
GROEN       = "#8bcd3c"
GROEN_DK    = "#4d7a1f"
ROOD        = "#e83a3a"
GEEL        = "#f0c800"
ORANJE      = "#f06430"
CYAAN       = "#1aa8c4"
ROZE        = "#d8327a"
DBLAUW      = "#2147a8"
PAPIER      = "#fefcf4"

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

def draw_notebook_bg(img):
    """Geef de achtergrond de 'schoolschrift'-lijntjes."""
    W, H = img.size
    d = ImageDraw.Draw(img)
    line_color = "#c5dff0"
    for y in range(60, H, 70):
        d.line([(0, y), (W, y)], fill=line_color, width=2)

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

def draw_hitster_banner(img, cy, w_frac=0.78):
    """Tekent de HITSTER-banner: paars/blauw blok met groene chunky letters + 4+ badge."""
    W, _ = img.size
    bw = int(W * w_frac)
    bh = 180
    x0 = (W - bw) // 2
    y0 = cy - bh // 2

    # We tekenen op een aparte laag zodat we de hele banner kunnen roteren.
    layer = Image.new("RGBA", (bw + 80, bh + 60), (0, 0, 0, 0))
    ld = ImageDraw.Draw(layer)
    # Linker derde paars, rechter twee derde blauw
    split = int(bw * 0.30)
    ld.rectangle([(40, 30), (40+split, 30+bh)], fill=PAARS)
    ld.rectangle([(40+split, 30), (40+bw, 30+bh)], fill=BLAUW)
    # HITSTER tekst
    f = get_font(124, bold=True)
    draw_marker_text(ld, (40 + bw//2, 30 + bh//2 + 8), "HITSTER",
                     fill=GROEN, outline=GROEN_DK, font=f, anchor="mm", offset=4)
    # 4+ badge rechtsboven
    f_age = get_font(56, bold=True)
    draw_marker_text(ld, (40 + bw - 36, 30 + 18), "4+",
                     fill=ROOD, outline="#8a1f1f", font=f_age, anchor="mm", offset=3)

    # Lichte rotatie (zoals in Kiki's tekening, een beetje scheef)
    rot = layer.rotate(-2.0, resample=Image.BICUBIC, expand=True)
    px = (W - rot.size[0]) // 2
    py = y0 - 15
    img.paste(rot, (px, py), rot)

def draw_kiki_block(img, cy):
    """De 'Kids Bij KIKI Schoenmakers'-tekstgroep, in viltstift-stijl."""
    W, _ = img.size
    d = ImageDraw.Draw(img)
    # 'Kids Bij'
    f_kb = get_font(72, bold=True)
    # Twee delen in verschillende kleuren naast elkaar
    kids_w = f_kb.getlength("Kids ")
    bij_w  = f_kb.getlength("Bij")
    total  = kids_w + bij_w
    left   = (W - total) // 2
    draw_marker_text(d, (left + kids_w/2 - 10, cy), "Kids", fill=GEEL,   outline="#8a7300", font=f_kb, anchor="mm")
    draw_marker_text(d, (left + kids_w + bij_w/2, cy), "Bij", fill=ORANJE, outline="#a23a18", font=f_kb, anchor="mm")
    # KIKI groot
    f_kk = get_font(180, bold=True)
    draw_marker_text(d, (W//2, cy + 160), "KIKI", fill=CYAAN, outline="#0d6b80", font=f_kk, anchor="mm", offset=5)
    # Schoenmakers
    f_sm = get_font(58, bold=True)
    draw_marker_text(d, (W//2, cy + 280), "Schoenmakers", fill=ROZE, outline="#8a1f4a", font=f_sm, anchor="mm")

def make_qr(url: str, out: Path):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=20, border=4)
    qr.add_data(url); qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").convert("RGB").save(out)

def make_card_front(qr_img: Path, out: Path):
    """Voorkant: HITSTER-banner boven, QR-code in een wit kader in het midden, tagline onder."""
    W = H = 1200
    img = Image.new("RGB", (W, H), PAPIER)
    draw_notebook_bg(img)
    d = ImageDraw.Draw(img)
    # Buitenste rand
    d.rectangle([(20, 20), (W-20, H-20)], outline="#333", width=4)
    # Banner bovenaan
    draw_hitster_banner(img, cy=160)
    # Doodles aan de zijkant
    draw_doodles(d, W, H)
    # QR-vak in het midden — wit met dunne rand zodat 'ie altijd scant
    qr = Image.open(qr_img).resize((760, 760), Image.LANCZOS)
    qx, qy = (W - 760) // 2, 290
    d.rectangle([(qx-20, qy-20), (qx+780, qy+780)], fill="white", outline="#444", width=3)
    img.paste(qr, (qx, qy))
    # Tagline
    f_tag = get_font(46, bold=True)
    draw_marker_text(d, (W//2, 1110), "scan om te spelen!", fill=DBLAUW, outline="#0e2255", font=f_tag, anchor="mm")
    img.save(out)

def make_card_back(title: str, artist: str, year, out: Path):
    """Achterkant: HITSTER-banner, GROOT jaartal in het midden, titel + artiest onder."""
    W = H = 1200
    img = Image.new("RGB", (W, H), PAPIER)
    draw_notebook_bg(img)
    d = ImageDraw.Draw(img)
    d.rectangle([(20, 20), (W-20, H-20)], outline="#333", width=4)
    # Banner
    draw_hitster_banner(img, cy=160)
    # Doodles
    draw_doodles(d, W, H)
    # GROOT jaartal
    f_year = get_font(360, bold=True)
    draw_marker_text(d, (W//2, 520), str(year), fill=ROOD, outline="#8a1f1f", font=f_year, anchor="mm", offset=8)
    # Titel
    f_title = get_font(86, bold=True)
    draw_marker_text(d, (W//2, 800), title, fill=PAARS, outline="#3a1f6b", font=f_title, anchor="mm")
    # Artiest
    f_artist = get_font(68, bold=True)
    draw_marker_text(d, (W//2, 900), artist, fill=ROZE, outline="#8a1f4a", font=f_artist, anchor="mm")
    # Mini-branding onderaan
    f_brand = get_font(42, bold=True)
    draw_marker_text(d, (W//2, 1120), "KIKI Schoenmakers", fill=CYAAN, outline="#0d6b80", font=f_brand, anchor="mm")
    img.save(out)

def _entry_track_id(v):
    """songs.json mag oude (string) of nieuwe (object) entries bevatten."""
    if isinstance(v, str): return v
    if isinstance(v, dict): return v.get("spotify")
    return None

def add_song(title: str, artist: str, year, spotify: str, base_url: str):
    track_id = extract_track_id(spotify)
    db = load_json(SONGS_PATH, {})
    # Zoek of dit nummer al bestaat
    code = None
    for k, v in db.items():
        if k.startswith("_"): continue
        if _entry_track_id(v) == track_id:
            print(f"Al aanwezig als code {k!r} — entry & bestanden worden bijgewerkt.")
            code = k
            break
    if code is None:
        used = {k for k in db.keys() if not k.startswith("_")}
        code = short_code(used)

    # Schrijf altijd in de nieuwe objectvorm (title/artist/year/spotify)
    db[code] = {
        "title":   title,
        "artist":  artist,
        "year":    int(year) if str(year).isdigit() else year,
        "spotify": track_id,
    }
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

def cmd():
    cfg = load_json(CONFIG_PATH, {})
    ap = argparse.ArgumentParser(description="Voeg nummers toe aan Kikister")
    ap.add_argument("--set-base-url", help="Sla de basis-URL van je site op (bv. https://naam.github.io/kikister/)")
    ap.add_argument("--csv", help="CSV met kolommen: title,artist,year,spotify")
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

    base = cfg.get("base_url")
    if not base:
        sys.exit("Stel eerst je basis-URL in:  python add_song.py --set-base-url https://...")

    if args.csv:
        with open(args.csv, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                add_song(row["title"], row["artist"], row["year"], row["spotify"], base)
        return

    if not all([args.title, args.artist, args.year, args.spotify]):
        ap.error("Geef title, artist, year en spotify (URL of track-id) op, of gebruik --csv.")
    add_song(args.title, args.artist, args.year, args.spotify, base)

if __name__ == "__main__":
    cmd()
