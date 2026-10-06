# Installer lessons from OpenRA and similar projects (2026-10-06)

How projects that run on the player's **own** copy of an old game get people from "I own it" to "I'm playing", and
what that means for this repo. Researched from OpenRA's source, wiki and issue tracker, plus OpenMW, fheroes2,
Ship of Harkinian, Zelda64Recomp and Heroic/umu. Nothing here has been implemented yet except the README's newcomer
section and the GOG link fix.

## Lessons, each with what we should do

1. **Recognise the user's files by hash, not by path.** OpenRA's `IDFiles` pair files with sha1, optionally over the
   first N bytes of a large file (`mods/ra-content/installer/*.yaml`). *Do:* a `sources.json` of known GOG installers,
   `i76.exe` and Nitro builds, with the steps each gets; an unknown build stops with a clear message.
2. **Look in many places, and always let the user point at a folder.** OpenRA's detection broke on escaped Steam paths
   (PR #21140) and on Flatpak sandboxes hiding Steam libraries (#21443). *Do:* Downloads, the GOG Galaxy registry key
   (`GOG.com\Games\1207658836`), Heroic and Lutris folders, a mounted CD, then "point me at it".
3. **Leave the original untouched.** OpenRA extracts into its own support folder. We cannot split content from engine
   (our DLLs sit beside `i76.exe`), so: copy the verified install into a folder we manage and patch only the copy.
4. **Required vs optional parts.** OpenRA marks packages `Required` and lets music and movies come later. *Do:* base
   game required; Nitro, music, controller layers, force feedback optional and re-runnable.
5. **Only mirror what the rights holder freed.** OpenRA offers downloads only because EA made the games freeware, and
   still says the assets are not under its GPL. *Do:* never offer the game itself.
6. **Pin third-party downloads, keep mirrors outside the release.** OpenRA pins SHA1s and reads mirror lists from its
   site, failing gracefully when empty (PR #11375). *Do:* sha256 plus two URLs (upstream, archive.org) per tool, and an
   error that says where to fetch it by hand. Today `install.ps1` downloads dgVoodoo without a hash check, and
   `deck/deck-install.sh` takes dgVoodoo, innoextract and "latest" GE-Proton unpinned.
7. **Read licences before bundling.** dgVoodoo's terms allow shipping "individual dgVoodoo files" with a game or mod,
   require the full zip for standalone hosting, and say *"You cannot bundle dgVoodoo inside launchers or frameworks,
   for general use across multiple applications"* (https://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/): keep downloading
   it. DxWnd (GPL), OpenGLide (LGPL-2.1) and IPXWrapper (GPL-2.0) could be shipped with source; downloading stays
   simpler. THIRD-PARTY.md should quote dgVoodoo's terms instead of "not checked".
8. **Antivirus false positives return with every release** (OpenRA #3326; their fix was signed installers, #6805). We
   are more exposed: proxy DLLs, a patched import table, AutoHotkey, `-ExecutionPolicy Bypass`. *Do:* sign
   `Strlkup.dll`, `u32x.dll`, `i76wheel.exe` (e.g. SignPath's free OSS signing), publish sha256s and reproducible
   builds, add a FAQ entry.
9. **macOS Gatekeeper.** Unsigned downloaded apps show as "damaged" since Catalina. OpenRA first printed a notice
   (PR #16959), then paid for Developer ID notarization in CI (PR #17652, #20485). *Do:* keep compiling the Swift
   launchers on the user's Mac (no quarantine), never ship an un-notarized prebuilt `.app`, document the quarantine flag
   on the downloaded zip and `.command` files.
10. **Sandboxed packaging can't see game files** (Flatpak/Snap; OpenRA wiki "Game-Content"). *Do:* run the Deck script
    outside any sandbox and document Heroic's Flatpak paths.
11. **One log location per OS, and say what to read first.** OpenRA points users at the first line of `exception.log`;
    two of its installer failures hid behind generic messages (#12985, #20051). *Do:* an action-by-action
    `install.log`, and a `collect-diagnostics` script (file hashes, dgVoodoo conf accepted?, the RDP check, the
    `input.map` lint, the proxy log). Never swallow an exception.
12. **Release channels.** OpenRA: release / playtest / bleed, `prep-YYMM` branches. *Do:* the installer installs a
    tagged release; `main` is the experimental channel; presets say which channel they are proven on. The only release
    so far is v1.0.0 (2026-07-14).
13. **Keep user data apart from the install.** OpenRA has a portable `Support/` mode; Zelda64Recomp uses `portable.txt`.
    Our game writes saves into its own folder, so *do:* back up `savegame.dir` and the saves before any update or
    uninstall.
14. **Be honest about modification.** OpenRA can say it uses no binary patches; we patch. Ship of Harkinian publishes
    its supported ROM hashes and a web checker. *Do:* list every byte we change with before/after hashes, a
    one-command restore, and a browser hash checker beside the save editor.
15. **Meet players in the launchers they already use.** fheroes2 ships extract scripts with an innoextract path for GOG
    installers; OpenMW's wizard imports from an install or a GOG installer; Heroic runs games through umu + GE-Proton
    with automatic fixes. *Do:* support Heroic and Galaxy installs; later, contribute a umu-protonfixes entry for the GOG
    id.

## Installer shape we should aim for

**Scripts, not a separate launcher app.** OpenRA can keep content separate because it is a new engine reading assets.
We run the original exe, which loads our DLLs from its own folder, so the result is a patched game folder whatever we
build; an app would add signing, notarization ($99/year) and antivirus exposure without removing the patching.
`LAUNCHER.ps1` can stay as a thin optional front end.

One pipeline across `Setup-From-GOG.ps1`, `deck/deck-install.sh` and `mac-install.command`:

1. **Find** the GOG installer, a Galaxy / Heroic / Lutris install, a CD, or a folder the user names.
2. **Verify** by sha256 against `sources.json`; an unknown build stops with a clear message.
3. **Stage** a copy into a managed folder; the GOG install is never touched.
4. **Patch**: tools fetched with pinned hashes and fallback URLs, then deployed.
5. **Record** `i76e-manifest.json`: every file added or changed with before/after hashes, each write read back.
6. **Lint** the `input.map`, make the shortcut.

Update = a new managed folder with saves and a linted `input.map` carried over, the previous one kept. Rollback =
switch back, or `-Restore` from the manifest. Uninstall = delete the managed folder.

**Never ship** game files or the portable zip. **Keep fetching** dgVoodoo, DxWnd, IPXWrapper, AutoHotkey, innoextract,
GE-Proton. **May ship in Releases:** our own `Strlkup.dll`, `u32x.dll`, `i76wheel.exe` (signed, hashes in the notes)
and the patched OpenGLide-HD build with its source.

## Sources

- OpenRA installer content: https://github.com/OpenRA/OpenRA/tree/bleed/mods/ra-content
- OpenRA macOS packaging: https://github.com/OpenRA/OpenRA/blob/bleed/packaging/macos/buildpackage.sh
- OpenRA issues/PRs: #3326, #6805, #11375, #12985, #16959, #17652, #20051, #20485, #21140, #21355, #21443
- OpenRA wiki: Game-Content, FAQS-(Frequently-Asked-Support), Branches-and-Releases
- OpenMW: https://openmw.readthedocs.io/en/latest/manuals/installation/install-game-files.html
- fheroes2: https://github.com/ihhub/fheroes2/blob/master/docs/INSTALL.md
- Ship of Harkinian: https://github.com/HarbourMasters/Shipwright
- dgVoodoo terms: https://dege.freeweb.hu/dgVoodoo2/ReadmeGeneral/
