/* dsndrumble.c — proxy dsound.dll: drive gamepad rumble from the sounds the
 * game ACTUALLY plays (the "based on the sound that's playing" backup path).
 *
 * The game plays every effect through DirectSound: it creates a secondary
 * buffer, Locks it, writes the .gpw PCM, Unlocks, and Play()s it. This proxy
 * sits in front of dsound.dll, wraps IDirectSound/IDirectSoundBuffer, captures
 * the PCM on Unlock, fingerprints it to a sound NAME (tools/gpw-fingerprints.py),
 * and on Play spins up a rumble "voice" that plays that sound's amplitude
 * envelope (tools/gpw-envelopes.py) on the pad — categorised to a motor by what
 * the sound is (weapons->buzz, explosions/impacts/tyres->heavy). A background
 * thread mixes active voices (MAX per motor) and drives XInput.
 *
 * This is the BACKUP to the force-feedback-data path (../ffb-shim/). The two
 * would fight over the motor, so this is NOT installed by default; install one
 * or the other. See README.md.
 *
 * Freestanding (no CRT). Forwards to the real dsound.dll (Wine builtin / system).
 * STATUS: builds; COM interception + fingerprint match are UNVERIFIED against
 * the live game (blind build) — the fingerprint uniqueness and envelope/voice
 * math are native-tested, the DirectSound wrapping is not. Experimental.
 */
#define CINTERFACE
#define COBJMACROS
#include <windows.h>
#include <dsound.h>

/* ================= envelopes (same table as the ffb-shim) ================= */
#define MAXENV 160
#define MAXLEN 96
typedef struct { char name[16]; unsigned char v[MAXLEN]; int len; } ENVELOPE;
static ENVELOPE g_env[MAXENV];
static int g_nenv;

/* ================= fingerprints (name -> len,hash,env,motor) ============== */
#define MAXFP 160
typedef struct { unsigned len, hash; int env; int motor; } FP;   /* motor 0=L 1=R 2=both */
static FP g_fp[MAXFP];
static int g_nfp;

/* ================= XInput (dynamic) ====================================== */
typedef struct { WORD l, r; } XVIB;
typedef DWORD (WINAPI *XSetFn)(DWORD, XVIB *);
typedef DWORD (WINAPI *XGetFn)(DWORD, void *);
static XSetFn xset;
static XGetFn xget;
static int g_pad = -1;

/* ================= voices (active sound-rumbles) ========================= */
#define MAXVOICE 24
typedef struct { int env, motor, active, looping; float pos; } VOICE;
static VOICE g_voice[MAXVOICE];
static CRITICAL_SECTION g_cs;
static HANDLE g_thread;
static volatile int g_run = 1;

static float cl01(float v){ return v<0?0:(v>1?1:v); }

/* ---- tiny freestanding file read ---- */
static long read_file(const char *path, char *buf, long max)
{
    HANDLE h = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ|FILE_SHARE_WRITE,
                           0, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
    DWORD got = 0;
    if (h == INVALID_HANDLE_VALUE) return -1;
    ReadFile(h, buf, (DWORD)max, &got, 0);
    CloseHandle(h);
    return got;
}

/* FNV-1a over every byte — MUST match tools/gpw-fingerprints.py */
static unsigned fnv1a(const unsigned char *p, unsigned n)
{
    unsigned h = 2166136261u, i;
    for (i = 0; i < n; i++) h = (h ^ p[i]) * 16777619u;
    return h;
}

static int find_env(const char *name)
{
    int i;
    for (i = 0; i < g_nenv; i++)
        if (lstrcmpiA(g_env[i].name, name) == 0) return i;
    return -1;
}

/* weapons -> buzz (right); explosions/impacts/tyres/vehicle -> heavy (left) */
static int motor_of(const char *n)
{
    char c = n[0];
    if (c == 'w') return 1;                 /* w* weapon fire */
    if (c == 'c') return 1;                 /* c* cockpit/UI clicks */
    if (c == 'x' || c == 'e') return 0;     /* x* explosion, e* impact */
    if (c == 't') return 0;                 /* t* tyre/skid */
    if (n[0]=='v'&&n[1]=='c'&&n[2]=='d') return 0;  /* vcd* surface loop */
    return 2;                                /* default: both */
}

static void parse_kv_ints(char *line, char *name, int nmax, int *ints, int imax, int *ni)
{
    char *eq = line, *q; int val = 0, have = 0;
    *ni = 0;
    while (*eq && *eq != '=') eq++;
    if (*eq != '=') { name[0] = 0; return; }
    *eq = 0; lstrcpynA(name, line, nmax);
    for (q = eq + 1; *q; q++) {
        if (*q >= '0' && *q <= '9') { val = val*10 + (*q-'0'); have = 1; }
        else if (*q == ',') { if (*ni < imax) ints[(*ni)++] = val; val = 0; have = 0; }
    }
    if (have && *ni < imax) ints[(*ni)++] = val;
}

static void load_tables(void)
{
    static char buf[131072];
    static const char *epaths[] = { "rumble-envelopes.ini", "C:\\AutoHotkey\\rumble-envelopes.ini", 0 };
    static const char *fpaths[] = { "rumble-fingerprints.ini", "C:\\AutoHotkey\\rumble-fingerprints.ini", 0 };
    long got; char *p; int i;

    for (i = 0, got = -1; epaths[i] && got < 0; i++) got = read_file(epaths[i], buf, sizeof(buf)-1);
    if (got > 0) {
        buf[got] = 0; p = buf;
        while (*p && g_nenv < MAXENV) {
            char *nl = p; int ints[MAXLEN], ni, k; char nm[16];
            while (*nl && *nl != '\n') nl++;
            if (*nl) *nl = 0;
            if (*p && *p != ';' && *p != '#' && *p != '\r') {
                parse_kv_ints(p, nm, 16, ints, MAXLEN, &ni);
                if (nm[0] && ni > 0) {
                    lstrcpynA(g_env[g_nenv].name, nm, 16);
                    for (k = 0; k < ni; k++) g_env[g_nenv].v[k] = (unsigned char)ints[k];
                    g_env[g_nenv].len = ni; g_nenv++;
                }
            }
            p = nl + 1;
        }
    }
    for (i = 0, got = -1; fpaths[i] && got < 0; i++) got = read_file(fpaths[i], buf, sizeof(buf)-1);
    if (got > 0) {
        buf[got] = 0; p = buf;
        while (*p && g_nfp < MAXFP) {
            char *nl = p; int ints[2], ni; char nm[16];
            while (*nl && *nl != '\n') nl++;
            if (*nl) *nl = 0;
            if (*p && *p != ';' && *p != '#' && *p != '\r') {
                parse_kv_ints(p, nm, 16, ints, 2, &ni);
                if (nm[0] && ni == 2) {
                    g_fp[g_nfp].len = (unsigned)ints[0];
                    g_fp[g_nfp].hash = (unsigned)ints[1];
                    g_fp[g_nfp].env = find_env(nm);
                    g_fp[g_nfp].motor = motor_of(nm);
                    g_nfp++;
                }
            }
            p = nl + 1;
        }
    }
}

static int match_fp(unsigned len, unsigned hash)
{
    int i;
    for (i = 0; i < g_nfp; i++)
        if (g_fp[i].len == len && g_fp[i].hash == hash) return i;
    return -1;
}

static int find_pad(void)
{
    unsigned char st[16]; int i;
    if (!xget) return 0;
    for (i = 0; i < 4; i++) if (xget(i, st) == 0) return i;
    return -1;
}

static void add_voice(int env, int motor, int looping)
{
    int i;
    if (env < 0) return;
    EnterCriticalSection(&g_cs);
    for (i = 0; i < MAXVOICE; i++)
        if (!g_voice[i].active) {
            g_voice[i].env = env; g_voice[i].motor = motor;
            g_voice[i].active = 1; g_voice[i].looping = looping; g_voice[i].pos = 0;
            break;
        }
    LeaveCriticalSection(&g_cs);
}
static void stop_voices_env(int env)   /* end looping voices of this sound (on Stop) */
{
    int i;
    EnterCriticalSection(&g_cs);
    for (i = 0; i < MAXVOICE; i++)
        if (g_voice[i].active && g_voice[i].env == env && g_voice[i].looping)
            g_voice[i].active = 0;
    LeaveCriticalSection(&g_cs);
}

/* mixer thread: ~60 Hz, advance voices, MAX per motor, drive XInput */
static DWORD WINAPI mixer(LPVOID arg)
{
    (void)arg;
    while (g_run) {
        float lo = 0, hi = 0; int i; XVIB v;
        Sleep(16);
        if (g_pad < 0) { g_pad = find_pad(); if (g_pad < 0) continue; }
        EnterCriticalSection(&g_cs);
        for (i = 0; i < MAXVOICE; i++) {
            VOICE *vc = &g_voice[i]; ENVELOPE *e; float a; int idx;
            if (!vc->active) continue;
            e = &g_env[vc->env];
            idx = (int)vc->pos;
            if (idx >= e->len) {
                if (vc->looping) { vc->pos = 0; idx = 0; }
                else { vc->active = 0; continue; }
            }
            a = e->v[idx] / 100.0f;
            a = 0.30f + 0.70f * a * a;          /* dead-zone lift + gamma-2 (same feel as shim) */
            if (vc->motor != 1) if (a > lo) lo = a;
            if (vc->motor != 0) if (a > hi) hi = a;
            vc->pos += 16.0f / 25.0f;           /* envelope windows are 25 ms */
        }
        LeaveCriticalSection(&g_cs);
        if (xset) {
            v.l = (WORD)(cl01(lo) * 65535.0f);
            v.r = (WORD)(cl01(hi) * 65535.0f);
            if (xset(g_pad, &v) != 0) g_pad = -1;
        }
    }
    if (xset && g_pad >= 0) { XVIB z = {0,0}; xset(g_pad, &z); }
    return 0;
}

/* ===================== IDirectSoundBuffer wrapper ======================== */
typedef struct {
    IDirectSoundBufferVtbl *lpVtbl;   /* must be first */
    IDirectSoundBuffer *real;
    void *lk1; DWORD ll1; void *lk2; DWORD ll2;   /* captured lock region */
    int env, motor;                                /* identified sound */
} WrapDSB;
static IDirectSoundBufferVtbl g_dsb_vtbl;

static WrapDSB *wrap_buffer(IDirectSoundBuffer *real)
{
    WrapDSB *w;
    if (!real) return 0;
    w = (WrapDSB *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(WrapDSB));
    if (!w) return 0;
    w->lpVtbl = &g_dsb_vtbl; w->real = real; w->env = -1; w->motor = 2;
    return w;
}

static HRESULT STDMETHODCALLTYPE dsb_QI(IDirectSoundBuffer *t, REFIID r, void **o)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->QueryInterface(w->real,r,o); }
static ULONG STDMETHODCALLTYPE dsb_AddRef(IDirectSoundBuffer *t)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->AddRef(w->real); }
static ULONG STDMETHODCALLTYPE dsb_Release(IDirectSoundBuffer *t)
{ WrapDSB *w=(WrapDSB*)t; ULONG n=w->real->lpVtbl->Release(w->real);
  if(n==0){ HeapFree(GetProcessHeap(),0,w);} return n; }
static HRESULT STDMETHODCALLTYPE dsb_GetCaps(IDirectSoundBuffer *t, LPDSBCAPS c)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->GetCaps(w->real,c); }
static HRESULT STDMETHODCALLTYPE dsb_GetCurrentPosition(IDirectSoundBuffer *t, LPDWORD a, LPDWORD b)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->GetCurrentPosition(w->real,a,b); }
static HRESULT STDMETHODCALLTYPE dsb_GetFormat(IDirectSoundBuffer *t, LPWAVEFORMATEX f, DWORD s, LPDWORD w2)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->GetFormat(w->real,f,s,w2); }
static HRESULT STDMETHODCALLTYPE dsb_GetVolume(IDirectSoundBuffer *t, LPLONG v)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->GetVolume(w->real,v); }
static HRESULT STDMETHODCALLTYPE dsb_GetPan(IDirectSoundBuffer *t, LPLONG p)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->GetPan(w->real,p); }
static HRESULT STDMETHODCALLTYPE dsb_GetFrequency(IDirectSoundBuffer *t, LPDWORD f)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->GetFrequency(w->real,f); }
static HRESULT STDMETHODCALLTYPE dsb_GetStatus(IDirectSoundBuffer *t, LPDWORD s)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->GetStatus(w->real,s); }
static HRESULT STDMETHODCALLTYPE dsb_Initialize(IDirectSoundBuffer *t, LPDIRECTSOUND d, LPCDSBUFFERDESC de)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->Initialize(w->real,d,de); }
static HRESULT STDMETHODCALLTYPE dsb_Lock(IDirectSoundBuffer *t, DWORD o, DWORD b,
    LPVOID *p1, LPDWORD b1, LPVOID *p2, LPDWORD b2, DWORD fl)
{ WrapDSB *w=(WrapDSB*)t; HRESULT hr=w->real->lpVtbl->Lock(w->real,o,b,p1,b1,p2,b2,fl);
  if(SUCCEEDED(hr)){ w->lk1=p1?*p1:0; w->ll1=b1?*b1:0; w->lk2=p2?*p2:0; w->ll2=b2?*b2:0; } return hr; }
static HRESULT STDMETHODCALLTYPE dsb_Unlock(IDirectSoundBuffer *t, LPVOID p1, DWORD b1, LPVOID p2, DWORD b2)
{ WrapDSB *w=(WrapDSB*)t;
  /* fingerprint the PCM the game just wrote, map to a sound + motor */
  if(w->env<0 && w->lk1 && w->ll1){
      unsigned len=w->ll1+(w->lk2?w->ll2:0), h;
      if(w->lk2 && w->ll2){ /* two segments: hash both in order */
          unsigned hh=2166136261u,i;
          for(i=0;i<w->ll1;i++) hh=(hh^((unsigned char*)w->lk1)[i])*16777619u;
          for(i=0;i<w->ll2;i++) hh=(hh^((unsigned char*)w->lk2)[i])*16777619u;
          h=hh;
      } else h=fnv1a((unsigned char*)w->lk1, w->ll1);
      { int m=match_fp(len,h); if(m>=0){ w->env=g_fp[m].env; w->motor=g_fp[m].motor; } }
  }
  return w->real->lpVtbl->Unlock(w->real,p1,b1,p2,b2); }
static HRESULT STDMETHODCALLTYPE dsb_Play(IDirectSoundBuffer *t, DWORD r1, DWORD r2, DWORD fl)
{ WrapDSB *w=(WrapDSB*)t;
  if(w->env>=0) add_voice(w->env, w->motor, (fl&DSBPLAY_LOOPING)?1:0);
  return w->real->lpVtbl->Play(w->real,r1,r2,fl); }
static HRESULT STDMETHODCALLTYPE dsb_SetCurrentPosition(IDirectSoundBuffer *t, DWORD p)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->SetCurrentPosition(w->real,p); }
static HRESULT STDMETHODCALLTYPE dsb_SetFormat(IDirectSoundBuffer *t, LPCWAVEFORMATEX f)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->SetFormat(w->real,f); }
static HRESULT STDMETHODCALLTYPE dsb_SetVolume(IDirectSoundBuffer *t, LONG v)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->SetVolume(w->real,v); }
static HRESULT STDMETHODCALLTYPE dsb_SetPan(IDirectSoundBuffer *t, LONG p)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->SetPan(w->real,p); }
static HRESULT STDMETHODCALLTYPE dsb_SetFrequency(IDirectSoundBuffer *t, DWORD f)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->SetFrequency(w->real,f); }
static HRESULT STDMETHODCALLTYPE dsb_Stop(IDirectSoundBuffer *t)
{ WrapDSB *w=(WrapDSB*)t; if(w->env>=0) stop_voices_env(w->env);
  return w->real->lpVtbl->Stop(w->real); }
static HRESULT STDMETHODCALLTYPE dsb_Restore(IDirectSoundBuffer *t)
{ WrapDSB *w=(WrapDSB*)t; return w->real->lpVtbl->Restore(w->real); }

static void init_dsb_vtbl(void)
{
    g_dsb_vtbl.QueryInterface = dsb_QI;
    g_dsb_vtbl.AddRef = dsb_AddRef;
    g_dsb_vtbl.Release = dsb_Release;
    g_dsb_vtbl.GetCaps = dsb_GetCaps;
    g_dsb_vtbl.GetCurrentPosition = dsb_GetCurrentPosition;
    g_dsb_vtbl.GetFormat = dsb_GetFormat;
    g_dsb_vtbl.GetVolume = dsb_GetVolume;
    g_dsb_vtbl.GetPan = dsb_GetPan;
    g_dsb_vtbl.GetFrequency = dsb_GetFrequency;
    g_dsb_vtbl.GetStatus = dsb_GetStatus;
    g_dsb_vtbl.Initialize = dsb_Initialize;
    g_dsb_vtbl.Lock = dsb_Lock;
    g_dsb_vtbl.Play = dsb_Play;
    g_dsb_vtbl.SetCurrentPosition = dsb_SetCurrentPosition;
    g_dsb_vtbl.SetFormat = dsb_SetFormat;
    g_dsb_vtbl.SetVolume = dsb_SetVolume;
    g_dsb_vtbl.SetPan = dsb_SetPan;
    g_dsb_vtbl.SetFrequency = dsb_SetFrequency;
    g_dsb_vtbl.Stop = dsb_Stop;
    g_dsb_vtbl.Unlock = dsb_Unlock;
    g_dsb_vtbl.Restore = dsb_Restore;
}

/* ======================= IDirectSound wrapper ============================ */
typedef struct { IDirectSoundVtbl *lpVtbl; IDirectSound *real; } WrapDS;
static IDirectSoundVtbl g_ds_vtbl;

static HRESULT STDMETHODCALLTYPE ds_QI(IDirectSound *t, REFIID r, void **o)
{ WrapDS *w=(WrapDS*)t; return w->real->lpVtbl->QueryInterface(w->real,r,o); }
static ULONG STDMETHODCALLTYPE ds_AddRef(IDirectSound *t)
{ WrapDS *w=(WrapDS*)t; return w->real->lpVtbl->AddRef(w->real); }
static ULONG STDMETHODCALLTYPE ds_Release(IDirectSound *t)
{ WrapDS *w=(WrapDS*)t; ULONG n=w->real->lpVtbl->Release(w->real);
  if(n==0) HeapFree(GetProcessHeap(),0,w); return n; }
static HRESULT STDMETHODCALLTYPE ds_CreateSoundBuffer(IDirectSound *t, LPCDSBUFFERDESC d,
    LPDIRECTSOUNDBUFFER *pp, LPUNKNOWN u)
{ WrapDS *w=(WrapDS*)t; IDirectSoundBuffer *real=0; HRESULT hr;
  hr=w->real->lpVtbl->CreateSoundBuffer(w->real,d,&real,u);
  if(SUCCEEDED(hr)&&real){ WrapDSB *wb=wrap_buffer(real); *pp=(IDirectSoundBuffer*)(wb?(void*)wb:(void*)real); }
  return hr; }
static HRESULT STDMETHODCALLTYPE ds_GetCaps(IDirectSound *t, LPDSCAPS c)
{ WrapDS *w=(WrapDS*)t; return w->real->lpVtbl->GetCaps(w->real,c); }
static HRESULT STDMETHODCALLTYPE ds_DuplicateSoundBuffer(IDirectSound *t, LPDIRECTSOUNDBUFFER o, LPDIRECTSOUNDBUFFER *n)
{ WrapDS *w=(WrapDS*)t; IDirectSoundBuffer *real=0; HRESULT hr;
  /* unwrap the original if it's ours */
  IDirectSoundBuffer *src = o; if(((WrapDSB*)o)->lpVtbl==&g_dsb_vtbl) src=((WrapDSB*)o)->real;
  hr=w->real->lpVtbl->DuplicateSoundBuffer(w->real,src,&real);
  if(SUCCEEDED(hr)&&real){ WrapDSB *wb=wrap_buffer(real); *n=(IDirectSoundBuffer*)(wb?(void*)wb:(void*)real); }
  return hr; }
static HRESULT STDMETHODCALLTYPE ds_SetCooperativeLevel(IDirectSound *t, HWND h, DWORD l)
{ WrapDS *w=(WrapDS*)t; return w->real->lpVtbl->SetCooperativeLevel(w->real,h,l); }
static HRESULT STDMETHODCALLTYPE ds_Compact(IDirectSound *t)
{ WrapDS *w=(WrapDS*)t; return w->real->lpVtbl->Compact(w->real); }
static HRESULT STDMETHODCALLTYPE ds_GetSpeakerConfig(IDirectSound *t, LPDWORD c)
{ WrapDS *w=(WrapDS*)t; return w->real->lpVtbl->GetSpeakerConfig(w->real,c); }
static HRESULT STDMETHODCALLTYPE ds_SetSpeakerConfig(IDirectSound *t, DWORD c)
{ WrapDS *w=(WrapDS*)t; return w->real->lpVtbl->SetSpeakerConfig(w->real,c); }
static HRESULT STDMETHODCALLTYPE ds_Initialize(IDirectSound *t, LPCGUID g)
{ WrapDS *w=(WrapDS*)t; return w->real->lpVtbl->Initialize(w->real,g); }

static void init_ds_vtbl(void)
{
    g_ds_vtbl.QueryInterface = ds_QI;
    g_ds_vtbl.AddRef = ds_AddRef;
    g_ds_vtbl.Release = ds_Release;
    g_ds_vtbl.CreateSoundBuffer = ds_CreateSoundBuffer;
    g_ds_vtbl.GetCaps = ds_GetCaps;
    g_ds_vtbl.DuplicateSoundBuffer = ds_DuplicateSoundBuffer;
    g_ds_vtbl.SetCooperativeLevel = ds_SetCooperativeLevel;
    g_ds_vtbl.Compact = ds_Compact;
    g_ds_vtbl.GetSpeakerConfig = ds_GetSpeakerConfig;
    g_ds_vtbl.SetSpeakerConfig = ds_SetSpeakerConfig;
    g_ds_vtbl.Initialize = ds_Initialize;
}

/* ======================= exported DirectSoundCreate ====================== */
typedef HRESULT (WINAPI *DSCreateFn)(LPCGUID, LPDIRECTSOUND *, LPUNKNOWN);
static DSCreateFn real_create;

static void load_real_dsound(void)
{
    /* load the REAL dsound by full system path so we don't recurse into ourselves */
    HMODULE m = LoadLibraryA("C:\\windows\\system32\\dsound.dll");
    if (!m) m = LoadLibraryA("dsound_org.dll");   /* Windows fallback: renamed original */
    if (m) real_create = (DSCreateFn)GetProcAddress(m, "DirectSoundCreate");
}

HRESULT WINAPI DirectSoundCreate(LPCGUID lpGuid, LPDIRECTSOUND *ppDS, LPUNKNOWN pUnkOuter)
{
    IDirectSound *real = 0; HRESULT hr; WrapDS *w;
    if (!real_create) load_real_dsound();
    if (!real_create) return E_FAIL;
    hr = real_create(lpGuid, &real, pUnkOuter);
    if (FAILED(hr) || !real) { if (ppDS) *ppDS = real; return hr; }
    w = (WrapDS *)HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, sizeof(WrapDS));
    if (!w) { *ppDS = real; return hr; }
    w->lpVtbl = &g_ds_vtbl; w->real = real;
    *ppDS = (IDirectSound *)w;
    return hr;
}

/* freestanding: the compiler may still emit memcpy/memset for aggregate ops */
void *memset(void *d, int c, size_t n){ unsigned char *p=d; while(n--) *p++=(unsigned char)c; return d; }
void *memcpy(void *d, const void *s, size_t n){ unsigned char *a=d; const unsigned char *b=s; while(n--) *a++=*b++; return d; }

BOOL WINAPI DllMainCRTStartup(HINSTANCE h, DWORD reason, LPVOID res)
{
    (void)h; (void)res;
    if (reason == DLL_PROCESS_ATTACH) {
        static const char *xd[] = { "xinput1_3.dll", "xinput9_1_0.dll", "xinput1_4.dll", 0 };
        int i; HMODULE m;
        DisableThreadLibraryCalls(h);
        init_ds_vtbl(); init_dsb_vtbl();
        InitializeCriticalSection(&g_cs);
        load_tables();
        for (i = 0; !xset && xd[i]; i++)
            if ((m = LoadLibraryA(xd[i]))) {
                xset = (XSetFn)GetProcAddress(m, "XInputSetState");
                xget = (XGetFn)GetProcAddress(m, "XInputGetState");
            }
        g_pad = find_pad();
        g_thread = CreateThread(0, 0, mixer, 0, 0, 0);
    } else if (reason == DLL_PROCESS_DETACH) {
        g_run = 0;
    }
    return TRUE;
}
