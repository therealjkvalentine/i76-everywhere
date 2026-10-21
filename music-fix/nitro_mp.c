/* nitro_mp.c - SKELETON (2026-10-21, nitro-mp-design lane): our multiplayer features on nitro.exe 28b8ae27 +
 * nitshell.dll f804f50d + anet2.dll a21c2baa, behind ONE separate menu entry, stock Nitro multiplayer untouched.
 * Design and evidence: docs/records/NITRO-MP-DESIGN-2026-10-21.md; RE notes: i76-map nitro-net\README.md.
 *
 * NOT BUILT, NOT INCLUDED from strlkproxy.c. Comments and empty functions only. Every address below is a static
 * proposal: the nitro-mp lane checks each site's bytes at run time (as sites_nitro.h does for the port) and refuses a
 * site that differs. Gold addresses in brackets.
 *
 * ---------------------------------------------------------------------------------------------------------------
 * THE ONE SWITCH: g_nmp_mode
 *   0 (always at boot) = stock Nitro. Nothing in this file acts, and every multiplayer switch of the Gold proxy is
 *     forced off for the session (list in nmp_force_stock). A patched game in a stock session behaves stock.
 *   1 = the user clicked our entry. Set by nmp_entry_click, cleared by nmp_leave (main menu 0xc00e, session end,
 *     dpClose). The shell and the exe are one process with one proxy, so the flag needs no transport between them.
 *
 * SHELL (nitshell.dll, base 0x10000000; the proxy is loaded first: nitshell and nitro.exe both import Strlkup.dll,
 * so the patch runs from a GetModuleHandleA("nitshell.dll") watch as mpm_watch does on Gold)
 *   S1 button   : a new widget record (proxy memory), id 0x13, built with Button_Init 0x1000e410 in the melee group
 *                 (beside ids 9 / 0xc, free space x 0x1d7 y 0x170 [inferred]); drawn as text (no sprite in the shell
 *                 database) or a sprite we add. Layout fn 0x10009610 / redraw 0x10009c10 get one extra show call.
 *   S2 click    : frame handler 0x10008770, `cmp esi, 0x12; ja 0x100092e6` at 0x1000887b: the ja target -> stub
 *                 nmp_entry_click (id 0x13 -> mode 1, then the id-9 path: HOST / JOIN; else jmp 0x100092e6).
 *   S3 species  : [0x10046cb0] u16 sessionType 604 (dpOpen in 0x1002f3c0 at +0xd of the 0x5f-byte session record,
 *                 dpEnumSessions in 0x1002dfb0): NMP_SPECIES while mode 1, 604 otherwise (written on entry / leave).
 *                 Our sessions are invisible to stock JOIN lists and stock sessions to ours.
 *   S4 version  : 'JO' version check against "6.04" [0x10045810] (handler 0x1002ffd0): our host sends NMP_VERSION
 *                 in mode 1 so a stock joiner that reaches it anyway gets the stock "version does not match" box.
 *   S5 list     : arena list 0x10031320 (`*.cbt` through the VFS, then findfirst "addon\*.cbt" 0x10045338): mode 1
 *                 adds `addon\nmp\*.cbt|*.lvl` (our scenes / scenarios) through the shell's msvcrt _findfirst import;
 *                 mode 0 sees exactly the stock list. Mission name "nmp\xxx" (<= 19 chars, record +0x20).
 *
 * EXE (nitro.exe)
 *   E1 receive  : IAT ANET2.DLL!dpReceive 0x4c13cc [anetdll.dll!dpReceive, patched by name] -> nmp_dpReceive (net_Pump 0x448d80 drops
 *                 unknown types after 0x446bb0 last-heard; the hook reads ours after the real call, as on Gold).
 *   E2 send     : through [0x4c13c0] dpSend [0x4bc38c]; every buffer keeps 16 spare bytes (ANet 1 wrote 4 past the
 *                 payload; not yet checked on ANet 2).
 *   E3 globals  : dp 0x53f258 [0x541024], me 0x53f25c [0x541028], net 0x53f264 [0x541030], host 0x53ecfc
 *                 [0x541064], group 0x53ecf8 [0x541060], players 0x53ed08 x 16 x 0x50 [0x541070 x 0x48], count
 *                 0x53ed00 [0x541068], flags 0x53f228 (team game = & 0x40 | & 0x2000, NOT a bool like [0x541010]),
 *                 mission 0x526758 [0x5049f0], join CRC 0x52676c [0x504a04], label table 0x552fd8 [0x54a178],
 *                 game state 0x4f30cc [0x4c2164]. Entity: owner +0x484 [+0x480], dead bit +0x458 [+0x454].
 *   E4 host tick: 0x4079a2 [0x40a5d0] call 0x42fee0 in ai_FrameTick 0x4076f0.
 *   E5 kill     : 0x46332e [0x46419d] call 0x42fee0 in entity_DamageAndKill 0x462c00.
 *   E6 AI fire  : 0x4064e6 [0x414f86] call weapon_SetTrigger 0x4af010.
 *   E7 joiner AI: 0x432e24 [0x403ddf] ai_FrameTick call in WinMain 0x431760 (skipped on joiners in mode 1).
 *   E8 damage   : object_ClassDamage 0x44fd80 [0x462040], its call sites (port lane's table).
 *   E9 score    : 0x464409 [0x465267] mirror -> net_SetPlayerScore 0x447050 (skip owner id 0).
 *   E10 chain   : 0x433165 [0x404110] (-> 0x44f550) and 0x433717 [0x404662] (-> net flag 0x448630).
 *   E11 box     : 0x4486ab [0x452d9f] `push 0; call 0x449ef0` scoreboard create (Nitro takes an argument;
 *                 0x4486b3 is a different call).
 *   E12 'ST'    : 0x445db8 [0x456c78] 'ST' handler -> mirror 0x463a20 (AI rows: who wrecked whom).
 *   E13 pool    : 0x4bd4bf [0x4b45bf] ODEF handler 0x4bd4b0 -> 0x4b3630: inject the parked AI records.
 *   E14 spawns  : per-team spawn tables (Nitro: "no spawn points for team %d"); count / layout to trace
 *                 [0x53fd88 / 0x540d98 single table on Gold].
 *
 * PACKETS (mode 1 only; 2-letter tags the stock pump drops): 'AT' AI state (<= 2 x 100 B per packet), 'AK' kill,
 * 'AM' reload / next scene, 'AC' CB line, 'AO' objective, 'AV' AI-pack report, + 'AH' (new) session hello
 * {u16 'AH', u8 proto, u8 flags, u32 pool CRC} sent by the host on every join and after a migration.
 * ---------------------------------------------------------------------------------------------------------------
 */
#if 0   /* skeleton: not compiled */

#define NMP_SPECIES  0x0000   /* our ANet sessionType: to be picked (not 604); see the record, risk R3 */
#define NMP_VERSION  "6.04+"  /* host 'JO' version string in mode 1 (S4) */

static volatile LONG g_nmp_mode;   /* 0 stock, 1 our entry */

/* --- mode ------------------------------------------------------------------------------------------------ */
static void nmp_force_stock(void) { /* every MP switch off while g_nmp_mode == 0: I76_COOP_AI, I76_COOP_CHAIN,
                                       I76_COOP_DAMAGE, I76_COOP_SCALE, I76_AIMELEE (+ _FILL, _RESPAWN, _RESPAWN_AI,
                                       _SCORE_ROWS, _TEAMS, _WAVE, _ARENAS), I76_DIFFICULTY_AI in network games,
                                       I76_MP_MENU (Gold shell only) */ }
static void nmp_enter(void) { /* mode 1; S3 species, S4 version, S5 list on */ }
static void nmp_leave(void) { /* mode 0; restore 604, "6.04", stock list; drop pool state */ }

/* --- shell ----------------------------------------------------------------------------------------------- */
static void nmp_shell_attach(BYTE *nitshell) { /* S1 button record, S2 ja-target patch, S5 _findfirst IAT hook */ }
static void nmp_entry_click(void) { /* S2 stub body: id 0x13 -> nmp_enter, then the id-9 HOST / JOIN path */ }
static void nmp_button_draw(void) { /* S1: text label when no sprite */ }
static intptr_t __cdecl nmp_findfirst(const char *spec, void *fd) { /* S5 */ return -1; }

/* --- exe: network layer ------------------------------------------------------------------------------------ */
static int __cdecl nmp_dpReceive(void *dp, void *from, void *to, int flags, void *buf, void *size) {
    /* E1: r = real(...); if (!g_nmp_mode) return r;  then the Gold coop_dpReceive body, re-addressed (E3) */
    return 0;
}
static int nmp_send(const void *pkt, int n) { /* E2 */ return 0; }
static int nmp_role(void) { /* 0 none, 1 host (me 0x53f25c == host 0x53ecfc), 2 joiner */ return 0; }
static void nmp_hello_send(void) { /* 'AH' on join / migration (host) */ }
static void nmp_hello_receive(const BYTE *pkt, int n) { /* joiner: pool CRC equal? else 'no AI pack' line */ }
static void nmp_migrate(void) { /* new host: adopt the AI rows / pool state every joiner already holds,
                                    restart the co-op scene (as on Gold), re-send 'AH' */ }

/* --- exe: entity features (Gold code re-addressed; netcode-independent) ----------------------------------- */
static void nmp_ai_sync_host(void)    { /* 'AT' sender (coop_ai_host_send) */ }
static void nmp_ai_sync_apply(const BYTE *pkt, int n) { /* coop_ai_apply + aim_at_revive + team byte */ }
static void nmp_host_tick(void)       { /* E4: aim_tick, difficulty skill, attacker cap */ }
static void nmp_kill_credit(void)     { /* E5: aim_on_kill -> 'AK' */ }
static void nmp_pool_inject(void)     { /* E13: aim_odef - 7 parked AI per stock .cbt arena */ }
static void nmp_fill_tick(void)       { /* mpfill: park / bring, teams, per-team spawn tables (E14) */ }
static void nmp_rows_tick(void)       { /* aim_rows_tick: AI rows in 0x53ed08, 0x50 stride, +0x44 = 1.0f, +0x48 team */ }
static void nmp_respawn_tick(void)    { /* aim_respawn_tick: humans and AI */ }
static void nmp_chain(void)           { /* E10: co-op chain 'AM' reload / next scene */ }
static void nmp_box(void)             { /* E11: scoreboard lines */ }

void apply_nitro_mp(void) { /* DllMain, nitro.exe only (exe hash): arm E1..E14 behind g_nmp_mode, start the
                               nitshell watch; nothing is written until a site's bytes check out */ }

#endif
