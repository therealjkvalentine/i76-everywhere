/* ===========================================================================
 * OWNER POLISH 2026-10-20 (docs/records/MENU-SOUND-POLISH-2026-10-20.md; included from strlkproxy.c before simtick.c)
 * ===========================================================================
 *
 * I76_SIGN_SOUND_RESTART=1 (off by default; on in the staged tick19 presets). Owner, play-test of the release candidate:
 * "i would really like the barricade hit sound to interrupt a playing barricade hit sound when triggered/appropriate
 * because it would sound a lot cooler to hit them and hear as they get closer together".
 *   The sound. A class-4 object (sign post, road-closed barricade) hit by a car plays vnvco3.wav on the CAR:
 *   physics_CollideBodyPair 0x434e5c..0x434ebc -> sound_PlayOnObject 0x4231f0 -> sound_StartObjectSound 0x421b40
 *   (I76_BREAKABLE_BOX's sweep plays the same call, simtick.c st_sign_sound). vnvco3.gpw's GAS0 header is all -1, so
 *   the defaults hold: priority 50, ONE instance, one-shot, 0.386 s (11025 Hz mono 8-bit, 4256 samples).
 *   Why a hit is dropped. The voice admission 0x422750 counts the active voices with the same name (0x422850..0x42287a)
 *   and, at the instance limit (voice +0x38 = 1), takes a voice of that name only if the new one's priority is
 *   strictly higher (0x4228b0 jg); the same car asking again has the same priority, so 0x422750 refuses and
 *   0x425130 / 0x421b40 return 0: the second hit inside 0.386 s plays nothing.
 *   The switch. Before the engine's call, if a vnvco3 voice is playing ON THAT CAR (0x4221d0 finds it by object and
 *   name, as setSiren's stop does) and the hit is a new one, that voice is stopped and freed with the engine's own
 *   stop 0x421e70 (-> 0x425ef0: Stop + Release + free, the path the per-frame update takes when a one-shot ends), then
 *   the engine's call starts the sound afresh. "New hit": the object hit (the tree root, +0x68 parents, of the other
 *   body's part [edi+4] at 0x434ebc; the sign the sweep knocks a post off) has not started or restarted the sound in
 *   the last 1.5 s. A barricade whose bar and legs touch the car over several passes therefore restarts the sound once,
 *   not every pass; the next barricade along the road (T05's ten swend_1, two pairs 5 m apart) restarts it. Other
 *   cars' voices and other names are never touched.
 *   Log: I76_SIGN_SOUND_LOG=1 (lab) logs every vnvco3 request (first 400: path, car, object hit, playing voice before,
 *   restarted, started or refused) and a total line every 25 requests; counting runs whether the restart is on or not,
 *   so the same log reads "before" (switch off) and "after".
 *
 * I76_FADE_NO_FLIP=1 (off by default; on in the staged tick19 presets). Owner: "when you click to exit the game two
 * frames flip back and forth really fast - this is not new, has always happened, but it looks a little buggy".
 *   Cause. The exe's palette fade 0x479a90 (fade-out 0x479c60: 32 steps, 10 ms each; called on leaving the mission
 *   0x4036af / 0x4041da / 0x404341 and after the mission-over menu 0x4044c7 = Exit Game, Abort, Replay ...) uploads a
 *   palette (0x5dd2c8) and PRESENTS (call [0x5dd2e0] at 0x479bdd) every step. Under the hardware (Glide) renderer the
 *   palette changes nothing on screen and nothing is drawn between the swaps, so each step flips to the other buffer:
 *   the last two frames alternate 32 times (~0.32 s).
 *   The switch. The present inside the fade loop (0x479bdd only) is skipped while the hardware renderer is live
 *   ([0x5dd2a8] == 1, renderer_IsHardwareDevice 0x495060); the palette uploads and the 10 ms step waits are unchanged,
 *   so the fade takes as long as before and the screen holds the last frame. The software renderer keeps its present
 *   (there the palette IS the fade). Log line at load; with I76_FADE_LOG=1 (lab) or I76_SIGN_SOUND_LOG=1 a line at a fade's 1st, 8th, 16th, 24th, 32nd step.
 */
static int st_call_site(DWORD site, DWORD stock, void *wrap, DWORD *chain, const char *what);   /* simtick.c */

/* ---- I76_SIGN_SOUND_RESTART ---------------------------------------------------------------------------------------- */
#define SSR_NAME ((const char *)0x004f1578)                  /* "vnvco3.wav" (0x434e62 pushes it) */
static int g_ssr, g_ssr_log;
static DWORD g_ssr_next = 0x004231f0;                        /* the call at 0x434ebc (chained if another hook is there) */
static BYTE *g_ssr_other;                                    /* [edi+4] at 0x434ebc: the other body of the contact */
static DWORD g_ssr_req, g_ssr_started, g_ssr_refused, g_ssr_restarted, g_ssr_same, g_ssr_logged;
static struct { BYTE *other; DWORD tick; } g_ssr_seen[32];
static int g_ssr_seen_i;
static int ssr_new_hit(BYTE *other) {                        /* 1 = this body has not (re)started the sound in the last 1.5 s */
    DWORD now = GetTickCount(); int i;
    if (!other) return 1;
    for (i = 0; i < 32; i++) if (g_ssr_seen[i].other == other && now - g_ssr_seen[i].tick < 1500) return 0;
    return 1;
}
static void ssr_note(BYTE *other) {
    int i;
    if (!other) return;
    for (i = 0; i < 32; i++) if (g_ssr_seen[i].other == other) { g_ssr_seen[i].tick = GetTickCount(); return; }
    g_ssr_seen[g_ssr_seen_i].other = other; g_ssr_seen[g_ssr_seen_i].tick = GetTickCount(); g_ssr_seen_i = (g_ssr_seen_i + 1) & 31;
}
/* the vnvco3 request for car (other = the post / part, 0 if unknown); play = the call that starts it. Returns its result. */
static int ssr_play(const char *path, BYTE *car, BYTE *other, int (__cdecl *play)(const char *, BYTE *, int), int f) {
    BYTE *v = 0; int restarted = 0, nh, r;
#ifdef _MSC_VER
    __try {
#endif
        if (car) v = ((BYTE *(__cdecl *)(const char *, BYTE *))0x004221d0)(SSR_NAME, car);   /* the voice playing it on this car */
        nh = ssr_new_hit(other);
        if (v && g_ssr) {
            if (nh) { ((void (__cdecl *)(BYTE *))0x00421e70)(v); restarted = 1; g_ssr_restarted++; }
            else g_ssr_same++;
        }
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { g_ssr = 0; mlog("  sign-sound: fault in the restart - turned off"); }
#endif
    g_ssr_req++;
    r = play(SSR_NAME, car, f);
    if (r) { g_ssr_started++; if (nh || restarted) ssr_note(other); } else g_ssr_refused++;
    if (g_ssr_log) {
        if (g_ssr_logged < 400) {
            g_ssr_logged++;
            mlog("  sign-sound: %s req %lu t=%lu car %p other %p playing-before %p %s -> %s", path, (unsigned long)g_ssr_req,
                 (unsigned long)GetTickCount(), (void *)car, (void *)other, (void *)v,
                 restarted ? "RESTARTED" : (v ? (g_ssr ? "same body: kept" : "kept (switch off)") : "none playing"),
                 r ? "started" : "REFUSED");
        }
        if (g_ssr_req % 25 == 0)
            mlog("  sign-sound: totals req %lu started %lu refused %lu restarted %lu same-body %lu (restart %s)", (unsigned long)g_ssr_req,
                 (unsigned long)g_ssr_started, (unsigned long)g_ssr_refused, (unsigned long)g_ssr_restarted, (unsigned long)g_ssr_same,
                 g_ssr ? "on" : "off");
    }
    return r;
}
static int __cdecl ssr_next_call(const char *name, BYTE *obj, int f) {
    return ((int (__cdecl *)(const char *, BYTE *, int))g_ssr_next)(name, obj, f);
}
static BYTE *ssr_root(BYTE *o) {                             /* the part's tree root (the ODEF object), as bbox_speed_normal: +0x68 = parent */
    int guard = 0;
#ifdef _MSC_VER
    __try {
#endif
        while (o && *(BYTE **)(o + 0x68) && ++guard < 16) o = *(BYTE **)(o + 0x68);
#ifdef _MSC_VER
    } __except (EXCEPTION_EXECUTE_HANDLER) { }
#endif
    return o;
}
static int __cdecl ssr_coll(const char *name, BYTE *obj, int f) {
    if (name != SSR_NAME) return ssr_next_call(name, obj, f);
    return ssr_play("contact", obj, ssr_root(g_ssr_other), ssr_next_call, f);
}
static __declspec(naked) void ssr_coll_thunk(void) {         /* at 0x434ebc: edi = the record of the other body (0x434dc7..0x434ddb) */
    __asm {
        mov eax, dword ptr [edi + 4]
        mov dword ptr [g_ssr_other], eax
        jmp ssr_coll
    }
}
static int __cdecl ssr_stock_call(const char *name, BYTE *obj, int f) {
    return ((int (__cdecl *)(const char *, BYTE *, int))0x004231f0)(name, obj, f);
}
/* simtick.c st_sign_sound: the sweep's knock-off (no engine contact), root = the sign whose post was knocked off */
static void ssr_sweep_sound(BYTE *car, BYTE *root) {
    if (g_ssr || g_ssr_log) ssr_play("sweep", car, root, ssr_stock_call, 0);
    else ssr_stock_call(SSR_NAME, car, 0);
}
static void apply_sign_sound_restart(void) {
    int on = env_flag("I76_SIGN_SOUND_RESTART", 8, 0) == 1, lg = env_flag("I76_SIGN_SOUND_LOG", 8, 0) == 1;
    static const BYTE nm[11] = "vnvco3.wav";
    if (!on && !lg) return;
    if (memcmp((const void *)0x004f1578, nm, 11) != 0) { mlog("  sign-sound: 0x4f1578 is not \"vnvco3.wav\" (unknown exe) - not applied"); return; }
    g_ssr = on; g_ssr_log = lg;
    if (!st_call_site(0x00434ebc, 0x004231f0, (void *)ssr_coll_thunk, &g_ssr_next, "collision sound (sign-sound restart)")) {
        mlog("  sign-sound: the contact sound call 0x434ebc was not patched - the sweep path only");
    }
    mlog("  sign-sound: I76_SIGN_SOUND_RESTART=%d (a new hit on a sign / barricade %s the vnvco3 playing on that car), log %s",
         g_ssr, g_ssr ? "stops and restarts" : "does not interrupt", g_ssr_log ? "on" : "off");
}

/* ---- I76_FADE_NO_FLIP -------------------------------------------------------------------------------------------- */
static int g_fade_noflip, g_fade_log;
static DWORD g_fade_steps, g_fade_skipped, g_fade_last;   /* per fade (a gap of 1 s starts a new one) */
static void __cdecl fade_present(void *disp) {               /* replaces call [0x5dd2e0] at 0x479bdd (the fade loop's present) */
    DWORD now = GetTickCount();
    int skip = g_fade_noflip && *(volatile DWORD *)0x005dd2a8 == 1;   /* hardware renderer: the palette fades nothing */
    if (now - g_fade_last > 1000) { g_fade_steps = 0; g_fade_skipped = 0; }
    g_fade_last = now; g_fade_steps++; if (skip) g_fade_skipped++;
    if (g_fade_log && (g_fade_steps == 1 || g_fade_steps % 8 == 0))
        mlog("  fade: step %lu t=%lu, present %s (%lu skipped so far)", (unsigned long)g_fade_steps, (unsigned long)now,
             skip ? "SKIPPED" : "made", (unsigned long)g_fade_skipped);
    if (skip) return;
    ((void (__cdecl *)(void *))*(DWORD *)0x005dd2e0)(disp);
}
static void apply_fade_no_flip(void) {
    static const BYTE o[6] = { 0xFF, 0x15, 0xE0, 0xD2, 0x5D, 0x00 };   /* call dword ptr [0x5dd2e0] */
    BYTE w[6] = { 0xE8, 0, 0, 0, 0, 0x90 };
    LONG rel;
    g_fade_noflip = env_flag("I76_FADE_NO_FLIP", 8, 0) == 1;
    g_fade_log = env_flag("I76_FADE_LOG", 8, 0) == 1 || env_flag("I76_SIGN_SOUND_LOG", 8, 0) == 1;
    if (!g_fade_noflip && !g_fade_log) return;
    rel = (LONG)((DWORD_PTR)fade_present - (0x00479bdd + 5)); memcpy(w + 1, &rel, 4);
    if (!patch_bytes(0x00479bdd, o, w, 6, "palette fade present (fade-no-flip)") || memcmp((void *)0x00479bdd, w, 6) != 0) {
        g_fade_noflip = 0; mlog("  fade: the fade present 0x479bdd did not verify - not applied"); return;
    }
    mlog("  fade: I76_FADE_NO_FLIP=%d (the palette fade's 32 presents %s under the hardware renderer)", g_fade_noflip,
         g_fade_noflip ? "skipped" : "kept, counted");
}
