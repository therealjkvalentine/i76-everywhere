/* ===========================================================================
 * CURSOR MAP, WIDE MENU  (I76_CURSOR_MAP_DGV=aw, with I76_CURSOR_MAP and I76_CURSOR_MAP_U32X=exe; 2026-10-19)
 * ===========================================================================
 * Included from cursormap.c (after its map helpers).
 *
 * THE LOOK THE OWNER WANTS. The daily driver's wide conf (dccd379a) has [DirectX] Resolution = 1680x1050 under
 * [General] ScalingMode = stretched_ar: dgVoodoo first stretches the 640x480 menus / garage / save screen / movies to
 * 1680x1050 and then fits THAT (16:10) into the 3440x1440 window, so the menu picture is 2304x1440 at x 568..2871,
 * wider than 4:3 (owner 2026-10-19: "i like the menu aspect ratio from the daily driver"). Three readers have to
 * agree on that picture for the pointer to work, and under the driver's presets none of them uses it:
 *
 *   - dgVoodoo's pencil: drawn at picture origin + 3.6 x (what dgVoodoo's GetCursorPos returns); fed the stretched
 *     map (=1) it lands at 568 + 0.67 x (measured: 242 px off at the 12 % insets, CURSOR-FIX-ON-18 s.3a);
 *   - the shell's hit-test: u32x maps i76shell's pointer over the 4:3 fit of the client (760..2680) whatever the
 *     [DirectX] Resolution, so the button that answers is drawn at 568 + 1.2 (x - 760), up to ~190 px off;
 *   - the OS arrow, where the pointer really is.
 * The tick conf (aa6414e4, [DirectX] Resolution 1920x1440) fixes it by making the picture the 4:3 fit, which is the
 * one u32x already assumes, and I76_CURSOR_MAP_DGV=ar feeds dgVoodoo the same map.
 *
 * THIS MODE keeps the wide picture and moves the two maps onto it instead:
 *   1. dgVoodoo's slots (cursormap.c cm_GetCursorPos_dgv / cm_GetCursorInfo_dgv) get map mode 3: the 640x480 page
 *      over the fit of the picture aspect (x and y scaled separately);
 *   2. u32x keeps the shell (its modal arrow in the garage / reminder OK popups and its pumps stay), but its own
 *      USER32 imports are put behind an adapter that converts between the real picture and the 4:3 picture u32x
 *      believes in: GetCursorPos (real -> 4:3), SetCursorPos / ClipCursor (4:3 -> real), PeekMessageA mouse lParams
 *      (real -> 4:3, client coordinates) and SetWindowPos of its arrow window (class u32xVptr, 4:3 -> real).
 *      u32x's 4:3 map of the adapted point is then exactly the picture map: UI = (x - 568) / 3.6 on 3440x1440.
 *   3. i76.exe's slots keep I76_CURSOR_MAP's stretched map (the in-mission Esc menu over the full-width Glide frame).
 *
 * The picture aspect: I76_CURSOR_MAP_ASPECT=W:H (or WxH) if set; else dgVoodoo.conf next to the exe (the file
 * PLAY.bat / PLAY-balanced.bat copy the wide conf over at every start): [General] ScalingMode = stretched -> the whole
 * client; otherwise [DirectX] Resolution WxH -> W:H; otherwise 4:3 (then mode 3 is the same as =ar). Read once.
 * With a 4:3 aspect the adapter is the identity and is not installed. Off unless I76_CURSOR_MAP_DGV=aw. */
static double g_aw_w, g_aw_h;          /* picture aspect; 0 = fill the client (ScalingMode = stretched) */
static int    g_aw_read;

static void cm_aw_read_aspect(void) {
    char v[64], sm[32], path[MAX_PATH], *slash; int a = 0, b = 0; DWORD n;
    if (g_aw_read) return;
    g_aw_read = 1; g_aw_w = 4.0; g_aw_h = 3.0;
    n = env_str("I76_CURSOR_MAP_ASPECT", v, sizeof(v));
    if (n && (sscanf(v, "%d:%d", &a, &b) == 2 || sscanf(v, "%dx%d", &a, &b) == 2) && a > 0 && b > 0) {
        g_aw_w = a; g_aw_h = b;
        mlog("  cursor-map: aw picture aspect %d:%d (I76_CURSOR_MAP_ASPECT)", a, b);
        return;
    }
    n = GetModuleFileNameA(NULL, path, MAX_PATH - 16);
    slash = (n > 0 && n < MAX_PATH - 16) ? strrchr(path, '\\') : NULL;
    if (!slash) { mlog("  cursor-map: aw picture aspect 4:3 (no exe path)"); return; }
    lstrcpyA(slash + 1, "dgVoodoo.conf");
    GetPrivateProfileStringA("General", "ScalingMode", "", sm, sizeof(sm), path);
    if (lstrcmpiA(sm, "stretched") == 0) {
        g_aw_w = g_aw_h = 0.0;
        mlog("  cursor-map: aw picture = the whole client (%s ScalingMode = stretched)", path);
        return;
    }
    GetPrivateProfileStringA("DirectX", "Resolution", "", v, sizeof(v), path);
    if (sscanf(v, "%dx%d", &a, &b) == 2 && a > 0 && b > 0) { g_aw_w = a; g_aw_h = b; }
    mlog("  cursor-map: aw picture aspect %g:%g (%s [DirectX] Resolution '%s', ScalingMode '%s')",
         g_aw_w, g_aw_h, path, v, sm);
}

/* map mode 3 (cm_map_mode): rc = client, org = its screen origin; fills m like mode 1 / 2 do */
static void cm_aw_fit(CmMap *m, const RECT *rc, POINT org) {
    double fw, fh, s;
    cm_aw_read_aspect();
    m->ox = org.x; m->oy = org.y;
    if (g_aw_w <= 0.0 || g_aw_h <= 0.0) { m->kx = rc->right / 640.0; m->ky = rc->bottom / 480.0; return; }
    s  = (rc->right / g_aw_w < rc->bottom / g_aw_h) ? rc->right / g_aw_w : rc->bottom / g_aw_h;
    fw = g_aw_w * s; fh = g_aw_h * s;
    m->kx = fw / 640.0; m->ky = fh / 480.0;
    m->ox += (int)((rc->right - fw) / 2.0); m->oy += (int)((rc->bottom - fh) / 2.0);
}

/* ---- the u32x adapter: real picture (mode 3) <-> the 4:3 picture u32x maps over (mode 2) ---- */
static BOOL (WINAPI *p_aw_GetCursorPos)(LPPOINT);
static BOOL (WINAPI *p_aw_SetCursorPos)(int, int);
static BOOL (WINAPI *p_aw_ClipCursor)(const RECT *);
static BOOL (WINAPI *p_aw_PeekMessageA)(LPMSG, HWND, UINT, UINT, UINT);
static BOOL (WINAPI *p_aw_SetWindowPos)(HWND, HWND, int, int, int, int, UINT);
static int g_aw_log;                   /* the first translations, for the record */

/* to43 = 1: a real screen point -> the 4:3 picture; 0: back. Returns 0 (point untouched) with no window yet. */
static int cm_aw_xform(double *x, double *y, int to43) {
    CmMap a = cm_map_mode(3), f = cm_map_mode(2);
    if (!a.on || !f.on) return 0;
    if (to43) { *x = f.ox + (*x - a.ox) * f.kx / a.kx; *y = f.oy + (*y - a.oy) * f.ky / a.ky; }
    else      { *x = a.ox + (*x - f.ox) * a.kx / f.kx; *y = a.oy + (*y - f.oy) * a.ky / f.ky; }
    return 1;
}
static LONG cm_aw_round(double v) { return (LONG)(v < 0 ? v - 0.5 : v + 0.5); }

static BOOL WINAPI aw_GetCursorPos(LPPOINT p) {
    BOOL ok = p_aw_GetCursorPos(p);
    if (ok && p) {
        double x = p->x, y = p->y; POINT raw = *p;
        if (cm_aw_xform(&x, &y, 1)) { p->x = cm_aw_round(x); p->y = cm_aw_round(y); }
        if (g_aw_log < 12 && (raw.x != p->x || raw.y != p->y)) {
            g_aw_log++; mlog("  cursor-map: aw u32x GetCursorPos (%ld,%ld) -> 4:3 (%ld,%ld)", raw.x, raw.y, p->x, p->y);
        }
    }
    return ok;
}
static BOOL WINAPI aw_SetCursorPos(int x, int y) {
    double fx = x, fy = y;
    if (cm_aw_xform(&fx, &fy, 0)) return p_aw_SetCursorPos((int)cm_aw_round(fx), (int)cm_aw_round(fy));
    return p_aw_SetCursorPos(x, y);
}
static BOOL WINAPI aw_ClipCursor(const RECT *r) {
    CmMap f = cm_map_mode(2);
    /* only a rect u32x mapped onto its 4:3 picture; a release or a screen-sized rect passes through */
    if (r && f.on && r->left >= f.ox - 1 && r->right <= f.ox + (LONG)(640 * f.kx + 0.5) + 1
        && r->top >= f.oy - 1 && r->bottom <= f.oy + (LONG)(480 * f.ky + 0.5) + 1) {
        double l = r->left, t = r->top, rr = r->right, b = r->bottom; RECT s;
        if (cm_aw_xform(&l, &t, 0) && cm_aw_xform(&rr, &b, 0)) {
            s.left = cm_aw_round(l); s.top = cm_aw_round(t); s.right = cm_aw_round(rr); s.bottom = cm_aw_round(b);
            return p_aw_ClipCursor(&s);
        }
    }
    return p_aw_ClipCursor(r);
}
static BOOL WINAPI aw_PeekMessageA(LPMSG msg, HWND hw, UINT lo, UINT hi, UINT rm) {
    BOOL ok = p_aw_PeekMessageA(msg, hw, lo, hi, rm);
    if (ok && msg && msg->hwnd && msg->message >= WM_MOUSEFIRST && msg->message <= WM_MOUSELAST
        && msg->message != WM_MOUSEWHEEL) {               /* the wheel's lParam is screen coordinates already */
        HWND gw = cm_window();
        if (gw && (msg->hwnd == gw || IsChild(gw, msg->hwnd))) {
            POINT p; double x, y;
            p.x = (short)LOWORD(msg->lParam); p.y = (short)HIWORD(msg->lParam);
            ClientToScreen(msg->hwnd, &p); x = p.x; y = p.y;
            if (cm_aw_xform(&x, &y, 1)) {
                p.x = cm_aw_round(x); p.y = cm_aw_round(y);
                ScreenToClient(msg->hwnd, &p);
                msg->lParam = MAKELPARAM((WORD)(short)p.x, (WORD)(short)p.y);
            }
        }
    }
    return ok;
}
static BOOL WINAPI aw_SetWindowPos(HWND h, HWND after, int x, int y, int cx, int cy, UINT fl) {
    char cls[16];
    if (!(fl & SWP_NOMOVE) && GetClassNameA(h, cls, sizeof(cls)) && lstrcmpA(cls, "u32xVptr") == 0) {
        double fx = x, fy = y;                         /* u32x's modal arrow, placed on its 4:3 picture */
        if (cm_aw_xform(&fx, &fy, 0)) { x = (int)cm_aw_round(fx); y = (int)cm_aw_round(fy); }
    }
    return p_aw_SetWindowPos(h, after, x, y, cx, cy, fl);
}

/* from apply_cursor_map, I76_CURSOR_MAP_DGV=aw and the shell left with u32x (I76_CURSOR_MAP_U32X=exe) */
static void cm_aw_u32x_install(void) {
    HMODULE u = GetModuleHandleA("u32x.dll"), u32 = GetModuleHandleA("user32.dll");
    int n = 0;
    cm_aw_read_aspect();
    if (!u) { mlog("  cursor-map: aw: u32x.dll not loaded - no adapter"); return; }
    if (g_aw_w > 0.0 && g_aw_h > 0.0 && g_aw_w * 3.0 == g_aw_h * 4.0) { mlog("  cursor-map: aw: 4:3 picture - no adapter needed"); return; }
    /* the real functions, as cursormap.c does: a slot already taken by someone else is bypassed, not chained */
    p_aw_GetCursorPos = (BOOL (WINAPI *)(LPPOINT))GetProcAddress(u32, "GetCursorPos");
    p_aw_SetCursorPos = (BOOL (WINAPI *)(int, int))GetProcAddress(u32, "SetCursorPos");
    p_aw_ClipCursor   = (BOOL (WINAPI *)(const RECT *))GetProcAddress(u32, "ClipCursor");
    p_aw_PeekMessageA = (BOOL (WINAPI *)(LPMSG, HWND, UINT, UINT, UINT))GetProcAddress(u32, "PeekMessageA");
    p_aw_SetWindowPos = (BOOL (WINAPI *)(HWND, HWND, int, int, int, int, UINT))GetProcAddress(u32, "SetWindowPos");
    if (patch_iat(u, "USER32.dll", "GetCursorPos", aw_GetCursorPos) != NULL) n++;
    if (patch_iat(u, "USER32.dll", "SetCursorPos", aw_SetCursorPos) != NULL) n++;
    if (patch_iat(u, "USER32.dll", "ClipCursor", aw_ClipCursor) != NULL) n++;
    if (patch_iat(u, "USER32.dll", "PeekMessageA", aw_PeekMessageA) != NULL) n++;
    if (patch_iat(u, "USER32.dll", "SetWindowPos", aw_SetWindowPos) != NULL) n++;
    mlog("  cursor-map: aw: u32x.dll %d/5 USER32 slots behind the picture adapter (4:3 <-> %g:%g)", n, g_aw_w, g_aw_h);
}
