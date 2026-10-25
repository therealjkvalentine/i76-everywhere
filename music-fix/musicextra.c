/* musicextra.c - I76_MUSIC_EXTRA=<folder>: shuffle the owner's own extra music in with the game's tracks (content-installer
 * lane 2026-10-25, docs/records/CONTENT-INSTALLER-2026-10-25.md; owner ruling 4: the unreleased Bullmark demo tracks and the
 * soundtrack-only cues, PRIVATE use - nothing is downloaded or shipped; the folder is the user's own).
 *
 * How: the virtual disc stays exactly as it is (tracks 2..17 = music\N.mp3, the TOC and every length the exe asks for are
 * the game's own), so mission runs, resume, pause and the gapless advance behave as before. Only the FILE a song start opens
 * changes: every Nth time play_track() opens a new song (N = I76_MUSIC_EXTRA_EVERY, default 3; 1 = every song) it opens the
 * next file of the extra folder's shuffle instead. The run logic keeps the logical track number, so when the extra song
 * ends the run continues with the next game track, as if the extra had been that track.
 *
 *   I76_MUSIC_EXTRA=<folder>       .mp3 / .wav files in the folder and its direct sub-folders (absolute, or relative to
 *                                  the game folder); unset, empty, "0" or "off" = off
 *   I76_MUSIC_EXTRA_EVERY=<n>      1..20, default 3: one song start in n plays an extra
 * The shuffle is a bag: every extra file plays once before any repeats, re-shuffled each round (seeded from the clock).
 * Log: "music-extra: ..." once at the first song start (folder, count, n), then "music-extra: track T -> <file>" per extra. */

static int  mx_state = -1;           /* -1 not read yet, 0 off, 1 on */
static char (*mx_files)[MAX_PATH];
static int  mx_n, mx_cap, mx_every = 3, mx_pos, mx_starts;
static int *mx_bag;
static unsigned mx_rng;

static unsigned mx_rand(void) { mx_rng = mx_rng * 1103515245u + 12345u; return (mx_rng >> 16) & 0x7fff; }

static void mx_scan(const char *dir, int depth) {
    char p[MAX_PATH]; WIN32_FIND_DATAA w; HANDLE h;
    _snprintf(p, sizeof p, "%s\\*", dir); p[sizeof p - 1] = 0;
    h = FindFirstFileA(p, &w);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        const char *x;
        if (w.cFileName[0] == '.') continue;
        if (w.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) {
            if (depth < 1) { char sub[MAX_PATH]; _snprintf(sub, sizeof sub, "%s\\%s", dir, w.cFileName); sub[sizeof sub - 1] = 0; mx_scan(sub, depth + 1); }
            continue;
        }
        x = strrchr(w.cFileName, '.');
        if (!x || (_stricmp(x, ".mp3") && _stricmp(x, ".wav"))) continue;
        if (mx_n == mx_cap) {
            int nc = mx_cap ? mx_cap * 2 : 64; char (*nf)[MAX_PATH] = realloc(mx_files, nc * MAX_PATH);
            if (!nf) break;
            mx_files = nf; mx_cap = nc;
        }
        _snprintf(mx_files[mx_n], MAX_PATH, "%s\\%s", dir, w.cFileName); mx_files[mx_n][MAX_PATH - 1] = 0;
        if (strchr(mx_files[mx_n], '"')) continue;     /* MCI string: no quotes inside a quoted path */
        mx_n++;
    } while (FindNextFileA(h, &w));
    FindClose(h);
}

static void mx_shuffle(void) {
    int i;
    for (i = 0; i < mx_n; i++) mx_bag[i] = i;
    for (i = mx_n - 1; i > 0; i--) { int j = (int)(mx_rand() % (unsigned)(i + 1)), t = mx_bag[i]; mx_bag[i] = mx_bag[j]; mx_bag[j] = t; }
    mx_pos = 0;
}

static void mx_init(void) {
    char v[MAX_PATH], dir[MAX_PATH];
    mx_state = 0;
    if (!env_str("I76_MUSIC_EXTRA", v, sizeof v) || !strcmp(v, "0") || !_stricmp(v, "off")) return;
    if (v[0] && (v[1] == ':' || (v[0] == '\\' && v[1] == '\\'))) lstrcpynA(dir, v, sizeof dir);
    else _snprintf(dir, sizeof dir, "%s\\%s", g_dir, v);
    dir[sizeof dir - 1] = 0;
    { size_t L = strlen(dir); while (L && (dir[L - 1] == '\\' || dir[L - 1] == '/')) dir[--L] = 0; }
    mx_every = env_int("I76_MUSIC_EXTRA_EVERY", 8, 3);
    if (mx_every < 1) mx_every = 1;
    if (mx_every > 20) mx_every = 20;
    mx_scan(dir, 0);
    if (!mx_n) { flog("music-extra: I76_MUSIC_EXTRA=%s but %s holds no .mp3 / .wav - the game's tracks only", v, dir); return; }
    mx_bag = (int *)malloc(mx_n * sizeof(int));
    if (!mx_bag) { mx_n = 0; return; }
    mx_rng = GetTickCount() ^ (GetCurrentProcessId() << 16);
    mx_shuffle();
    mx_state = 1;
    flog("music-extra: %d extra songs in %s shuffled in, one song start in %d (I76_MUSIC_EXTRA_EVERY)", mx_n, dir, mx_every);
}

/* play_track's file choice: the extra file to open for this song start, or NULL for the game's own music\N.mp3 */
static const char *mx_pick(int track) {
    const char *f;
    if (mx_state < 0) mx_init();
    if (mx_state != 1) return NULL;
    mx_starts++;
    if (mx_starts % mx_every) return NULL;
    if (mx_pos >= mx_n) mx_shuffle();
    f = mx_files[mx_bag[mx_pos++]];
    mlog("music-extra: track %d -> %s (song start %d, extra %d of %d this round)", track, f, mx_starts, mx_pos, mx_n);
    return f;
}
