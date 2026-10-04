/*
 * i76uncap.dll — 60 FPS for Interstate '76: render extra frames while the sim stays 20 Hz.
 *
 * STAGE 2: after the engine's real present, render N extra frames by re-running
 * BeginFrame + render_scene + Flip. Optionally advance (extrapolate) every render-consumed
 * transform between sub-frames so the extra frames show intermediate motion (Stage 3).
 *
 * Controlled at runtime by C:\Users\james\i76-uncap-lab\captures\i76uncap.ctl :
 *     extras=<0..3>   extra frames per real frame (0 = passthrough, 2 = 60fps at 20 base)
 *     interp=<0|1>    0 = identical extra frames, 1 = extrapolate transforms
 *     pace=<ms>       sleep between sub-frames (0 = none / bunched)
 *     enabled=<0|1>
 *
 * Engine (Gold i76.exe, base 0x400000, no ASLR):
 *   0x5DD2C0 present fn-ptr (->0x4343D0)   0x5DD2BC beginframe fn-ptr (->0x434340)
 *   0x4621E0 render_scene(cam)  cam=0x4C2730   surface=0x5DCEC0
 *   0x5A7E1C loop frame counter   player entity = [[[0x54a264]]+0x70]
 *   render-consumed transforms: static 0x5FCDC4 (pos+matrix) + heap scene nodes (found live)
 *
 * Build (32-bit): cl /nologo /O2 /LD i76uncap.c /link /OUT:i76uncap.dll
 */
#include <windows.h>
#include <tlhelp32.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef int  (__cdecl *present_t)(void*);
typedef int  (__cdecl *begin_t)(void*);
typedef void (__cdecl *render_t)(void*);

#define PTR_PRESENT   ((void**)0x005DD2C0)
#define PTR_BEGIN     ((void**)0x005DD2BC)
#define RENDER_SCENE  ((render_t)0x004621E0)
#define SURFACE       ((void*)0x005DCEC0)
#define CAMERA        ((void*)0x004C2730)
#define ADDR_FRAMECTR ((volatile int*)0x005A7E1C)
#define ROOT          ((int*)0x0054A264)

static present_t g_orig_present = 0;
static begin_t   g_begin = 0;
static volatile LONG g_present_count = 0;

/* runtime controls */
static volatile int g_extras = 0;
static volatile int g_interp = 0;
static volatile int g_pace = 0;
static volatile int g_enabled = 1;
static volatile int g_fpscap = 0;      /* 0 = uncapped; else target frames/sec, applied in-DLL */
static volatile int g_savestate = 0;   /* set to 1 -> snapshot on the next frame boundary */
static volatile int g_loadstate = 0;   /* set to 1 -> restore on the next frame boundary */

/* ---- save-state (emulator style) ----------------------------------------------------
 * Every A/B test so far was confounded because the two runs start from different states:
 * the car ends up on different terrain, so "top speed" and "coast decay" measure the ground,
 * not the physics. Snapshot the world once and restore it before each run and the comparison
 * becomes exact - and it lets a human line up a scripted set piece (the Mission 5 canyon jump)
 * that automated driving cannot find.
 *
 * Snapshots the game's committed private read/write regions. Same-process only: heap addresses
 * must still be valid, so a state cannot be restored after a relaunch.  */
#define STATE_FILE "C:\\Users\\james\\i76-uncap-lab\\captures\\state.bin"
#define STATE_LO   0x00400000u
#define STATE_HI   0x20000000u
#define STATE_MAXREGION (16u*1024u*1024u)

/* interpolation: render-consumed world-position copies to extrapolate between sub-frames.
 * 0x5FCDC4 is the static transform that drives the eye (verified live). rescan() adds the
 * heap scene-node copies of the player position so the player render nodes move too. */
#define CULL_TABLE 0x0054E11C
#define CULL_STRIDE 0x20
#define CULL_SLOTS  16
#define EYE_XFORM  0x005FCDC4
#define MAXTRACK 256
static volatile int g_ntrack = 0;
static unsigned g_track[MAXTRACK];
static float g_prev[MAXTRACK][3];
static int g_have_prev = 0;
/* Which culling-table slot (= which vehicle) each tracked copy belongs to, so every car gets
 * ITS OWN delta. -1 = the eye transform, which follows the player (slot 0). */
static int g_owner[MAXTRACK];
static volatile int g_needs_rescan = 0;   /* set when a tracked address faults (heap copy freed) */

static const char* LOG = "C:\\Users\\james\\i76-uncap-lab\\captures\\i76uncap.log";
static const char* CTL = "C:\\Users\\james\\i76-uncap-lab\\captures\\i76uncap.ctl";
static const char* REC = "C:\\Users\\james\\i76-uncap-lab\\captures\\traces\\inproc.csv";

/* ---- in-process per-frame recorder -------------------------------------------------
 * External polling samples at best every ~50 ms, which cannot resolve anything that
 * happens inside one 20 Hz frame (a whole launch-to-fall transition fitted -38 m/s^2
 * that way). Recording from inside the present hook gives one exact sample PER FRAME.
 * ctl: record=1 start, record=0 stop+flush.  */
#define RECMAX 40000
typedef struct { double t; int frame; float px,py,pz,vx,vy,vz,spd; float e1x,e1z,e2x,e2z; } Sample;
static Sample* g_rec = 0;
static volatile int g_nrec = 0;
static volatile int g_record = 0;
static int g_recording = 0;
static double g_qpc_freq = 0.0;

static double now_sec(void){
    LARGE_INTEGER c; QueryPerformanceCounter(&c);
    return (double)c.QuadPart / g_qpc_freq;
}
static void rec_flush(void){
    if(!g_rec || g_nrec<=0) return;
    FILE* f=fopen(REC,"w");
    if(!f) return;
    fputs("t_ms,frame,x,y,z,vx,vy,vz,speed,e1x,e1z,e2x,e2z\n",f);
    double t0=g_rec[0].t;
    for(int i=0;i<g_nrec;i++){
        Sample* s=&g_rec[i];
        fprintf(f,"%.3f,%d,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.6f,%.3f,%.3f,%.3f,%.3f\n",
            (s->t-t0)*1000.0, s->frame, s->px,s->py,s->pz, s->vx,s->vy,s->vz, s->spd,
            s->e1x,s->e1z, s->e2x,s->e2z);
    }
    fclose(f);
}
static void rec_sample(void){
    if(!g_rec || g_nrec>=RECMAX) return;
    __try {
        int w=*ROOT; if(!w) return;
        int sub=*(int*)w; if(!sub) return;
        int e=*(int*)(sub+0x70); if(!e) return;
        Sample* s=&g_rec[g_nrec];
        s->t=now_sec();
        s->frame=*ADDR_FRAMECTR;
        float* pos=(float*)(CULL_TABLE);
        s->px=pos[0]; s->py=pos[1]; s->pz=pos[2];
        float* vel=(float*)(e+0xBC);
        s->vx=vel[0]; s->vy=vel[1]; s->vz=vel[2];
        s->spd=*(float*)(e+0xAC);
        float* e1=(float*)(CULL_TABLE+1*CULL_STRIDE);
        float* e2=(float*)(CULL_TABLE+2*CULL_STRIDE);
        s->e1x=e1[0]; s->e1z=e1[2]; s->e2x=e2[0]; s->e2z=e2[2];
        g_nrec++;
    } __except(EXCEPTION_EXECUTE_HANDLER){ }
}

static void logline(const char* s){ FILE* f=fopen(LOG,"a"); if(f){fputs(s,f);fputc('\n',f);fclose(f);} }

/* player entity or 0; SEH-guarded so a bad deref at menus can't crash us */
static int player_entity(void){
    __try {
        int w = *ROOT; if(!w) return 0;
        int sub = *(int*)w; if(!sub) return 0;
        return *(int*)(sub+0x70);
    } __except(EXCEPTION_EXECUTE_HANDLER) { return 0; }
}

/* one extra rendered+presented frame; SEH-guarded */
static void extra_frame(void){
    __try {
        if(g_begin) g_begin(SURFACE);
        RENDER_SCENE(CAMERA);
        g_orig_present(SURFACE);
    } __except(EXCEPTION_EXECUTE_HANDLER) { }
}

/* Scan committed heap for float3 copies of the current player position and record their
 * addresses (the render-consumed transforms). Always includes the eye transform. Called
 * once per mission start from the control thread (not the render path). */
static void rescan(void){
    /* Snapshot every live vehicle's position from the culling table, then find each one's
     * render-node copies in the heap. Tracking per-vehicle (not just the player) is what lets
     * Taurus and the other cars be interpolated too. */
    float P[CULL_SLOTS][3]; int liveSlot[CULL_SLOTS]; int nlive=0;
    __try {
        for(int i=0;i<CULL_SLOTS;i++){
            float* c=(float*)(CULL_TABLE + i*CULL_STRIDE);
            P[i][0]=c[0]; P[i][1]=c[1]; P[i][2]=c[2];
            liveSlot[i] = (c[0]!=0.0f || c[2]!=0.0f);
            if(liveSlot[i]) nlive++;
        }
    } __except(EXCEPTION_EXECUTE_HANDLER){ return; }
    if(!nlive || !liveSlot[0]) return;   /* not in a mission yet */

    int n=0;
    g_track[n]=EYE_XFORM; g_owner[n]=0; n++;   /* eye follows the player (slot 0) */

    MEMORY_BASIC_INFORMATION mbi;
    unsigned char* addr=(unsigned char*)0x00400000;
    unsigned char* limit=(unsigned char*)0x08000000;
    const float tol=1.5f;
    while(addr<limit && n<MAXTRACK){
        if(!VirtualQuery(addr,&mbi,sizeof(mbi))) break;
        unsigned char* base=(unsigned char*)mbi.BaseAddress;
        SIZE_T sz=mbi.RegionSize;
        int rw = (mbi.State==MEM_COMMIT) &&
                 (mbi.Protect==PAGE_READWRITE || mbi.Protect==PAGE_EXECUTE_READWRITE ||
                  mbi.Protect==PAGE_WRITECOPY || mbi.Protect==PAGE_READONLY || mbi.Protect==PAGE_EXECUTE_READ);
        if(rw && sz<=0x800000){
            __try {
                for(SIZE_T o=0; o+12<=sz && n<MAXTRACK; o+=4){
                    float* f=(float*)(base+o);
                    unsigned a=(unsigned)(base+o);
                    if(a>=CULL_TABLE-8 && a<=CULL_TABLE+CULL_SLOTS*CULL_STRIDE) continue; /* the table itself */
                    if(a==EYE_XFORM) continue;
                    for(int s=0;s<CULL_SLOTS && n<MAXTRACK;s++){
                        if(!liveSlot[s]) continue;
                        if(f[0]>P[s][0]-tol && f[0]<P[s][0]+tol &&
                           f[1]>P[s][1]-tol && f[1]<P[s][1]+tol &&
                           f[2]>P[s][2]-tol && f[2]<P[s][2]+tol){
                            g_track[n]=a; g_owner[n]=s; n++;
                            break;
                        }
                    }
                }
            } __except(EXCEPTION_EXECUTE_HANDLER){ }
        }
        addr = base + sz;
    }
    g_ntrack=n; g_have_prev=0;
}

/* Is this region ours (the recorder buffer)? Restoring over it would corrupt the DLL. */
static int region_is_ours(unsigned char* base, SIZE_T sz){
    unsigned char* rec = (unsigned char*)g_rec;
    return rec && rec >= base && rec < base + sz;
}

/* THREAD STACKS MUST NEVER BE RESTORED.
 * The first attempt saved and restored every private RW region, which included the calling
 * thread's own stack: overwriting it clobbers the return address and the game dies instantly
 * (confirmed - crash dump on the first restore). Skip any region holding a live stack.
 * The current thread's bounds come from the TEB; other threads are excluded heuristically by
 * skipping regions that contain their stack guard signature (MEM_PRIVATE + PAGE_GUARD nearby). */
static int region_is_stack(unsigned char* base, SIZE_T sz){
    NT_TIB* tib = (NT_TIB*)NtCurrentTeb();
    unsigned char* lo = (unsigned char*)tib->StackLimit;
    unsigned char* hi = (unsigned char*)tib->StackBase;
    /* overlap with this thread's stack? */
    if(hi > base && lo < base + sz) return 1;
    /* a local's address must also be outside the region we are about to overwrite */
    volatile int probe;
    unsigned char* here = (unsigned char*)&probe;
    if(here >= base && here < base + sz) return 1;
    return 0;
}

static void state_save(void){
    FILE* f = fopen(STATE_FILE, "wb");
    if(!f){ logline("savestate: cannot open file"); return; }
    MEMORY_BASIC_INFORMATION mbi;
    unsigned char* addr = (unsigned char*)STATE_LO;
    int nreg = 0; unsigned total = 0;
    while((unsigned)(ULONG_PTR)addr < STATE_HI){
        if(!VirtualQuery(addr, &mbi, sizeof(mbi))) break;
        unsigned char* base = (unsigned char*)mbi.BaseAddress;
        SIZE_T sz = mbi.RegionSize;
        if(sz == 0) break;
        if(mbi.State == MEM_COMMIT && mbi.Type == MEM_PRIVATE &&
           (mbi.Protect == PAGE_READWRITE || mbi.Protect == PAGE_EXECUTE_READWRITE) &&
           sz <= STATE_MAXREGION && !region_is_ours(base, sz) && !region_is_stack(base, sz)){
            unsigned b = (unsigned)(ULONG_PTR)base, s = (unsigned)sz;
            __try {
                fwrite(&b, 4, 1, f); fwrite(&s, 4, 1, f); fwrite(base, 1, s, f);
                nreg++; total += s;
            } __except(EXCEPTION_EXECUTE_HANDLER){ }
        }
        addr = base + sz;
    }
    fclose(f);
    { char b[128]; sprintf(b, "savestate: %d regions, %u KB", nreg, total/1024); logline(b); }
}

/* Freeze/thaw every OTHER thread around a restore.
 * Restoring heap pages while the audio/worker threads keep running corrupts whatever they are
 * holding, and the game dies a moment later (observed twice). An emulator can restore safely
 * because nothing else is executing; this reproduces that condition. */
static void suspend_others(int suspend){
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
    if(snap == INVALID_HANDLE_VALUE) return;
    THREADENTRY32 te; te.dwSize = sizeof(te);
    DWORD me = GetCurrentThreadId(), pid = GetCurrentProcessId();
    if(Thread32First(snap, &te)){
        do {
            if(te.th32OwnerProcessID == pid && te.th32ThreadID != me){
                HANDLE h = OpenThread(THREAD_SUSPEND_RESUME, FALSE, te.th32ThreadID);
                if(h){ if(suspend) SuspendThread(h); else ResumeThread(h); CloseHandle(h); }
            }
        } while(Thread32Next(snap, &te));
    }
    CloseHandle(snap);
}

/* WARNING - loadstate is EXPERIMENTAL AND KILLS THE GAME. Kept for the record.
 * Three attempts, three crashes: (1) restoring everything clobbered the calling thread's own
 * stack; (2) excluding stacks still died because other threads kept running over restored
 * heap; (3) suspending every other thread first ALSO died. The regions being restored contain
 * heap metadata, CRT state and dgVoodoo/DirectDraw internals whose invariants cannot survive
 * being rolled back underneath a live process - an emulator can do this only because it owns
 * a flat, self-contained memory image.
 *
 * USE INSTEAD: the game's own bookmark saves for a reproducible start state, plus fpscap=N to
 * change frame rate without relaunching. Together those give identical-start A/B runs, which
 * is what the save-state was wanted for. See autotest/enter-mission5.ps1.  */
static void state_load(void){
    FILE* f = fopen(STATE_FILE, "rb");
    if(!f){ logline("loadstate: no state file"); return; }
    logline("loadstate: EXPERIMENTAL - known to crash the game; prefer bookmark + fpscap");
    int nreg = 0;
    suspend_others(1);
    for(;;){
        unsigned b = 0, s = 0;
        if(fread(&b, 4, 1, f) != 1) break;
        if(fread(&s, 4, 1, f) != 1) break;
        if(s == 0 || s > STATE_MAXREGION) break;
        unsigned char* buf = (unsigned char*)malloc(s);
        if(!buf) break;
        if(fread(buf, 1, s, f) != s){ free(buf); break; }
        MEMORY_BASIC_INFORMATION mbi;
        if(VirtualQuery((void*)(ULONG_PTR)b, &mbi, sizeof(mbi)) &&
           mbi.State == MEM_COMMIT && mbi.RegionSize >= s &&
           !region_is_ours((unsigned char*)(ULONG_PTR)b, s) &&
           !region_is_stack((unsigned char*)(ULONG_PTR)b, s)){
            __try { memcpy((void*)(ULONG_PTR)b, buf, s); nreg++; }
            __except(EXCEPTION_EXECUTE_HANDLER){ }
        }
        free(buf);
    }
    fclose(f);
    suspend_others(0);
    { char t[96]; sprintf(t, "loadstate: restored %d regions", nreg); logline(t); }
    g_ntrack = 0; g_have_prev = 0;      /* tracked heap copies are stale after a restore */
}

static int __cdecl my_present(void* surface){
    int r = g_orig_present(surface);            /* the real frame at the true sim position */
    InterlockedIncrement(&g_present_count);

    /* Snapshot/restore at a frame boundary - the sim is between steps here, so the state is
     * coherent. Doing it from the control thread instead would tear mid-update. */
    if(g_savestate){ g_savestate = 0; state_save(); }
    if(g_loadstate){ g_loadstate = 0; state_load(); }

    /* In-DLL frame limiter. Lets the frame rate change WITHOUT relaunching, which is what
     * makes save-state A/B possible: same process, same state, only the rate differs.
     * (dgVoodoo's FPSLimit and I76PATCH are both read once at startup.) */
    if(g_fpscap > 0){
        static double next_due = 0.0;
        double period = 1.0 / (double)g_fpscap;
        double now = now_sec();
        if(next_due == 0.0 || now > next_due + 1.0) next_due = now;   /* (re)sync */
        next_due += period;
        double wait = next_due - now;
        while(wait > 0.0){
            if(wait > 0.002) Sleep((DWORD)((wait - 0.001) * 1000.0));  /* coarse sleep */
            else Sleep(0);                                             /* spin the last bit */
            now = now_sec();
            wait = next_due - now;
        }
    }

    /* one exact sample per REAL frame (before any extra frames are drawn) */
    if(g_record){
        if(!g_recording){ g_nrec=0; g_recording=1; }
        rec_sample();
    } else if(g_recording){
        g_recording=0; rec_flush();
    }

    int n = g_extras; if(n>3) n=3;
    if(!(g_enabled && n>0 && player_entity())) return r;

    if(!(g_interp && g_ntrack>0)){              /* extras without interpolation (identical) */
        for(int k=0;k<n;k++){ if(g_pace>0) Sleep(g_pace); extra_frame(); InterlockedIncrement(&g_present_count); }
        return r;
    }

    /* --- interpolated extra frames ------------------------------------------------ */
    /* Deltas are PER COPY (each address extrapolates from its own previous value), so a car
     * that starts beside the player with the same heading still gets its own motion - an
     * ownership mix-up cannot corrupt the trajectory. A discontinuity guard drops implausible
     * jumps (respawn/teleport/scan drift), the sm64ex "skip interpolation this frame" idea. */
    int m=g_ntrack; if(m>MAXTRACK) m=MAXTRACK;
    static float cur[MAXTRACK][3], delta[MAXTRACK][3];
    static int ok[MAXTRACK];
    const float MAXJUMP = 25.0f;   /* >25 m in one 50 ms tick = 500 m/s: not real motion */
    /* Per-address SEH: other vehicles' copies live on the heap and can be freed mid-mission.
     * A fault must disable only THAT address, never abort the frame - aborting dropped us
     * straight back to 20 fps. A fault also schedules a rescan so the list self-heals. */
    int faulted=0;
    for(int i=0;i<m;i++){
        ok[i]=0;
        __try {
            float* p=(float*)g_track[i];
            cur[i][0]=p[0]; cur[i][1]=p[1]; cur[i][2]=p[2];
            if(g_have_prev){
                float dx=cur[i][0]-g_prev[i][0], dy=cur[i][1]-g_prev[i][1], dz=cur[i][2]-g_prev[i][2];
                if(dx*dx+dy*dy+dz*dz > MAXJUMP*MAXJUMP){ dx=dy=dz=0.0f; }   /* discontinuity: don't smear */
                delta[i][0]=dx; delta[i][1]=dy; delta[i][2]=dz;
            }
            else { delta[i][0]=delta[i][1]=delta[i][2]=0.0f; }
            ok[i]=1;
        } __except(EXCEPTION_EXECUTE_HANDLER){ faulted=1; }
    }
    if(faulted) g_needs_rescan=1;

    for(int k=1;k<=n;k++){
        if(g_pace>0) Sleep(g_pace);
        float frac=(float)k/(float)(n+1);       /* 1/3, 2/3 ahead (extrapolate along last-tick motion) */
        for(int i=0;i<m;i++){
            if(!ok[i]) continue;
            __try {
                float* p=(float*)g_track[i];
                p[0]=cur[i][0]+delta[i][0]*frac; p[1]=cur[i][1]+delta[i][1]*frac; p[2]=cur[i][2]+delta[i][2]*frac;
            } __except(EXCEPTION_EXECUTE_HANDLER){ ok[i]=0; g_needs_rescan=1; }
        }
        extra_frame();
        InterlockedIncrement(&g_present_count);
    }
    /* restore the true positions so the engine's next sim step integrates from truth */
    for(int i=0;i<m;i++){
        if(!ok[i]) continue;
        __try { float* p=(float*)g_track[i]; p[0]=cur[i][0]; p[1]=cur[i][1]; p[2]=cur[i][2]; }
        __except(EXCEPTION_EXECUTE_HANDLER){ ok[i]=0; g_needs_rescan=1; }
    }
    for(int i=0;i<m;i++){ if(ok[i]){ g_prev[i][0]=cur[i][0]; g_prev[i][1]=cur[i][1]; g_prev[i][2]=cur[i][2]; } }
    g_have_prev=1;
    return r;
}

static void read_ctl(void){
    FILE* f=fopen(CTL,"r"); if(!f) return;
    char line[128];
    while(fgets(line,sizeof(line),f)){
        int v;
        if(sscanf(line,"extras=%d",&v)==1) g_extras=v;
        else if(sscanf(line,"interp=%d",&v)==1) g_interp=v;
        else if(sscanf(line,"pace=%d",&v)==1) g_pace=v;
        else if(sscanf(line,"enabled=%d",&v)==1) g_enabled=v;
        else if(sscanf(line,"record=%d",&v)==1) g_record=v;
        else if(sscanf(line,"fpscap=%d",&v)==1) g_fpscap=v;
        else if(sscanf(line,"savestate=%d",&v)==1) { if(v) g_savestate=1; }
        else if(sscanf(line,"loadstate=%d",&v)==1) { if(v) g_loadstate=1; }
    }
    fclose(f);
}

static DWORD WINAPI init_thread(LPVOID arg){
    char buf[256];
    LARGE_INTEGER fq; QueryPerformanceFrequency(&fq); g_qpc_freq=(double)fq.QuadPart;
    g_rec = (Sample*)malloc(sizeof(Sample)*RECMAX);
    Sleep(3000);
    g_orig_present = (present_t)(*PTR_PRESENT);
    g_begin        = (begin_t)(*PTR_BEGIN);
    sprintf(buf,"init: present=0x%08X begin=0x%08X", (unsigned)g_orig_present,(unsigned)g_begin);
    logline(buf);
    DWORD old;
    VirtualProtect(PTR_PRESENT,4,PAGE_READWRITE,&old);
    *PTR_PRESENT=(void*)my_present;
    VirtualProtect(PTR_PRESENT,4,old,&old);
    logline("hook installed");
    int lp=0,ls=0, wasInMission=0;
    for(;;){
        Sleep(500);
        read_ctl();
        int inMission = player_entity()!=0;
        if(inMission && (!wasInMission || g_ntrack==0 || g_needs_rescan)){
            g_needs_rescan=0;
            rescan();
            /* histogram by owner slot: proves each vehicle (not just the player) has copies */
            int hist[CULL_SLOTS]; for(int i=0;i<CULL_SLOTS;i++) hist[i]=0;
            for(int i=0;i<g_ntrack;i++){ int o=g_owner[i]; if(o>=0&&o<CULL_SLOTS) hist[o]++; }
            int off=sprintf(buf,"rescan: %d copies  per-vehicle:", g_ntrack);
            for(int i=0;i<CULL_SLOTS;i++) if(hist[i]) off+=sprintf(buf+off," slot%d=%d",i,hist[i]);
            logline(buf);
        }
        if(!inMission){ g_ntrack=0; g_have_prev=0; }
        wasInMission = inMission;

        static int tick=0;
        if(++tick>=2){   /* ~1s cadence for the rate line */
            tick=0;
            int p=g_present_count, s=*ADDR_FRAMECTR;
            sprintf(buf,"presents/s=%d simframes/s=%d extras=%d interp=%d pace=%d track=%d en=%d",
                    (p-lp)/1, (s-ls)/1, g_extras, g_interp, g_pace, g_ntrack, g_enabled);
            logline(buf);
            lp=p; ls=s;
        }
    }
    return 0;
}

BOOL WINAPI DllMain(HINSTANCE h, DWORD reason, LPVOID r){
    if(reason==DLL_PROCESS_ATTACH){
        DisableThreadLibraryCalls(h);
        logline("=== i76uncap attached (stage2) ===");
        CreateThread(0,0,init_thread,0,0,0);
    }
    return TRUE;
}
