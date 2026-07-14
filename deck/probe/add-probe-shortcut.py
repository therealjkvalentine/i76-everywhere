#!/usr/bin/env python3
# Add "I76 Input Probe" as a non-Steam shortcut (run with Steam DOWN).
# Same safe binary-VDF editor as add-to-steam.py: round-trip self-test, append-only.
import os, zlib, struct, shutil, re

USERCFG = os.path.expanduser("~/.steam/steam/userdata/121224686/config")
STEAMCFG = os.path.expanduser("~/.steam/steam/config")
EXE = os.path.expanduser("~/Games/Interstate76/probe/i76-input-probe.exe")
DIR = os.path.dirname(EXE)
NAME = "I76 Input Probe"
COMPAT = "GE-Proton10-12"

def read_str(b, i):
    j = b.index(0, i); return b[i:j].decode("utf-8", "replace"), j+1
def parse_map(b, i):
    d = []
    while True:
        t = b[i]; i += 1
        if t == 0x08: return d, i
        key, i = read_str(b, i)
        if t == 0x00: v, i = parse_map(b, i)
        elif t == 0x01: v, i = read_str(b, i)
        elif t == 0x02: v = struct.unpack("<i", b[i:i+4])[0]; i += 4
        else: raise ValueError(f"bad type {t} at {i}")
        d.append((t, key, v))
def dump_map(d):
    out = bytearray()
    for t, key, v in d:
        out.append(t); out += key.encode() + b"\x00"
        if t == 0x00: out += dump_map(v)
        elif t == 0x01: out += v.encode() + b"\x00"
        elif t == 0x02: out += struct.pack("<i", v)
    out.append(0x08); return bytes(out)
def find(d, key):
    for t,k,v in d:
        if k.lower()==key.lower(): return v

sc_path = os.path.join(USERCFG, "shortcuts.vdf")
raw = open(sc_path, "rb").read()
root, _ = parse_map(raw, 0)
assert dump_map(root) == raw, "round-trip mismatch - ABORT"
shortcuts = find(root, "shortcuts")
names = [find(v,"AppName") for t,k,v in shortcuts if t==0]
key = ('"%s"%s' % (EXE, NAME)).encode()
top = (zlib.crc32(key) & 0xFFFFFFFF) | 0x80000000
signed = top - 0x100000000
if NAME in names:
    print("probe shortcut already present"); raise SystemExit
idx = str(len([1 for t,k,v in shortcuts if t==0]))
shortcuts.append((0x00, idx, [
    (0x02,"appid",signed),(0x01,"AppName",NAME),(0x01,"Exe",'"%s"'%EXE),
    (0x01,"StartDir",'"%s"'%DIR),(0x01,"icon",""),(0x01,"ShortcutPath",""),
    (0x01,"LaunchOptions",""),(0x02,"IsHidden",0),(0x02,"AllowDesktopConfig",1),
    (0x02,"AllowOverlay",1),(0x02,"OpenVR",0),(0x02,"Devkit",0),
    (0x01,"DevkitGameID",""),(0x02,"DevkitOverrideAppID",0),(0x02,"LastPlayTime",0),
    (0x01,"FlatpakAppID",""),(0x00,"tags",[]),
]))
shutil.copy2(sc_path, sc_path+".probebak")
open(sc_path,"wb").write(dump_map(root))
print(f"probe shortcut appended idx {idx} (appid {top})")
# compat mapping -> Proton
cfg_path = os.path.join(STEAMCFG,"config.vdf")
cfg = open(cfg_path, encoding="utf-8").read()
if '"CompatToolMapping"' in cfg and ('"%d"'%top) not in cfg:
    block='\t\t\t\t\t"%d"\n\t\t\t\t\t{\n\t\t\t\t\t\t"name"\t\t"%s"\n\t\t\t\t\t\t"config"\t\t""\n\t\t\t\t\t\t"priority"\t\t"250"\n\t\t\t\t\t}\n'%(top,COMPAT)
    cfg=re.sub(r'("CompatToolMapping"\s*\{\n)', r'\1'+block, cfg, count=1)
    shutil.copy2(cfg_path, cfg_path+".probebak")
    open(cfg_path,"w",encoding="utf-8").write(cfg)
    print(f"compat mapping -> {COMPAT}")
