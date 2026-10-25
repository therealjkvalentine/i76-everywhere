# Privacy scrub, 2026-10-25

Rule of the day: nothing public names the developer, family members or testers, user-profile or private folder paths,
machine names, network addresses or private links. The committed text predates the rule. This record covers the scrub of
the working tree (tracked files, not git history) and what is left. Third-party credits (real authors of third-party
software, community map authors, the game's own credits) are public and stay.

## What was done

| Class | Replacement | Lines before | Lines after |
|---|---|---|---|
| Developer's name (prose) | "the developer" | 118 | 8 (the MIT copyright line, the rest in lane-owned files) |
| Family testers (two Macs) | "the M4 Max tester", "the M2 tester" (plus "Mac") | 322 | 14 |
| Outside tester of the first patch-kit build | "the tester" | 32 | 2 (plus file names, below) |
| User-profile paths | docs: `<lab>`, `<re-archive>`, `<games>`, `<downloads>`, `<home>` or a repo-relative path; scripts: `%USERPROFILE%` / `$env:USERPROFILE` / home lookup | 847 | 23 (listed below) |
| Archive, bench and gold-install paths | `<archive>`, `<bench>`, `<gold game folder>` | 60 | 17 |
| LAN addresses | `<LAN-IP>`, `<LAN subnet>`, `<LAN broadcast>`; test fixtures moved to the documentation range | 42 | 6 |
| Tailscale addresses | `<tailscale-ip>` or "the developer's MacBook" | 12 | 0 |
| Host names | "the laptop bench", "the desktop" | 11 | 7 (file names such as FFB-LAPTOP-RECON are not machine names) |
| Owner e-mail addresses | removed; patch author lines use the GitHub noreply address | 5 | 0 |
| ssh `user@host` strings | "the family Mac over ssh" | 12 | 0 |

"Before" is the tree at 6240f43, "after" is the tree after the third scrub commit. Counts are matching lines over tracked
text files (the bulky measurement file re/verify/oracles/results.json is data and was scrubbed too).

Code behaviour was not changed. Where a private value was a default, it became a parameter or a lookup:

- Python: profile-path literals became a home-directory lookup plus the rest of the path (same value on that account).
- PowerShell: `"$env:USERPROFILE\..."` or `(Join-Path $env:USERPROFILE '...')`; every changed script parses exactly as before.
- tools/lan-test/hosts.sh: the Mac and laptop addresses are no longer defaults. They come from a git-ignored
  `tools/lan-test/hosts.local.sh` (`hosts.local.sh.example` is committed); neutral placeholder defaults otherwise. The two
  Mac variables were renamed `M2MAC` and `M4MAC`.
- tools/consolidate-copies.ps1 and consolidate-retry-locked.ps1: archive root from `I76_ARCHIVE_ROOT` (dry-run output
  identical to before). tools/content-archive/copyidx.py: `I76_COMMUNITY_ARCHIVE`. deck/*.py scratch paths: `I76_DECK_WORK`.
  tools/setup-sshd-windows.ps1: `-Subnet` is now required instead of defaulting to a home subnet.
- Tests (`python -I -m unittest discover -s tests`): the same 16 errors as before the scrub (they need game files that are
  not in the repo), no new failure; syntax and parse checks of every changed .py and .ps1 equal to before.

## Left for the second pass

Files other lanes were editing during this pass (not touched): README.md, ROADMAP.md, AGENTS.md, docs/PROCESS.md,
.github/*, tools/patch-kit/*, PLAY-i76.ps1, every docs/records/*2026-10-25*.md, music-fix/* (including strlkproxy.c and
musicextra.c, whose source and binary pairing must not drift), tools/Build-From-GOG.ps1, tools/launch-video/*. Their
remaining hits: names and profile paths in AGENTS.md (5 profile-path lines), name and path lines across the 2026-10-25
records, a few comment lines in music-fix sources, and profile paths in tools/launch-video/compose.py and timeline-v1.json.

Functional strings that cannot be neutralised without changing behaviour or a shipped binary (decide per item):

- C sources with a profile path compiled in: lab/src/i76uncap.c (3 log and control paths), lab/src/u32x.c,
  u32x/u32x_full.c, u32x/u32x_min.c (one log path each). u32x is shipped: change the source and rebuild together, not
  text-only.
- Config files read verbatim: lab/tools/renderers/reshade/ReShade.ini (3 search paths), re/binaries/i76-gog2017.toml and
  re/binaries/sandbox.toml (reference exe and game dir), tools/trainer/tunables.json (reference exe path),
  tools/soundhd/out/pack-v1/manifest.json (provenance field of a built pack).
- Sibling-folder names used in code and in about 190 files of prose: the lab folder name and the evidence-archive folder
  name (tens of scripts match the lab name in a process path, tools/export_public.toml lists both as sibling repos, and
  `--i76-map` is a command-line flag of tools/menu-hd/build_hd.py). They are folder names, not profile paths; the prose
  uses placeholders, the code keeps the real names.
- Bundle identifiers of the form `com.<initials>.i76.*` in build-launchers.sh, setup-nitro.sh and two docs: changing them
  changes the macOS app identity (firewall entries, preferences).
- File names that carry a tester's first name: the first patch-kit build record under docs/records (referenced from about 20 files), plus script
  and preset names in history. Rename it together with its references (propose a TESTER-BUILD-2026-10-23.md name).
- The GitHub account name in URLs (clone, release, issue-form and Pages links) is the repository's address and stays unless
  the repository is moved. The MIT LICENSE carries the developer's legal name as copyright holder; the owner decides.
- docs/release/COMMUNITY-CONTACTS-2026-10-25.md and a research note list several third-party people's published e-mail
  addresses. They are public but belong to other people; recommend replacing them with the contact page or profile link
  they came from.
- Generic examples that remain: install-folder examples such as a `D:\Games\...` path in INSTALL.md.

## Cannot be scrubbed without losing meaning

Records whose subject is a comparison between named machines (the LAN matrices, the Mac converge and graphics-tune records,
the Nitro Mac and multiplayer design records) were rewritten to roles ("the M2 tester Mac", "the M4 Max tester Mac",
"the developer's MacBook"). The measurements survive; who sat at which machine does not. If a finer split is ever needed,
use stable role labels (Mac A, Mac B) rather than people. The first patch-kit build record is about one outside tester; it
now says "the tester" throughout, and its file name still names him (see above).

## Release assets embed the old text

The published pre-release v0.7.3 patch-kit zip and the draft v0.8.0 Patch Kit and Mac Kit zips carry a repo snapshot under
`_i76e/repo/` with profile paths and a first name in scripts and docs. A source rewrite does not change them. Rebuild the
kits from the scrubbed tree and replace the v0.7.3 asset; rebuild the draft before publishing it.

## Git history still holds the old text

This pass edited the tree only. Every earlier commit (1309 on all refs) still contains the old strings, and so do commit
messages (71 mention a name, address or profile path) and the commit author fields (an old personal address and a laptop
host name). The owner has approved a history rewrite; it has not been run. A replacement list for git-filter-repo (blob
text and commit messages), a mailmap, the list of binary blobs to drop and the command are kept outside the repository, in
the lab's privacy folder (REWRITE-NOTES.txt there). Findings from scanning all 4,690 blobs in history: four binary blobs
embed the profile path (two build intermediates, two Python bytecode files; none is in the current tree); no archives are
committed; the saves and executables contain no name or address. After a force-push, GitHub still serves old commits by SHA,
through forks and pull-request refs, and from caches until purged.

## Second pass, 2026-10-25 (later the same day)

Done: README, AGENTS, the 2026-10-25 records, docs/release (the five third-party e-mail addresses in COMMUNITY-CONTACTS and one in
the research dump became contact-page or profile links), the patch-kit comment, tools/launch-video (paths now come from `I76_LAB`
or default to `~/i76-uncap-lab`; `${LAB}` in the timeline and stills JSON expands to it), the 8 files that named SCOTT-BUILD, and
`docs/records/SCOTT-BUILD-2026-10-23.md` is now `TESTER-BUILD-2026-10-23.md` with every reference fixed. Compiled-in log paths in
lab/src/i76uncap.c, lab/src/u32x.c, u32x/u32x_full.c and u32x/u32x_min.c are now relative file names (the log lands in the
process's working folder). The shipped u32x DLLs do not contain the string (the log code is behind `U32X_LOG`), so no rebuild is
needed; a rebuild would only be needed to change the log build, with `u32xuild.ps1` / `lab\srcuild-u32x-log.ps1`.
Config files: ReShade.ini uses `%REFS%`, filled in by renderer-matrix.ps1 when it copies the file; tunables.json uses `~` (i76tune.py
expands it); the two re/binaries toml files and the soundhd manifest carry placeholder provenance values (documentation only).

Matching lines over tracked text files after pass 2 (PRIVACY-SCRUB record excluded):

| Class | After pass 1 | After pass 2 |
|---|---|---|
| Developer name (prose) | 8 | 0 (a third-party credit `James "moose2000" Brown` in a patch matches the rule text; the MIT line stays by design) |
| Family testers | 14 | 1 (a comment in music-fix/strlkproxy.c, lane-owned) |
| Outside tester | 2 | 0 |
| User-profile paths | 23 | 0 |
| Archive / bench / gold paths | 17 | 0 |
| LAN addresses | 6 | 0 |
| Host names | 7 | 0 (file names such as FFB-LAPTOP-RECON are not machine names) |
| E-mail addresses | 0 owner, 6 third party | 0 |
| ssh user@host | 0 | 0 |

Still left, with the reason:

- music-fix/* (dirty or edited today by running lanes): one family-tester name in a comment of strlkproxy.c. deck/* and tools/ffb/*
  were committed to within the last half hour and were not touched this pass; both were already free of the profile-path classes
  by the third pass of pass 1.
- Folder names kept in code: `game-scott-*` entries in tools/consolidate-copies.ps1 are the real names of lab folders. The history
  rewrite's `-scott` rule would turn them into `game-tester-*` and they would stop matching the folders on disk; rename the lab
  folders first or accept that those archive entries no longer match.
- Bundle identifiers `com.jkv.i76.*` (build-launchers.sh, setup-nitro.sh and docs) change the macOS app identity if renamed.
- The GitHub account name in URLs, the MIT copyright line and third-party credits (Scott Krager / Lahman, Andrew Heckler, Eric
  Valentine, James Brown and others) stay by rule.
- Sibling folder names (`i76-map`, `i76-uncap-lab`) in code comments and process paths stay as folder names, as in pass 1.
- New text keeps arriving from running lanes (docs/OWNER-TEST-LIST.md gained an ssh line while this pass ran). Run the class scan
  again immediately before the history rewrite.

Release assets: rebuilt by repacking the published or draft zips, not by running package-patch-kit.ps1 at HEAD. Reason: HEAD's
PLAY-i76.ps1 is 425 lines ahead of 935f897 and the packaging script already adds an unreleased SETTINGS.bat, so a fresh build
would ship untested launcher code in v0.8.0 and a different kit in v0.7.3. The repack keeps every binary byte-identical, replaces
only the text files that carried a name, a profile path or a lab folder (14 in v0.7.3, 16 in the v0.8.0 Patch Kit, 2 in the Mac Kit;
the four .py files that carried a profile literal are the scrubbed HEAD versions, which differ from the shipped ones only in that
literal), and rewrites `_i76e\MD5SUMS` / VERSION.txt to match. The kit contents were grepped clean (the project's GitHub URL and the
LICENSE copyright line remain).

| Asset | New sha256 | Old sha256 |
|---|---|---|
| v0.7.3 Patch Kit `...v0.7.3-f5d5ac0.zip` (published pre-release) | `ddaf9c738f6878bdbf2f6fe5749bdf6cf4393ad015ae1dd9145c94fd170ad783` | `365fdd2ab74438fc525954ef6afc3574f2998b90bb083b68a3c22e525054ee5f` |
| v0.8.0 Patch Kit `...v0.8.0-935f897.zip` (draft) | `c39a69c3daff616d83ff09cb013e38fcc17fdd44c7c93b6db379437fbfaccaa8` | `639e1e859f2e2973f8a3dd59d828fe24d1eb8c7dd068417e3e4b4403b1ff417e` |
| v0.8.0 Mac Kit `...v0.8.0-9cb3a44.zip` (draft) | `fb1160e97908f6de3dc50d97c1c0c78ef7c649211cadd1bc0fac1ee7fbf2679e` | `0953118cefef47d0c7194dbf9d7c35e72525786f8e69009bfbb29862817e6864` |
| v0.8.0 Mac Kit `.zip.MD5SUMS` | `ec98c244e5d88e1d8478b9e974ec266bf666a0d5a54fc289656dc6704782b7f8` | `688cae58409ba6f21e07f0f6b0f19480d2aa8c2e36719f805e751a7ee4fda03b` |

The v0.8.0 release is still a draft. The v0.7.3 body gained a line with the new sha256. The history-rewrite replacement list
(lab privacy folder) gained the third-party e-mail strings, the Deck host name, `ssh james@`, the escaped archive path and
`192.168.1.x`.
