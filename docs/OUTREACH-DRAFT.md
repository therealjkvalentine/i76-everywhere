# Outreach — announcing i76-everywhere (v1.0)

Ready-to-post drafts for sharing the project. **Nothing here is auto-posted** — copy, tweak the
greeting per venue, and post from your own accounts. Repo: **https://github.com/therealjkvalentine/i76-everywhere**
· Hosted save editor: **https://therealjkvalentine.github.io/i76-everywhere/**

## Where to post (checked July 2026)

| Venue | Angle | Why it's worth it |
|---|---|---|
| **interstate76.com forums** | "the community's own game, now on Apple Silicon + Deck" | Alive (Tuesday Night Events as of Mar 2026); the core faithful. |
| **GOG forum** — Interstate series board | "if you own it on GOG you already have the 20 FPS fix; here's the rest" | The de-facto "20 FPS thread" audience. |
| **VOGONS** | dgVoodoo-under-Wine + the Glide/DirectDraw details | DOS/early-Windows preservation crowd; they'll dig the internals. |
| **r/macgaming** | "1997 Glide game on Apple Silicon, free stack, no CrossOver" | Highest-traffic casual audience for the Mac angle. |
| **r/emulation**, r/retrogaming, r/DOSGaming | "runs everywhere + a browser save editor" | Broad reach; the save editor is the shareable hook. |
| **PCGamingWiki** — Interstate '76 page | Add Mac/Deck/Android rows + the fixes | **Highest passive discoverability** — people search this first. Community-editable. |
| **Open76 / Roanish-i76 GitHub** | Link the reverse-engineered save + texture formats | Attracts *builders*, not just players — see the issue templates below. |

---

## Universal body (works for forums/Reddit; trim per venue)

> **Interstate '76 running well on Apple Silicon Macs, the Steam Deck, and modern Windows — free/open-source stack, physics-correct 20 FPS, plus a browser save editor. No copyrighted files.**
>
> I spent some time getting I'76 Gold (GOG) running properly across everything I own and wrote down
> every gotcha in a public, reproducible repo:
>
> **https://github.com/therealjkvalentine/i76-everywhere**
>
> Highlights:
> - **Mac (Apple Silicon):** software renderer via DxWnd in a self-contained Wine wrapper — instant
>   start, in-mission music, clean quit, physics-safe ~19.2 FPS. No CrossOver, no Windows VM.
> - **Steam Deck:** the pretty dgVoodoo Glide→Vulkan path *with force feedback*, and a one-liner
>   installer that uses YOUR GOG download.
> - **Windows:** one-command setup for max graphics + FFB + an optional HD texture pack.
> - **Browser save editor** (no install, nothing uploaded): edit your garage — weapons, armor,
>   condition, parts, scene select — with measured weapon DPS/range. Runs in any browser:
>   https://therealjkvalentine.github.io/i76-everywhere/
>
> A few findings that might interest even Windows players:
> - The 2019 GOG `i76.exe` is **byte-identical to UCyborg's AiO patch** — so the 20 FPS physics
>   limiter (I76PATCH.DLL) is already inside every GOG install. If you own it on GOG, you already
>   have the frame-rate fix.
> - The **wrong-music-over-cutscenes** GOG bug (long called unfixable) is fixed here with a proxy
>   `SMACKW32.DLL` that recreates the 1997 CD-drive behavior — works on Mac *and* GOG-Windows.
> - dgVoodoo2 works under Wine on Apple Silicon with three specific conditions (documented), though
>   the Mac ships the software path instead — the per-launch MoltenVK shader compile isn't worth it.
>
> The repo contains **no game files** (OpenRA-style): you bring your own GOG copy. Issues and PRs
> welcome — especially test reports from other M-chips, Deck models, and (untested so far) Android
> via Winlator.

---

## Per-venue tweaks

**interstate76.com** — lead with community: *"Long-time fan — got our game running on the machines
people actually have now (M-series Macs, the Deck) so it's easy to jump back in for Tuesday nights."*

**GOG forum** — lead with the limiter finding: *"PSA: your GOG copy already contains the 20 FPS
physics fix (the exe is the AiO patch). Here's how to get the rest going on Mac/Deck/Windows…"*

**VOGONS** — lead with internals: the `-gdi` undocumented renderer switch, Glide-wrapper CWD gotcha,
dgVoodoo ≤2.78.2 + DXVK + Glide-only recipe under Wine, and the winemac arrow-key/Grey-code issue.

**r/macgaming** — lead casual: *"Interstate '76 (1997) on Apple Silicon, free stack, no CrossOver —
one download and a script."* Screenshot of the game in the big 4:3 window + the save editor.

---

## PCGamingWiki edit (do this — best long-term reach)

On the [Interstate '76 page](https://www.pcgamingwiki.com/wiki/Interstate_%2776):
- **Essential improvements / Other information:** note the AiO-limiter-inside-GOG fact and the
  cutscene-music proxy fix, linking the repo.
- **Other platforms / macOS + Linux (Steam Deck):** add rows pointing to the repo's Mac and Deck docs.
- **Input / Video:** the arrow-key Grey-code fix, the DxWnd letterbox recipe, dgVoodoo settings.
Keep it factual and cite the repo as the source; don't copy game assets.

---

## GitHub issues for the reimplementation projects (attracts builders)

Open a friendly issue on **[Open76](https://github.com/rob518183/Open76)** and
**[Roanish/i76](https://github.com/Roanish/i76)**:

> Subject: **Reverse-engineered save + texture formats you may find useful**
>
> Hi — I've been documenting I76's formats while building a cross-platform port
> (github.com/therealjkvalentine/i76-everywhere). The **save format is fully decoded** (116-byte
> records, item catalog from I76.ZFS, armor/condition/location model) with a working editor, and the
> **VQM/M16 texture formats** are cracked with round-trip encoders. All MIT, no game content. Happy
> to help if any of it is useful to your engine — and I'd love to point players your way as the
> long-term "modern I76." Cheers.

---

## Answer-in-advance (FAQ for replies)

- *"Is this legal?"* — Yes. No game content is distributed; you use your own GOG copy. See THIRD-PARTY.md.
- *"Do I need Claude/AI?"* — No. Every step is a script or spelled out. AI just makes the from-scratch
  Mac wrapper faster; the Deck/Windows installers are one command.
- *"Widescreen / higher res on Mac?"* — Camera is hardcoded 4:3; software renderer maxes at 1024×768.
  Higher internal res needs Glide (great on the Deck; parked on Mac). It's documented, not a bug.
