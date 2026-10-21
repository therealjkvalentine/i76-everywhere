/* difficulty.c - the game's own Difficulty Level (Play Options) as the AI skill in network AI arenas. Included from
 * strlkproxy.c just before aimelee.c, which calls difficulty_ai_skill() from its host tick (one marked hook).
 * Record: docs/records/DIFFICULTY-OPTION-2026-10-20.md.
 *
 * WHAT THE GAME ALREADY HAS (our exe 6319abf7 is the GOG AiO build of Gold 1.2, not retail 1.0; shell a300db63):
 *   - Options > Play Options shows "Difficulty Level" as its 7th row (shell widget table 0x10047200: label 0x10047410,
 *     value 0x1004743c drawn by 0x100141d0 from the names Wimp / Champion / Badass at 0x100471f0, click 0x10014250
 *     cycles 0 -> 1 -> 2 -> 0). The shell keeps the value in its byte 0x100477b8, read by PlayerDef_Load 0x10016f70 and
 *     written by PlayerDef_Save 0x10017050 to I76PLYR.DEF +0x5c (one byte; +0x5d..+0x5f are stack garbage, every reader
 *     masks with 0xff).
 *   - The exe reads the DEF into 0x654b40 (player_LoadPlyrDef 0x4970f0, after every shell return), so the byte lives at
 *     0x654b9c while a mission runs. Its only gameplay readers are the player damage factor (bullets 0x4a76e8, flame
 *     0x4443a9): 2.0 / 1.0 / 0.75 for the PLAYER's shots, and only when net_IsNetworkGame 0x452d20 is 0. Stock does
 *     not tie it to the AI at all, and a network melee does not see it.
 *
 * WHAT THIS ADDS: in a network AI arena the host's AI skill follows that byte (I76_DIFFICULTY_AI=1, default):
 *   Wimp (0) -> skill 4, Champ (1) -> 3, Badass (2) -> 1 (g_diff_map, the one place to change the mapping; any other
 *   byte value is treated as Champ, as the exe's damage factor does).
 *   THE STOCK SKILL SCALE RUNS BACKWARDS: setSkill level 1 is the BEST driver and shooter, 5 the worst (and the AI block's
 *   default). 0x40bd90 fills ai+0xa81c throttle / +0xa820 steering / +0xa824 aim / +0xa828 fire from the tables at
 *   0x5fcb7c..: level 1 = 1.0 / 1.0 / 1.0 / 1.0, 2 = 0.8 / 0.8 / 0.8 / 0.9, 3 = 0.6 / 0.6 / 0.6 / 0.8, 4 = 0.5 / 0.5 / 0.4 / 0.7,
 *   5 = 0.4 / 0.4 / 0.2 / 0.6 (i76-map subsystems/ai.md M23; read back live on the host 2026-10-20: level 2 -> 0.8 0.8 0.8
 *   0.9, level 5 -> 0.4 0.4 0.2 0.6). The brief's first table (Wimp 2 / Champ 3 / Badass 5) would have made Wimp the
 *   hardest and Badass the softest; this table keeps its steps (one easier, two harder than Champ) the right way round. Only the host runs aimelee's skill code, so the
 *   host's DEF rules; a joiner's DEF changes nothing. I76_AIMELEE_SKILL, when set, overrides the byte (lab use);
 *   I76_DIFFICULTY_AI=0 gives aimelee's own value (3, the M1 default) whatever the byte says.
 * Logged when the (mission, byte, source, skill) changes: "difficulty: <name> -> AI skill N (source: DEF | env | off)".
 * The campaign and the single-player Instant Melee are not touched (the exe already applies Gold's player factor there).
 */
static const struct { const char *name; int skill; } g_diff_map[3] = {
    { "Wimp", 4 }, { "Champ", 3 }, { "Badass", 1 },          /* stock levels: 1 = best, 5 = worst (see above) */
};
static int g_diff_on = -1;                                  /* I76_DIFFICULTY_AI, read on first use */

/* the AI skill (1..5) for an AI car the host is about to set up; aim_skill = aimelee's value (I76_AIMELEE_SKILL or 3) */
static int difficulty_ai_skill(int aim_skill) {
    static DWORD last_key = 0xffffffff; static void *last_tab;
    void *tab = *(void **)(0x0054a178 + 4);                /* the mission's object table: a new arena = a new log line */
    int raw = *(volatile BYTE *)0x00654b9c, idx = raw <= 2 ? raw : 1, env = env_present("I76_AIMELEE_SKILL"), skill;
    DWORD key;
    const char *src;
    if (g_diff_on < 0) g_diff_on = env_flag("I76_DIFFICULTY_AI", 8, 1);
    if (env) { skill = aim_skill; src = "env"; }
    else if (!g_diff_on) { skill = aim_skill; src = "off"; }
    else { skill = g_diff_map[idx].skill; src = "DEF"; }
    key = (DWORD)raw | (DWORD)skill << 8 | (DWORD)(env ? 1 : g_diff_on ? 0 : 2) << 16;
    if (key != last_key || tab != last_tab) {
        mlog("difficulty: %s -> AI skill %d (source: %s)%s", g_diff_map[idx].name, skill, src,
             raw > 2 ? " [unknown DEF byte, read as Champ]" : "");
        last_key = key; last_tab = tab;
    }
    return skill;
}
