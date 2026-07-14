# Steam library artwork — sources

Two sets of artwork exist for the non-Steam shortcut:

1. **The committed `*.png` in this folder** — *original, generated* placeholder art
   ([`../make-art.py`](../make-art.py): a 70s desert-sunset scene, no copyrighted assets). Safe to
   publish; the repo ships these as the fallback.

2. **Authentic game art applied on the physical Deck** (2026-07-11) — official/community artwork
   (Activision-copyrighted). **NOT in this repo** — moved to the gitignored
   `../game-data/reference/art/authentic/` so the public repo ships no copyrighted assets. Re-fetch it yourself
   from these sources and drop into `~/.steam/steam/userdata/<id>/config/grid/` named by the
   shortcut appid (`<appid>p.png` portrait, `<appid>.png` header, `<appid>_hero.png`,
   `<appid>_logo.png`, `<appid>_icon.png`):

   - **SteamGridDB** (the canonical Steam-artwork site): <https://www.steamgriddb.com/game/5247794/grids>
     — the iconic blue gun-car box cover (600×900), the "Arsenal" landscape header (920×430), a
     full-bleed hero, and a clean transparent logo. *(Automated fetchers get 403 — open it in a real
     browser, or use the SteamGridDB API with a free key.)*
   - **GOG official art** via the API: `https://api.gog.com/products/1207661003?expand=images`
     — returns the key-art `background` (2560×670, the gun-topped muscle car), `logo`, and `icon`
     on the `images-*.gog-statics.com` CDN.
   - **Wikipedia** box cover (256×256, low-res): the infobox image on
     <https://en.wikipedia.org/wiki/Interstate_%2776>.

   What was applied on the Deck: portrait = SteamGridDB box cover; header = SteamGridDB "Arsenal"
   landscape; hero = SteamGridDB hero (upscaled to 1920×620); logo = SteamGridDB transparent logo;
   icon = that logo fit to 256×256. Assembled with `make-art.py`'s sibling one-off (PIL LANCZOS).
