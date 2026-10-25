# v0.7 announcement: texts to send (owner sends; nothing has been posted)

Who to send them to: [COMMUNITY-CONTACTS-2026-10-25.md](COMMUNITY-CONTACTS-2026-10-25.md). The long version is
[RELEASE-NOTES-v0.7.md](RELEASE-NOTES-v0.7.md). Link everywhere: **https://github.com/therealjkvalentine/i76-everywhere**
(the README's top has the download link and, once the video lane lands, the video).

When v0.7.4 is out, change "v0.7.3" in each text below.

---

## 1. Forum / Discord post (UltraFunk Discord, GOG Interstate forum)

**Title (GOG):** i76-everywhere Patch Kit v0.7.3 - 120 fps with the 1997 physics, 2.3 km draw distance, for your GOG copy

> Hi all. I've been working on a patch kit for the GOG version of Interstate '76 and it's ready for other people to try.
> It goes over your own GOG install (nothing of the game is in it) and keeps every original file, with an uninstaller
> that puts the folder back byte for byte.
>
> - 120 fps, with the car still simulated 24 times a second like on a 1997 Pentium 166, so the handling, the jumps and
>   the AI feel right (the mission 5 canyon jump matches the 1997 numbers exactly)
> - widescreen at your monitor's shape, nothing stretched
> - draw distance 600 m -> 1.8 km, or 2.3 km fading out at the edge in the preview launcher, with terrain that morphs in
>   instead of popping
> - a mirror that shows the road, menus that work with a modern mouse, a WASD layout + pad/wheel
> - a fix for the October Windows 11 update that broke start-up (dgVoodoo 2.87.5 + a winmm fix)
>
> In the repo but not in the kit yet: LAN games with AI cars filling empty seats, a two-player co-op campaign, Nitro
> "Arena Drop-In + AI" and "Co-Op" game types, wheel FFB with a tuning page, head look, and a Mac (Wine) build.
>
> Download and details: https://github.com/therealjkvalentine/i76-everywhere
> It's a pre-release; bug reports with `mciproxy.log` are very welcome. Hats off to vahokif's I26, which is a different
> approach (a reimplementation) and well worth a look too.

*(Discord: the same text; drop the title. GOG: post as a new thread, not a reply.)*

## 2. Email to creators (LGR, Dev Game Club, Gilgamechasaur, Spoony, ACE1918, ...)

**Subject:** Interstate '76 at 120 fps with the original physics - a patch kit for the GOG version

> Hi <name>,
>
> I saw your <video / episode: title> on Interstate '76 and thought you might like this. I've been building
> i76-everywhere, a free patch kit that goes over the GOG copy of the game: 120 fps while the car is still simulated at
> the 24 steps a second it ran at on a 1997 Pentium 166 (so the handling and the jumps are exactly as they were),
> widescreen without stretching, draw distance from 600 m out to 2.3 km with the terrain morphing in instead of popping,
> a proper rear-view mirror, and menus that work with a modern mouse. The original game code still runs underneath, so
> saves, add-on maps and multiplayer keep working; nothing of the game is redistributed. The repo also has LAN games
> with AI cars dropping into empty seats, a two-player co-op campaign, wheel force feedback and a Mac build, which I
> play with my family at home.
>
> Everything is here: https://github.com/therealjkvalentine/i76-everywhere . If it's useful, I'm happy to send a
> ready-to-run build, help set it up for a recording, or talk about how it was done (most of it was measuring the 1997
> game and working out what the frame rate changes). Thanks for keeping the game in front of people.
>
> James Valentine

*(Dev Game Club variant: replace the first sentence with "I listened to your 2025 episodes on Interstate '76, including
the interview with Sean Vesce and Zack Norman, and thought you might like this." and add, if wanted: "If Sean or Zack
are curious, I'd love to hear whether the 24-steps-a-second number matches what they remember.")*

## 3. Tweet-length line (Bluesky / X / Discord status)

> Interstate '76 at 120 fps with the original 1997 physics, widescreen, 2.3 km draw distance, for your GOG copy: free
> patch kit, nothing of the game included. https://github.com/therealjkvalentine/i76-everywhere

(209 characters with the link; X counts the link as 23, so 180 there.)

---

## 4. Courtesy notes (not announcements)

**To Dege (dgVoodoo 2), as a GitHub issue on dege-diosg/dgVoodoo2 titled "Heads-up: 2.87.5 fixes the DDraw start-up
crash after Windows 11 26100.9711 (Interstate '76)":**

> Thank you for dgVoodoo. A heads-up in case it is useful: after the 2026-10-24 cumulative update (KB5127647 /
> KB5127648 / KB5127690, build 26100.9711) on a Windows 11 24H2 laptop, 2.87.3's DDraw.dll crashed at start-up in
> Interstate '76 (GOG). 2.87.5 fixes it (DirectDrawCreate returns S_OK, the game boots and plays). Your 2.87.4 note
> ("Fixed the crash with Win11 26H1+ builds") looks like the same change arriving on 24H2 with that update; that is my
> inference, not proven. On a desktop that did not take the update 2.87.5 behaves the same as 2.87.3, and our 136-line
> conf loaded unchanged. (Separately, Defender quarantined the 2.87.4 zip as Trojan:Win32/Kepavll!rfn, as you said.)
> The game's other crash on that build was in winmmbase.dll, Windows' AcGenral shim, not dgVoodoo. We ship 2.87.5
> unmodified in a patch kit for the game, with your readme; if you would rather we did not bundle it, tell me and I
> will switch to a download step. Details: https://github.com/therealjkvalentine/i76-everywhere/blob/main/docs/records/DGVOODOO-UPDATE-2026-10-24.md

*(Owner check before sending: THIRD-PARTY.md still says redistribution was "not checked against the licence text",
while the kit README says "shipped as its readme allows". Settle that first; the last two sentences assume the kit
README is right.)*

**To vahokif (I26):** the draft in [PRIOR-ART-I26-2026-10-21.md](../PRIOR-ART-I26-2026-10-21.md) s.7 still stands (the
41.667 ms step, the difficulty finding, the ANet notes). Send it with the forum post or before it, so it reads as a
note between two projects, not a competing announcement.

**To Local Ditch** (contact page): "Thanks for linking i76-everywhere from your links and FAQ pages. v0.7.3 is out as a
patch kit for the GOG copy (link). The optional maps step credits each author and downloads from your site and LSM,
never rehosting; if you would rather it did not fetch from localditch.com, say so and I will point it elsewhere."

## 5. Friends and family (text / group chat)

> Remember the car-combat game I've been obsessing over? It's done enough to share. If you have a PC, the GOG version of Interstate '76 is about $6 and this kit makes it run like it should on a modern machine: 120 fps, your monitor's shape, way more draw distance, and LAN games where computer drivers fill the empty seats so two of us can play against a full field. The boys and I have been playing co-op on it all week. Download and how-to: https://github.com/therealjkvalentine/i76-everywhere (read the README; it's three steps). If you try it, tell me what broke, and if you'd rather have a build that just runs, say so and I'll send one. Thank you for your patience while every computer in the house ran tests all night.

