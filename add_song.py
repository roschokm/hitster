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

def get_font(size: int, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for c in candidates:
        if os.path.exists(c):
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()

def make_qr(url: str, out: Path):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=20, border=4)
    qr.add_data(url); qr.make(fit=True)
    qr.make_image(fill_color="black", back_color="white").convert("RGB").save(out)

def make_card_front(qr_img: Path, out: Path):
    W = H = 1200
    img = Image.new("RGB", (W, H), "white")
    qr = Image.open(qr_img).resize((900, 900), Image.LANCZOS)
    img.paste(qr, ((W-900)//2, (H-900)//2))
    d = ImageDraw.Draw(img)
    d.text((W//2, 80), "KIKISTER", fill="black", font=get_font(60, bold=True), anchor="mm")
    img.save(out)

def make_card_back(title: str, artist: str, year: str|int, out: Path):
    W = H = 1200
    img = Image.new("RGB", (W, H), "#1DB954")
    d = ImageDraw.Draw(img)
    d.text((W//2, 360), str(year), fill="white", font=get_font(220, bold=True), anchor="mm")
    d.text((W//2, 660), title, fill="white", font=get_font(90, bold=True), anchor="mm")
    d.text((W//2, 790), artist, fill="white", font=get_font(70), anchor="mm")
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
