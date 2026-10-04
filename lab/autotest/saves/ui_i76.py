"""ui_i76.py - copy of i76-map\captures\002-nav\ui.py adapted for the sandbox i76.exe (the original keys on
the process name 'i76_pristine*' and is left untouched). Same commands: shot <name> | click x y | key vk |
uclick ux uy | quit | chord mod vk | sleep s | state. The process is picked by name 'i76.exe' AND by path
containing 'i76-uncap-lab' so the daily driver can never be the target."""
import sys, time, win32gui, win32ui, win32con, win32api, win32process, psutil, ctypes, struct
def _pid():
    for p in psutil.process_iter(['name', 'exe']):
        n = (p.info['name'] or '').lower(); e = (p.info['exe'] or '').lower()
        if n == 'i76.exe' and 'i76-uncap-lab' in e: return p.pid
    raise SystemExit("no sandbox i76.exe running")
pid = _pid()
def main_hwnd():
    r=[]
    def cb(h,_):
        if win32process.GetWindowThreadProcessId(h)[1]==pid and win32gui.IsWindowVisible(h) and win32gui.GetClassName(h)!='#32770': r.append(h)
    win32gui.EnumWindows(cb,None); return r[0]
def shot(name):
    hw=main_hwnd(); l,t,r,b=win32gui.GetWindowRect(hw); w,h=r-l,b-t
    hdc=win32gui.GetDC(0); src=win32ui.CreateDCFromHandle(hdc); mem=src.CreateCompatibleDC(); bmp=win32ui.CreateBitmap(); bmp.CreateCompatibleBitmap(src,w,h); mem.SelectObject(bmp); mem.BitBlt((0,0),(w,h),src,(l,t),win32con.SRCCOPY)
    bmp.SaveBitmapFile(mem,name+".bmp")
    import subprocess; subprocess.run(["powershell","-NoProfile","-Command",f"Add-Type -AssemblyName System.Drawing; $b=[System.Drawing.Bitmap]::FromFile('{name}.bmp'); $s=New-Object System.Drawing.Bitmap 960,720; $g=[System.Drawing.Graphics]::FromImage($s); $g.DrawImage($b,0,0,960,720); $s.Save('{name}.png'); $g.Dispose(); $s.Dispose(); $b.Dispose(); Remove-Item '{name}.bmp'"],check=False)
    print(f"window {l},{t} {w}x{h} -> {name}.png (scale {w/960:.3f})")
def focus(hw):
    if win32gui.GetForegroundWindow()!=hw:
        try: win32gui.SetForegroundWindow(hw)
        except Exception: pass
        if win32gui.GetForegroundWindow()!=hw:
            ctypes.windll.user32.ShowWindow(hw,6); time.sleep(0.6); ctypes.windll.user32.ShowWindow(hw,9); time.sleep(0.8)
def click(x,y):
    hw=main_hwnd(); focus(hw); l,t,_,_=win32gui.GetWindowRect(hw)
    win32api.SetCursorPos((l+x,t+y)); time.sleep(0.3); win32api.mouse_event(2,0,0,0,0); time.sleep(0.06); win32api.mouse_event(4,0,0,0,0); time.sleep(0.8); print("clicked",l+x,t+y)
def key(vk):
    hw=main_hwnd(); focus(hw)
    win32api.keybd_event(vk,0,0,0); time.sleep(0.05); win32api.keybd_event(vk,0,2,0); time.sleep(0.5)
def uclick(ux,uy):
    """click at a 640x480 UI coordinate (see the original ui.py for the two window regimes)"""
    hw=main_hwnd(); l,t,r,b=win32gui.GetWindowRect(hw); w=r-l
    if w >= 3000: click(ux, uy)
    else: click(ux*3, uy*3)
def quit_game(timeout=20):
    """clean exit (M12: a killed instance never sends MCI_CLOSE): WM_CLOSE to the main window, wait, kill only as a fallback"""
    hw=main_hwnd(); p=win32process.GetWindowThreadProcessId(hw)[1] if hw else None
    if hw: win32gui.PostMessage(hw,0x0010,0,0)
    t0=time.time()
    while p and psutil.pid_exists(p) and time.time()-t0<timeout: time.sleep(0.5)
    if p and psutil.pid_exists(p):
        psutil.Process(p).kill(); print("quit: WM_CLOSE ignored after %ds, killed %d"%(timeout,p))
    else: print("quit: clean exit in %.1fs (pid %s)"%(time.time()-t0,p))
def chord(mod,vk):
    hw=main_hwnd(); focus(hw)
    win32api.keybd_event(mod,0,0,0); time.sleep(0.08); win32api.keybd_event(vk,0,0,0); time.sleep(0.08); win32api.keybd_event(vk,0,2,0); time.sleep(0.05); win32api.keybd_event(mod,0,2,0); time.sleep(0.6); print('chord',mod,vk)
def state():
    h=ctypes.windll.kernel32.OpenProcess(0x10|0x400,False,pid)
    def rd(a,n):
        b=ctypes.create_string_buffer(n); g=ctypes.c_size_t(); ctypes.windll.kernel32.ReadProcessMemory(h,ctypes.c_void_p(a),b,n,ctypes.byref(g)); return b.raw[:g.value]
    def i32(a): return struct.unpack('<I',rd(a,4))[0]
    w=i32(0x54a264); s=i32(w) if w else 0; e=i32(s+0x70) if s else 0
    print(f"frame {i32(0x5a7e1c)} entity {e:#x} world {w:#x} scene {i32(0x4c2160)}")
if __name__ == '__main__':
    args=sys.argv[1:]
    while args:
        c=args.pop(0)
        if c=='shot': shot(args.pop(0))
        elif c=='click': click(int(args.pop(0)),int(args.pop(0)))
        elif c=='key': key(int(args.pop(0)))
        elif c=='uclick': uclick(int(args.pop(0)),int(args.pop(0)))
        elif c=='quit': quit_game()
        elif c=='chord': chord(int(args.pop(0)),int(args.pop(0)))
        elif c=='sleep': time.sleep(float(args.pop(0)))
        elif c=='state': state()
