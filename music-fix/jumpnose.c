/* ===========================================================================
 * JUMP NOSE  (jump-pitch lane 2026-10-23; docs/records/TICK-FINISH-2026-10-18.md s.22.6; owner ruling 2026-10-23)
 * ===========================================================================
 * Included from strlkproxy.c after mirrordetail.c; applied after apply_simtick (Gold and Nitro: one site, in the Gold -> Nitro map).
 * Off unless set:
 *
 *   I76_JUMP_NOSE=<0.5..1.0>   the nose-down pitch rate a car carries into the air is scaled ONCE by this factor on its first
 *                              airborne step (unset or 1 = stock). The owner's ruling 2026-10-23: 0.91 = "the nose down pitch
 *                              tweak ... baaarely noticeable, like 9 % less".
 *
 * THE MECHANISM (TICK-FINISH s.22.4 / s.22.5, re-read 2026-10-23 from the exe). On the last grounded step before a lip, a
 * lifted front wheel makes physics_ResolveGroundContact 0x437230 ease the pitch rate toward -pi (one wheel) / -2 pi (two) with
 * k = 2 dt: the kick, -15 / -30 deg/s at 41.667 ms. In the air the airborne branch of physics_IntegrateVehicleMotion 0x43a5d0
 * (0x43a78a-0x43a898) copies the body rates ent+0xc8 into a local triple (0x43a7f5), compares the pitch copy with -pi/20
 * ([0x4bd1a4], 0x43a811) and calls the ease 0x43bda0 toward -pi/20 (0x43a82d) ONLY when the rate is above it, sets flag 0x4
 * from the old flags (0x43a83d: bit 4 clear there = the first airborne step) and rotates the pose by the copy (0x4389f0).
 * No throttle, aero or gravity torque touches the pitch in flight: a kicked rate is held to the landing (-35 deg single,
 * -85 double, the double-kick wreck). The held nose-dive is therefore a single stored number, and the smallest change is to
 * scale that number once when the car leaves the ground:
 *
 *   site 0x43a7f5 (Nitro 0x4265c2, the same 19 bytes): the copy `mov ecx,[edx] / add esp,0xc / mov [eax],ecx / mov ecx,[edx+4]
 *   / mov [eax+4],ecx / mov edx,[edx+8] / mov [eax+8],edx` becomes `call jn_copy_stub / add esp,0xc / nop x11`. The stub does
 *   the copy (edx = &ent->rates, eax = the copy; ecx / edx are dead after the site: reloaded at 0x43a825 / 0x43a83d) and calls
 *   jn_first_air(copy, ent = ebp): when flag 0x4 is clear (first airborne step) and the pitch rate is nose-down (< 0), both the
 *   stored rate ent+0xc8[0] and this step's copy are multiplied by the factor. Later airborne steps (flag 0x4 set) and every
 *   grounded step (0x437230, the other branch of 0x43a5d0) are untouched, so the lip kick itself, the take-off velocity, the
 *   ballistic path and ground handling are as stock; only the attitude the car carries across changes, by (1 - factor).
 *   A nose-up rate (> 0) is left alone. A bounce that leaves the ground again scales again (one scale per take-off).
 *
 * Logged: "jump-nose: factor F, site patched" at apply; the first 8 scalings (rate before -> after, in rad/s); nothing else.
 */
static float g_jn_factor;
static volatile LONG g_jn_scaled, g_jn_logged;

static void __cdecl jn_first_air(float *copy, BYTE *ent) {
    DWORD flags = *(DWORD *)(ent + EF(0x454));
    float *rates = (float *)(ent + 0xc8);
    float before = rates[0];
    if (flags & 0x4) return;                       /* airborne on the previous step too: already scaled */
    if (!(before < 0.0f)) return;                  /* nose-up or level: not the held nose-dive */
    rates[0] = before * g_jn_factor;
    copy[0] = rates[0];
    InterlockedIncrement(&g_jn_scaled);
    if (g_jn_logged < 8) { InterlockedIncrement(&g_jn_logged); mlog("jump-nose: first airborne step, pitch rate %.4f -> %.4f rad/s (x %.2f)", before, rates[0], g_jn_factor); }
}
static __declspec(naked) void jn_copy_stub(void) {        /* in place of the 19-byte rates copy at 0x43a7f5; eax = copy, edx = &rates, ebp = ent */
    __asm {
        mov ecx, [edx]
        mov [eax], ecx
        mov ecx, [edx + 4]
        mov [eax + 4], ecx
        mov ecx, [edx + 8]
        mov [eax + 8], ecx
        pushad
        push ebp
        push eax
        call jn_first_air
        add esp, 8
        popad
        ret
    }
}
static void apply_jump_nose(void) {
    char buf[32];
    static const BYTE stock[19] = { 0x8b, 0x0a, 0x83, 0xc4, 0x0c, 0x89, 0x08, 0x8b, 0x4a, 0x04, 0x89, 0x48, 0x04, 0x8b, 0x52, 0x08, 0x89, 0x50, 0x08 };
    BYTE want[19] = { 0xE8, 0, 0, 0, 0, 0x83, 0xc4, 0x0c, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90, 0x90 };
    LONG rel;
    double f;
    if (!env_str("I76_JUMP_NOSE", buf, sizeof(buf))) return;
    f = atof(buf);
    if (!(f >= 0.5 && f <= 1.0)) { mlog("jump-nose: I76_JUMP_NOSE=%s out of range (0.5..1.0): off", buf); return; }
    if (f == 1.0) { mlog("jump-nose: factor 1.00 = stock: off"); return; }
    g_jn_factor = (float)f;
    rel = (LONG)((DWORD_PTR)jn_copy_stub - (0x0043a7f5 + 5));    /* Gold-relative; nitro_patch_bytes re-aims a leading E8 */
    memcpy(want + 1, &rel, 4);
    if (!patch_bytes(0x0043a7f5, stock, want, 19, "jump-nose airborne rates copy")) { mlog("jump-nose: site 0x43a7f5 not stock: off"); return; }
    mlog("jump-nose: factor %.2f, site 0x43a7f5 patched (the held nose-down pitch rate x %.2f once on the first airborne step)", f, f);
}
