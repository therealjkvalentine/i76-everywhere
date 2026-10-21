/* nitro.c - which exe loaded us, and the Gold -> Nitro site map at run time (nitro-port lane, 2026-10-21).
 * Record: docs/records/NITRO-PORT-2026-10-21.md. Included by strlkproxy.c right after the logging helpers.
 *
 * EXE DETECTION. DllMain calls exe_detect() first. Nitro = PE stamp 0x351c24ce AND the crc32 of .text equal to the one
 * gen_sites.py took from nitro.exe 28b8ae27 (so a patched or other Nitro build is NOT treated as this one). Gold = PE stamp
 * 0x34ecb06c (GOG 9a232dcc, AiO 60abf7bc, ours 6319abf7 all carry it). Anything else = "other", which takes the Gold path
 * exactly as before this file existed (every Gold site is byte-verified there, so an unknown build is left alone).
 *
 * THE GOLD PATH IS UNCHANGED. On Gold (and other) g_exe != EXE_NITRO, so na_() returns its argument and patch_bytes()
 * never reaches nitro_patch_bytes(). Nitro takes its own DllMain sequence (nitro_dllmain, at the end of strlkproxy.c)
 * that calls only the apply_* functions ported so far.
 *
 * SITES. Proxy code names Gold addresses. On Nitro:
 *   - patch_bytes(gold_va, expect, want, n, what) is redirected here: the site is looked up in sites_nitro.h, and
 *       * the caller expects the pristine Gold bytes (expect == the table's Gold bytes): memory at the Nitro address must
 *         equal the table's Nitro bytes, and n must not exceed `ok` (the bytes the generator found to be the same
 *         instructions in both exes up to relocation);
 *       * otherwise (a chained patch expecting an earlier patch of ours) the expect bytes are relocated like want, then
 *         compared with memory;
 *       * want is relocated: a leading E8 / E9 rel32 is re-aimed (an exe target is translated through the table, a
 *         proxy target is kept); any other dword in the exe's range makes the patch refuse (it needs a hand port).
 *     Any failure logs "site <what> (gold 0x..): <reason>, feature off" and returns 0, which every caller already
 *     treats as "not patched".
 *   - NA(gold) gives the Nitro address of a data / code address for reads, calls and computed jumps (0 = unmapped);
 *     nrd32(gold) is a read that answers 0 for an unmapped address.
 *   - Entity fields at and above +0x444 moved 4 bytes in Nitro (the entity grew; NITRO-VS-RETAIL s.2.1): EF(off).
 */
#include "sites_nitro.h"

#define EXE_OTHER 0
#define EXE_GOLD  1
#define EXE_NITRO 2
static int g_exe = EXE_OTHER;
static const char *g_exe_name = "other";

static DWORD crc32_buf(const BYTE *p, DWORD n) {
    DWORD c = 0xffffffffu, k; int b;
    for (k = 0; k < n; k++) { c ^= p[k]; for (b = 0; b < 8; b++) c = (c >> 1) ^ (0xedb88320u & (0u - (c & 1u))); }
    return ~c;
}
static void exe_detect(void) {
    BYTE *base = (BYTE *)GetModuleHandleA(NULL);
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)(base + ((IMAGE_DOS_HEADER *)base)->e_lfanew);
    DWORD stamp = nt->FileHeader.TimeDateStamp;
    if (stamp == NITRO_PE_STAMP && nt->OptionalHeader.SizeOfImage >= 0x1000 + NITRO_TEXT_SIZE) {
        DWORD crc = crc32_buf(base + 0x1000, NITRO_TEXT_SIZE);
        if (crc == NITRO_TEXT_CRC32) { g_exe = EXE_NITRO; g_exe_name = "nitro 28b8ae27"; }
        else { g_exe = EXE_OTHER; g_exe_name = "nitro stamp, unknown .text"; }
    } else if (stamp == GOLD_PE_STAMP) { g_exe = EXE_GOLD; g_exe_name = "gold"; }
}

static const nitro_site_t *nsite_find(DWORD gold) {
    int lo = 0, hi = NITRO_SITE_COUNT - 1;
    while (lo <= hi) {
        int m = (lo + hi) / 2;
        if (g_nitro_sites[m].gold == gold) return &g_nitro_sites[m];
        if (g_nitro_sites[m].gold < gold) lo = m + 1; else hi = m - 1;
    }
    return 0;
}
static DWORD na_(DWORD gold) {
    const nitro_site_t *s;
    if (g_exe != EXE_NITRO) return gold;
    s = nsite_find(gold);
    return s ? s->nitro : 0;
}
#define NA(x) na_((DWORD)(x))
static DWORD nrd32(DWORD gold) { DWORD a = na_(gold); return a ? *(volatile DWORD *)(DWORD_PTR)a : 0; }
/* entity field offset: +4 at and above +0x444 on Nitro */
#define EF(off) ((g_exe == EXE_NITRO && (off) >= 0x444) ? (off) + 4 : (off))

#define GOLD_IMG_LO 0x00400000u
#define GOLD_IMG_HI 0x0066b000u

/* relocate a patch's bytes from the Gold site to the Nitro site; 0 = cannot (an exe address the table does not know) */
static int nitro_reloc(DWORD gold, DWORD nva, const BYTE *in, BYTE *out, SIZE_T n, const char **why) {
    SIZE_T i, from = 0;
    memcpy(out, in, n);
    if (n >= 5 && (in[0] == 0xE8 || in[0] == 0xE9)) {
        LONG rel; DWORD t, t2;
        memcpy(&rel, in + 1, 4);
        t = gold + 5 + (DWORD)rel;
        if (t >= GOLD_IMG_LO && t < GOLD_IMG_HI) {
            t2 = na_(t);
            if (!t2) { *why = "call / jmp target has no Nitro address"; return 0; }
        } else t2 = t;
        rel = (LONG)(t2 - (nva + 5)); memcpy(out + 1, &rel, 4);
        from = 5;
    }
    for (i = from; i + 4 <= n; i++) {       /* only a dword that IS a mapped Gold address is translated; any other value (a
                                               size such as 0x400000, opcode bytes run into a pointer) is a literal */
        DWORD d, d2; memcpy(&d, in + i, 4);
        if (d >= GOLD_IMG_LO && d < GOLD_IMG_HI && nsite_find(d) && (d2 = na_(d)) != 0) { memcpy(out + i, &d2, 4); i += 3; }
    }
    (void)why;
    return 1;
}

static LONG g_nsite_ok, g_nsite_refused;
static int nitro_patch_bytes(DWORD gold, const BYTE *expect, const BYTE *want, SIZE_T n, const char *what) {
    const nitro_site_t *s = nsite_find(gold);
    BYTE e2[64], w2[64]; const char *why = ""; DWORD old; BYTE *p;
    if (n > sizeof(w2)) { why = "patch too long"; goto refuse; }
    if (!s || !s->nitro) { why = "no Nitro address"; goto refuse; }
    p = (BYTE *)(DWORD_PTR)s->nitro;
    if (s->len && n <= s->len && memcmp(expect, s->gsig, n) == 0) {      /* the caller expects Gold's pristine bytes */
        if (n > s->ok) { why = "Gold and Nitro instructions differ inside the patch window (signature mismatch)"; goto refuse; }
        if (memcmp(p, s->sig, n) != 0) { why = "signature mismatch (memory is not the mapped Nitro bytes)"; goto refuse; }
    } else if (s->len == 0 && s->status >= SN_VOTED) {                   /* a data site: relocate the expected bytes */
        if (!nitro_reloc(gold, s->nitro, expect, e2, n, &why)) goto refuse;
        if (memcmp(p, e2, n) != 0) { why = "data signature mismatch"; goto refuse; }
    } else {                                                              /* chained: expects an earlier patch of ours */
        if (!nitro_reloc(gold, s->nitro, expect, e2, n, &why)) goto refuse;
        if (memcmp(p, e2, n) != 0) { why = "signature mismatch (neither the mapped Nitro bytes nor our earlier patch)"; goto refuse; }
    }
    if (s->len && n <= s->len && memcmp(expect, s->gsig, n) == 0) {
        /* pristine site: every byte the patch keeps from Gold's instruction comes from Nitro's (operands, branch
         * displacements: Gold's `je +0x1c` is Nitro's `je +0x31`, so `74 1c -> eb 1c` becomes `eb 31`); a leading
         * E8 / E9 rel32 the patch changes is re-aimed; any other changed dword in the exe's range is translated */
        SIZE_T i, from = 0;
        memcpy(w2, want, n);
        if (n >= 5 && (want[0] == 0xE8 || want[0] == 0xE9) && memcmp(want + 1, s->gsig + 1, 4) != 0) {
            if (!nitro_reloc(gold, s->nitro, want, w2, 5, &why)) goto refuse;
            from = 5;
        }
        for (i = from; i < n; i++) if (want[i] == s->gsig[i]) w2[i] = s->sig[i];
        for (i = from; i + 4 <= n; i++) {   /* a changed operand that names another mapped Gold address (e.g. a call [IAT]
                                               re-aimed at another import); every other changed byte is the patch's own */
            DWORD d, d2; memcpy(&d, want + i, 4);
            if (memcmp(want + i, s->gsig + i, 4) != 0 && d >= GOLD_IMG_LO && d < GOLD_IMG_HI && nsite_find(d) && (d2 = na_(d)) != 0) {
                memcpy(w2 + i, &d2, 4); i += 3;
            }
        }
    } else if (!nitro_reloc(gold, s->nitro, want, w2, n, &why)) goto refuse;
    if (!VirtualProtect(p, n, PAGE_EXECUTE_READWRITE, &old)) { why = "VirtualProtect failed"; goto refuse; }
    memcpy(p, w2, n);
    VirtualProtect(p, n, old, &old);
    if (memcmp(p, w2, n) != 0) { why = "read-back failed"; goto refuse; }
    InterlockedIncrement(&g_nsite_ok);
    mlog("  nitro site %s: gold 0x%06lX -> nitro 0x%06lX, %u bytes, signature ok, patched", what, (unsigned long)gold,
         (unsigned long)s->nitro, (unsigned)n);
    return 1;
refuse:
    InterlockedIncrement(&g_nsite_refused);
    mlog("  site %s (gold 0x%06lX -> nitro 0x%06lX): %s, feature off", what, (unsigned long)gold,
         (unsigned long)(s ? s->nitro : 0), why);
    return 0;
}

/* every address a feature needs at run time (reads, calls), checked before the feature is switched on */
static int nitro_need(const char *feature, const DWORD *gold, int n) {
    int i, bad = 0;
    if (g_exe != EXE_NITRO) return 1;
    for (i = 0; i < n; i++) {
        const nitro_site_t *s = nsite_find(gold[i]);
        if (!s || !s->nitro) { mlog("  site %s (gold 0x%06lX): no Nitro address, feature off", feature, (unsigned long)gold[i]); bad++; }
        else if (s->len && memcmp((void *)(DWORD_PTR)s->nitro, s->sig, s->len) != 0) {
            mlog("  site %s (gold 0x%06lX -> nitro 0x%06lX): signature mismatch, feature off", feature, (unsigned long)gold[i], (unsigned long)s->nitro); bad++;
        }
    }
    return bad == 0;
}

/* one log line: how many table code sites match memory (the build check), at DllMain */
static void nitro_table_check(void) {
    int i, code = 0, match = 0, data = 0, unm = 0;
    for (i = 0; i < NITRO_SITE_COUNT; i++) {
        const nitro_site_t *s = &g_nitro_sites[i];
        if (!s->nitro) { unm++; continue; }
        if (!s->len) { data++; continue; }
        code++;
        if (memcmp((void *)(DWORD_PTR)s->nitro, s->sig, s->len) == 0) match++;
    }
    mlog("nitro: site table %d rows: %d code sites, %d match memory; %d data; %d unmapped", NITRO_SITE_COUNT, code, match, data, unm);
}

/* site_is(gold, expect, n): "the running exe holds what the Gold code expects at this site". Gold / other: memcmp at the
 * Gold address, exactly as before. Nitro: the caller's pristine Gold bytes -> memory must be the table's Nitro bytes and n
 * within the window both exes share; anything else (an earlier patch of ours) -> the bytes relocated as patch_bytes does. */
static int site_is(DWORD gold, const BYTE *expect, SIZE_T n) {
    const nitro_site_t *s; BYTE e2[64]; const char *why = "";
    if (g_exe != EXE_NITRO) return memcmp((const void *)(DWORD_PTR)gold, expect, n) == 0;
    s = nsite_find(gold);
    if (!s || !s->nitro || n > sizeof(e2)) return 0;
    if (s->len && n <= s->len && memcmp(expect, s->gsig, n) == 0)
        return n <= s->ok && memcmp((const void *)(DWORD_PTR)s->nitro, s->sig, n) == 0;
    return nitro_reloc(gold, s->nitro, expect, e2, n, &why) && memcmp((const void *)(DWORD_PTR)s->nitro, e2, n) == 0;
}

/* Our naked asm stubs name exe addresses as immediates / displacements. On Nitro each listed Gold address found in the stub's
 * first `span` bytes is rewritten to its Nitro address (our own code, VirtualProtect). Every listed address must be mapped and
 * found at least once, else nothing is written and 0 is returned (the caller leaves its feature off). Gold: returns 1. */
static int nitro_reloc_stub(void *fn, const DWORD *gold, int ng, int span, const char *what) {
    BYTE *p = (BYTE *)fn; DWORD old; int i, k, hits[16] = {0}, total = 0;
    if (g_exe != EXE_NITRO) return 1;
    if (p[0] == 0xE9) { LONG r; memcpy(&r, p + 1, 4); p = p + 5 + r; }    /* an incremental-link thunk */
    if (ng > 16) return 0;
    for (i = 0; i < ng; i++) if (!na_(gold[i])) { mlog("  site %s (gold 0x%06lX): no Nitro address for the stub, feature off", what, (unsigned long)gold[i]); return 0; }
    for (k = 0; k + 4 <= span; k++) for (i = 0; i < ng; i++) { DWORD d; memcpy(&d, p + k, 4); if (d == gold[i]) hits[i]++; }
    for (i = 0; i < ng; i++) if (!hits[i]) { mlog("  site %s: stub does not hold gold 0x%06lX, feature off", what, (unsigned long)gold[i]); return 0; }
    if (!VirtualProtect(p, span, PAGE_EXECUTE_READWRITE, &old)) return 0;
    for (k = 0; k + 4 <= span; k++) for (i = 0; i < ng; i++) {
        DWORD d; memcpy(&d, p + k, 4);
        if (d == gold[i]) { DWORD n2 = na_(gold[i]); memcpy(p + k, &n2, 4); total++; k += 3; break; }
    }
    VirtualProtect(p, span, old, &old);
    FlushInstructionCache(GetCurrentProcess(), p, span);
    mlog("  nitro stub %s: %d address(es) relocated", what, total);
    return 1;
}

/* A call site that exists only in nitro.exe (no Gold counterpart): `call rel32` at nitro_va must target expect_target (a Nitro
 * address) or, chained, a wrapper of ours; it is repointed at wrap and *chain gets the target it held. Nitro only. */
static int nitro_patch_call(DWORD nitro_va, DWORD expect_target, void *wrap, DWORD *chain, const char *what) {
    BYTE *p = (BYTE *)(DWORD_PTR)nitro_va, w[5] = { 0xE8 }; LONG rel; DWORD tgt, old;
    if (g_exe != EXE_NITRO) return 0;
    if (p[0] != 0xE8) { mlog("  site %s (nitro 0x%06lX): not a call, feature off", what, (unsigned long)nitro_va); return 0; }
    memcpy(&rel, p + 1, 4); tgt = nitro_va + 5 + (DWORD)rel;
    if (tgt != expect_target) { mlog("  site %s (nitro 0x%06lX): calls 0x%08lX, not 0x%06lX - signature mismatch, feature off", what, (unsigned long)nitro_va, (unsigned long)tgt, (unsigned long)expect_target); return 0; }
    if (chain) *chain = tgt;
    rel = (LONG)((DWORD_PTR)wrap - (nitro_va + 5)); memcpy(w + 1, &rel, 4);
    if (!VirtualProtect(p, 5, PAGE_EXECUTE_READWRITE, &old)) return 0;
    memcpy(p, w, 5); VirtualProtect(p, 5, old, &old);
    if (memcmp(p, w, 5) != 0) return 0;
    InterlockedIncrement(&g_nsite_ok);
    mlog("  nitro-only site %s: 0x%06lX call 0x%06lX -> wrapper, patched", what, (unsigned long)nitro_va, (unsigned long)expect_target);
    return 1;
}
