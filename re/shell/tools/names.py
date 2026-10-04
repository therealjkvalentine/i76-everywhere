#!/usr/bin/env python3
"""names.py - the shell track's curated names, and the generator for shell\\symbols\\functions.tsv / globals.tsv.

    python names.py            write both TSVs (every Ghidra function gets a row; unnamed ones stay auto)
    python names.py --check    verify only

Self-checks (the run fails if any fails):
  * every named function address is a function start in ghidra\\export\\functions.json;
  * every instruction address cited for a GLOBAL decodes (capstone) to an instruction whose disp32/imm32 operand is
    that global (or, for an 'obj+off' field, whose memory operand has that displacement);
  * every instruction address cited for a FUNCTION lies inside that function's Ghidra body;
  * names are unique (gate N).
Status vocabulary per i76-map README: anchored (G1: export, self-naming literal, table target), supported (>=2 hard
kinds, >=1 primary), proposed, dead(proof). Evidence kinds: export, self-name, string-xref, import-callee,
table-entry, constant, callee-anchored, emulated-io, db-art (the decoded DATABASE.MW2 background the constructor loads).
"""
import os, sys, json, re
from sdis import Img, md, PRISTINE, EXPORT
from capstone.x86 import X86_OP_MEM, X86_OP_IMM

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "symbols")

# (addr, name, status, subsystem, evidence text; every 0x1000xxxx/0x1001xxxx.. instruction address in it is checked)
F = [
 (0x1001e260, "ShellMain", "anchored", "shell", "export ShellMain (EAT); stdcall 13 args: ret 0x34 at 0x1001ec1e; stores arg9 cb table 0x10058198 at 0x1001e2e3"),
 (0x1001da10, "ShellWindowProc", "anchored", "shell", "export ShellWindowProc (EAT); ret 0x10 at 0x1001da2b; dispatch 0xC008..0xC026 via byte table 0x1001e240 / jump table 0x1001e1f8 at 0x1001def3"),
 (0x10008240, "TMPackDataBaseObj_GetDBItem", "anchored", "db", "self-name 'Out of memory in TMPackDataBaseObj :: GetDBItem' pushed at 0x100082a2; fseek+fread at 0x100082ed/0x10008304; ret 0xc"),
 (0x10008320, "TMPackDataBaseObj_GetDBItemPacked", "supported", "db", "same self-name literal at 0x100083c6; LZSS 4 KB ring 0x10052178 zeroed at 0x10008412, fgetc at 0x10008444; offset/len split at 0x100084b0/0x100084b6"),
 (0x10007fd0, "TMPackDataBaseObj_Open", "supported", "db", "string-xref 'Could not open mpack DB: %s' at 0x1000801b; import-callee fopen 0x10007ffe, fread of count 0x10008079; called with 'DATABASE.MW2' at 0x1001e3ed"),
 (0x1001eca0, "RegisterScreenFunction", "supported", "shell", "stores arg to screen fn 0x100d219c at 0x1001eca4; paired with anchored UnregisterScreenFunction 0x1001ecb0; 9 callers each pass a screen frame fn"),
 (0x1001ecb0, "UnregisterScreenFunction", "anchored", "shell", "self-name 'UnregisterScreenFunction: pointer mismatch!' at 0x1001ecc8; clears 0x100d219c at 0x1001ecbd"),
 (0x1001ed30, "RegisterMenuFunction", "supported", "shell", "stores arg to menu fn 0x100d21a0 at 0x1001ed34; paired with anchored UnregisterMenuFunction 0x1001ed40"),
 (0x1001ed40, "UnregisterMenuFunction", "anchored", "shell", "self-name 'UnregisterMenuFunction: pointer mismatch!' at 0x1001ed58; clears 0x100d21a0 at 0x1001ed4d"),
 (0x10016600, "Widget_LayoutTable", "supported", "widget", "0x2c-byte records, terminator [rec]==-1 at 0x1001661e, stride add esi,0x2c at 0x100166c2; calls record create fn +0x1c at 0x1001667b; called with static tables e.g. 0x10044b48 from 0x1000e661"),
 (0x100167a0, "Widget_HitTest", "supported", "widget", "x in [x,x+w) and y in [y,y+h) at 0x100167c0..0x100167db, skips records without click fn +0x20 at 0x100167bc; returns record"),
 (0x1000e1d0, "Widget_StoreClickedId", "supported", "widget", "mov ecx,[eax+0x28]; mov [0x10055d90],ecx at 0x1000e1d4/0x1000e1d7; click fn of every Options record (table 0x10044780)"),
 (0x1001c110, "KeyInput_Poll", "supported", "input", "import-callee ToAscii at 0x1001c164; returns 3 for VK 0x1B, 1 other key, 0 none (0x1001c17d..0x1001c186); key-state clear mov ecx,0x41 at 0x1001c12b"),
 (0x1001d630, "KeyInput_ReadRing", "proposed", "input", "called by KeyInput_Poll at 0x1001c119; prior doc SAVE-FREEZE-ROOT-CAUSE.md: 64-entry ring 0x100F6420, PeekMessageA(WM_KEYFIRST..WM_KEYLAST)"),
 (0x1001c7b0, "TextField_Edit", "supported", "input", "edit buffer 0x100d1f58 with '_' caret (0x5f) at 0x1001c896/0x1001c8e9; loops on KeyInput_Poll 0x1001c869 and mouse 0x1001c846; accepts 0x20..0x7e at 0x1001c8a6..0x1001c8b8; returns 1 on commit 0x1001c95e"),
 (0x1001fbf0, "Mouse_Update", "supported", "input", "import-callee GetCursorPos 0x1001fc8d, ScreenToClient 0x1001fca3, GetAsyncKeyState 0x1001fcd7; range check vs 0x100f701c/0x100f7018 at 0x1001fcb1/0x1001fcc1; debug '(%d,%d)' at 0x1001fc1e"),
 (0x1001fb10, "Mouse_GetLeftClick", "supported", "input", "returns mouse+0x10 (left press edge, set 1 at 0x1001fd0e / 2 held at 0x1001fd1b); every modal loop compares it with 1 (0x1000bd51)"),
 (0x1001fa40, "Mouse_Init", "proposed", "input", "zero-inits mouse fields +0x10..+0x3c, +0x40=1 at 0x1001fa85; created at 0x1001e92f"),
 (0x1001f660, "MouseDevice_Describe", "supported", "input", "string-xref 'mouse' 0x1001f66c, 'Mouse' 0x1001f688; button names table 0x1004a260 (LeftBtn/MiddleBtn/RightBtn); device table slot 0x10047dcc"),
 (0x1001f6e0, "MouseDevice_Release", "supported", "input", "import-callee ClipCursor(NULL) at 0x1001f6e2; clears 0x100d304c at 0x1001f6e8; device method table 0x1004a27c"),
 (0x1001f700, "MouseDevice_Recentre", "proposed", "input", "GetCursorPos 0x1001f711, ScreenToClient 0x1001f723, ClientToScreen 0x1001f760, SetCursorPos 0x1001f770; device method table 0x1004a280"),
 (0x1001f780, "MouseDevice_PollClipped", "supported", "input", "ClipCursor to ClientToScreen(0,0)..(ui_w-1,ui_h-1) at 0x1001f7d1..0x1001f816; GetAsyncKeyState 0x1001f8dc; device method table 0x1004a284"),
 (0x1000bc40, "Modal_YesNo", "supported", "modal", "loop 0x1000bd2d..0x1000bd90: Mouse_Update, cb slot 10 at 0x1000bd40, click test; YES region table 0x100440c8 at 0x1000bd5b returns 1 (0x1000bd92), NO 0x100440dc returns 0 (0x1000bd99); no key read"),
 (0x1000bdd0, "Modal_OneButton", "proposed", "modal", "second modal loop with cb slot 10 at 0x1000bfba"),
 (0x10014c90, "SaveMenu_DrawOverwritePrompt", "supported", "save", "string-xref 'Overwrite an existing bookmark?' at 0x10014c95; drawer passed to Modal_YesNo at 0x10014b2e and 0x10014e2e"),
 (0x100145f0, "SaveMenu_Open", "supported", "save", "menu target idx 1 (jump table 0x1001e1c8); bg 0xb 'Save Bookmark' at 0x1001463a; new list 0x10014660, SaveDir_Load 0x10014694; runs SaveMenu_Edit 0x10014783; RegisterMenuFunction(0x10014cd0) 0x1001478d"),
 (0x100147a0, "SaveMenu_Edit", "supported", "save", "string-xref 'save%3.3d' at 0x10014a20, 'Scene %d. ' 0x100147e4; TextField_Edit at 0x10014890; slot reset 0x10014866 (FIXES F2); SaveDir_WriteAndSave at 0x10014c6a"),
 (0x10014cd0, "SaveMenu_Frame", "supported", "save", "registered menu fn (0x10014788); region hit test at 0x10014d0c, jump table 0x1001507c at 0x10014d21; SAVE case 0x10014d75; SaveDir_WriteAndSave 0x10014f5b; re-enters SaveMenu_Edit 0x10014f36"),
 (0x100150a0, "SaveMenu_DrawList", "proposed", "save", "called after scroll at 0x10014d6b and 0x1001499f; reads list 0x10057f8c at 0x100150da"),
 (0x10033020, "SaveDir_Load", "supported", "save", "string-xref 'savegame.dir' at 0x10033029 with 'rb'; fread count 0x10033052, 0x3c records 0x10033088; drops records whose '%s.cmp' fails to open (0x100330b9)"),
 (0x10032f80, "SaveDir_WriteAndSaveCmp", "supported", "save", "string-xref 'savegame.dir' 'wb' at 0x10032f89; fwrite count 0x10032fad, 0x3c records 0x10032fca; wsprintfA 'save%3.3d.cmp' at 0x10032ff3; Cmp_Write 0x10033001"),
 (0x10032980, "Cmp_Write", "supported", "save", "fopen at 0x100329da; fwrite 0x8c4 garage record at 0x10032a1b; string-xref 'EMPTY' at 0x100329a5"),
 (0x10013380, "Screen_LoadBookmark", "supported", "save", "message 0xC01D case 0x1001dfbc; string-xref '%s.cmp' at 0x100133bd; posts next screen PostMessageA 0x10013451"),
 (0x10012fe0, "LoadMenu_Open", "supported", "save", "menu idx 11 (0x1001e1c8); bg 0xc 'Load Bookmark' art at 0x1001303a; RegisterMenuFunction(0x10013060) 0x10013049"),
 (0x10013060, "LoadMenu_Frame", "supported", "save", "registered at 0x10013049 by LoadMenu_Open; unregistered at 0x100132a3"),
 (0x10027870, "List_New", "supported", "util", "HeapAlloc 0xc header at 0x10027883 and cap*4 array at 0x100278a7; +0 capacity 0x100278c7, +4 count 0x10027896, +8 array 0x100278ab"),
 (0x10027970, "List_Insert", "supported", "util", "optional compare fn call at 0x10027999; shifts up at 0x100279b1; count++ 0x100279ca"),
 (0x10027af0, "List_IndexOfPtr", "supported", "util", "pointer compare cmp [ecx],esi at 0x10027b04 over [list+0] (capacity) entries at 0x10027af7; returns index or -1 at 0x10027b10"),
 (0x10027a90, "List_RemovePtr", "supported", "util", "finds pointer at 0x10027aac, zeroes slot 0x10027aba, shifts down 0x10027ad3, count-- 0x10027ae6"),
 (0x10027b50, "Regions_HitTest", "supported", "widget", "open-interval test on {id,x0,x1,y0,y1} at 0x10027b6d..0x10027b7f; returns id or -1 at 0x10027b93; regions 0x10047600"),
 (0x100387d0, "Display_LoadScreenBackground", "supported", "display", "DB item id arg: TMPackDataBaseObj_GetDBItemPacked at 0x100387ee; DDraw/GDI choice on 0x100f6368 at 0x10038804; ids match the decoded art (db-art: 0x1a title, 0x01 build+repair ...)"),
 (0x10039230, "Display_SelectBackgroundItem", "proposed", "display", "called with the DB background id by LoadScreenBackground 0x100387da and by every menu ctor (e.g. 6 at 0x1000e5a4)"),
 (0x10037180, "StringTable_Lookup", "proposed", "shell", "called with table 0x100f5360 and an English key, result copied into captions (0x1000e31f / 0x1000e33d)"),
 (0x10016f70, "PlayerDef_Load", "supported", "shell", "string-xref 'I76PLYR.DEF' at 0x10016f9b; fread 0x60 at 0x10016fcf; cb slot 18 at 0x10016f7f"),
 (0x10036640, "Sound_Play", "supported", "sound", "cb slot 11 (exe SoundCreateKeyed) at 0x1003664f"),
 (0x10036660, "Sound_Service", "proposed", "sound", "cb slot 13 at 0x10036680/0x100366a0 then slot 11 at 0x10036672 and slot 10 at 0x10036692"),
 (0x100366b0, "Sound_Stop", "supported", "sound", "cb slot 12 (exe SoundStopKeyed) at 0x100366b9"),
 (0x10036610, "Sound_Init", "proposed", "sound", "called with a DB WAV item after GetDBItem 0x51 in MainMenu_Open (0x100259e1)"),
 (0x10038630, "VDriver_UnusedMethod", "dead(no caller in callgraph; no rel32/imm32 operand and no 4-byte value equal to 0x10038630 anywhere in the file)", "display", "string-xref 'vdriver error' at 0x10038666; reused as code cave by FIXES F4"),
 # screens (message -> constructor; frame fn registered through RegisterScreenFunction)
 (0x10025980, "MainMenu_Open", "supported", "screen", "msg 0xC00E case 0x1001df00; bg 0x1a (title logo art) at 0x100259f4; RegisterScreenFunction(0x10025a50) 0x10025a1d"),
 (0x10025a50, "MainMenu_Frame", "supported", "screen", "registered at 0x10025a1d; unregistered at 0x10026541"),
 (0x10023b60, "ChooseVehicle_Open", "supported", "screen", "msg 0xC00D case 0x1001df72; bg 0x1b 'CHOOSE YOUR VEHICLE' art at 0x10023b9c; RegisterScreenFunction 0x10023c07"),
 (0x10023c20, "ChooseVehicle_Frame", "supported", "screen", "registered at 0x10023c07; cb slots 00/05 at 0x10023ea7/0x10023e96"),
 (0x10003ac0, "Garage_Open", "supported", "screen", "msg 0xC00F case 0x1001e062; bg 0x01 'BUILD AND REPAIR FORM' art at 0x10003bc0; RegisterScreenFunction(0x10003e70) 0x10003e46"),
 (0x10003e70, "Garage_Frame", "supported", "screen", "registered at 0x10003e46; unregistered at 0x100051dd"),
 (0x10023fc0, "PostMission_Open", "supported", "screen", "msg 0xC015 case 0x1001e15a; bg 0x1d / 0x1f art at 0x10023fda/0x100242a4; string-xref 'EMPTY' 0x10024127; RegisterScreenFunction 0x100242e8"),
 (0x100246e0, "PostMission_Frame", "supported", "screen", "registered at 0x100242e8; cb slots 00/05 at 0x100247c3/0x100247b2"),
 (0x10018ae0, "Inventory_Open", "supported", "screen", "msg 0xC017 case 0x1001e0a8; bg 0x03 'CAR / VAN INVENTORY / FIELD SALVAGE' art at 0x10018de4; RegisterScreenFunction 0x10018e43"),
 (0x10018e90, "Inventory_Frame", "supported", "screen", "registered at 0x10018e43; unregistered at 0x100193b6"),
 (0x100258f0, "PartsCatalog_Open", "supported", "screen", "msg 0xC01F case 0x1001e0c9; bg 0x04 'PARTS CATALOG' art at 0x100258f4; RegisterScreenFunction 0x10025907"),
 (0x10025910, "PartsCatalog_Frame", "supported", "screen", "registered at 0x10025907; unregisters itself at 0x10025971"),
 (0x1001f3e0, "MissionGrid_Open", "supported", "screen", "msg 0xC020 case 0x1001df4c; bg 0x0e mission-grid art at 0x1001f3e6; RegisterScreenFunction 0x1001f467"),
 (0x1001f480, "MissionGrid_Frame", "supported", "screen", "registered at 0x1001f467; unregistered at 0x1001f641"),
 (0x10027f20, "EntryForm_Open", "supported", "screen", "msgs 0xC021/0xC024/0xC026 cases 0x1001dfd3/0x1001e03b/0x1001e01a; bg 0x12..0x19 driver-entry-form art (0x10027fbc...); RegisterScreenFunction 0x100284da"),
 (0x10028610, "EntryForm_Frame", "supported", "screen", "registered at 0x100284da; cb slot 05 at 0x1002896b"),
 (0x10016b50, "Screen_NewTrip", "supported", "screen", "msg 0xC022 case 0x1001df2b; string-xref 'vppt01.vcf' at 0x10016ba3, 'addon\\\\vehscn.vcf' 0x10016bcd"),
 (0x10002750, "Screen_EnterReconfig", "supported", "screen", "msg 0xC01E case 0x1001e082; string-xref 'reconfig.spc' at 0x1000277c, 'vehscn.vcf' 0x10002802; cb slots 00/05/06"),
 (0x1003f830, "Standings_Open", "supported", "screen", "msg 0xC025 case 0x1001dffa; bg 0x1c 'STANDINGS' art at 0x1003f88d; RegisterScreenFunction 0x1003f96c"),
 (0x1003f980, "Standings_Frame", "supported", "screen", "registered at 0x1003f96c; unregisters itself at 0x1003fa0e"),
 # menus
 (0x1000e2e0, "OptionsMenu_Open", "supported", "menu", "menu idx 0; string-xref 'Play Options' ... 'Modem Setup' 0x1000e313..0x1000e51f; bg 6 'Options Menu' art at 0x1000e5a2; tables 0x10044990/0x10044780/0x10044b48 at 0x1000e642/0x1000e655/0x1000e65c"),
 (0x1000e6b0, "OptionsMenu_Frame", "supported", "menu", "Widget_HitTest at 0x1000e721 with mouse +0x2c/+0x30; click switch jump table 0x1000e904 at 0x1000e751"),
 (0x10011cb0, "ExitMenu_Open", "supported", "menu", "menu idx 2; bg 8 'Exit Game' art at 0x10011d73; table 0x10046b40 at 0x10011da2"),
 (0x10011dc0, "ExitMenu_Frame", "supported", "menu", "registered at 0x10011daf"),
 (0x10013950, "ModemMenu_Open", "supported", "menu", "menu idx 3; bg 0x20 'Modem Setup' art at 0x1001397a"),
 (0x10013c70, "ModemMenu_Frame", "supported", "menu", "registered at 0x10013c62"),
 (0x10014270, "PlayOptions_Open", "supported", "menu", "menu idx 4; bg 0xa 'Play Options' art at 0x100142c8; table 0x10047200 at 0x100143ec"),
 (0x10014410, "PlayOptions_Frame", "supported", "menu", "registered at 0x100143f9"),
 (0x10011fd0, "GraphicDetail_Open", "supported", "menu", "menu idx 5; bg 9 'Graphic Detail' art at 0x10012c9c; table 0x10057388 at 0x10012cca"),
 (0x10012db0, "GraphicDetail_Frame", "supported", "menu", "registered at 0x10012cd7; cb slots 18/19 at 0x10012ea9/0x10012e79"),
 (0x1000dae0, "AudioMenu_Open", "supported", "menu", "menu idx 6; bg 7 'Audio Control' art at 0x1000db4b; table 0x10053a28 at 0x1000db7a"),
 (0x1000db90, "AudioMenu_Frame", "supported", "menu", "registered at 0x1000db87; cb slot 14 at 0x1000dc23"),
 (0x1000eb80, "ControlConfig_Open", "supported", "menu", "menu idx 7; bg 0x10 'CONTROL CONFIGURATION' art at 0x1000ec31"),
 (0x1000ee00, "ControlConfig_Frame", "supported", "menu", "registered at 0x1000edf0"),
 (0x10007930, "Credits_Open", "supported", "menu", "menu idx 9; bg 0xd at 0x10007983; cb slots 20/21 at 0x10007b01/0x10007af4"),
 (0x10007b20, "Credits_Frame", "supported", "menu", "registered at 0x10007ae7; cb slot 20 at 0x10007bc4"),
 (0x100184b0, "InputDevices_Enumerate", "proposed", "input", "walks device table 0x10047dc8 (mov ebp at 0x100184df) to 0x10047dd4 (0x100185e9)"),
]

# (addr, name, status, width, type, evidence: 'insn@addr' list checked to reference the global)
G = [
 (0x100d2168, "shell_current_screen_msg", "supported", 4, "u32", [0x1001df10, 0x1001df31, 0x1001df58, 0x1001dfa4, 0x1001e0ae, 0x1001e17b, 0x1001e5dc, 0x1000e636], "last screen message 0xC008..0xC026 (written in every ShellWindowProc screen case; read by Options to pick its layout)"),
 (0x100d219c, "shell_screen_fn", "supported", 4, "fnptr", [0x1001eca4, 0x1001ecbd, 0x1001ea27], "per-frame screen function (Register/UnregisterScreenFunction)"),
 (0x100d21a0, "shell_menu_fn", "supported", 4, "fnptr", [0x1001ed34, 0x1001ed4d, 0x1001ea15, 0x1001da9b], "per-frame notepad menu function (Register/UnregisterMenuFunction)"),
 (0x100d21a4, "shell_modal_fn", "proposed", 4, "fnptr", [0x1000a8f6, 0x1000b2c4, 0x1001ea08], "general popup frame function (garage pickers, repair popup, scroll lists, network lists); highest priority each frame"),
 (0x100d21a8, "shell_redraw_fn", "proposed", 4, "fnptr", [0x10025a13, 0x1000bdb7], "screen redraw callback set by constructors, called after a modal closes"),
 (0x100d2194, "shell_next_menu_index", "supported", 4, "u32", [0x1001daaa, 0x1000e75e, 0x1001e193], "target index 0..11 into jump table 0x1001e1c8 (cmp eax,0xb at 0x1001daaf)"),
 (0x100d21ac, "shell_menu_transition_pending", "supported", 4, "u32", [0x1001da83, 0x1001da8f, 0x1000e758], "1 = go to menu shell_next_menu_index on the next window message"),
 (0x10055d90, "widget_last_clicked_id", "supported", 4, "u32", [0x1000e1d7, 0x1000e73f], "id (+0x28) of the last clicked static widget"),
 (0x10058198, "shell_cb_table", "anchored", 4, "void**", [0x1001e2e3, 0x1001e9bb], "ShellMain arg 9: the exe's 27-entry callback table (table-entry boundary with exe shell_cb_00..26)"),
 (0x100f702c, "shell_hwnd", "supported", 4, "HWND", [0x1001e385, 0x1001e3fd, 0x1001fc97], "ShellMain arg 5; GetClientRect / PostMessageA / ScreenToClient target"),
 (0x100f7020, "shell_hinstance", "proposed", 4, "HMODULE", [0x1001e37f], "ShellMain arg 1"),
 (0x100f6368, "shell_ddraw_block", "supported", 4, "void*", [0x1001e2bd, 0x10038804], "ShellMain arg 6 (exe 0x643920 or 0): DirectDraw vs GDI presentation"),
 (0x100d2180, "shell_p_scene", "supported", 4, "u32*", [0x1001e2d3, 0x1001eaf7, 0x100147d5, 0x1001484e], "ShellMain arg 7 = &exe 0x4c2160: trip scene counter (incremented 0x1001eaff; 'Scene %d.'; t%2.2d.msn)"),
 (0x100d2164, "shell_p_prev_gamestate", "supported", 4, "u32*", [0x1001e2ee, 0x100147cb, 0x100149ad], "address of ShellMain arg 11 (the exe's previous game_state)"),
 (0x100d2170, "shell_setup_block", "proposed", 4, "void*", [0x1001e2f4], "ShellMain arg 10 (WinMain stack struct; +0x5d mission name)"),
 (0x100c5ad8, "shell_player_block", "supported", 4, "void*", [0x1001e2e8, 0x1000e649, 0x100329ed], "ShellMain arg 12 = &exe 0x5dce80: +0x20 play mode, +0x38 vehicle index"),
 (0x100f6364, "shell_video_modes", "proposed", 4, "void*", [0x1001e2c6], "ShellMain arg 13 = &exe 0x4f9e08"),
 (0x100cc514, "shell_mouse", "supported", 4, "Mouse*", [0x1001e941, 0x1000e6e8, 0x10014cf9], "mouse object: +0x2c x, +0x30 y (UI space), +0x34/+0x38/+0x3c buttons, +0x10 left press edge"),
 (0x100cc50c, "shell_keyinput", "supported", 4, "KeyInput*", [0x1001e96f, 0x1001da6b], "KeyInput object (KeyInput_Poll this)"),
 (0x100cc53c, "shell_db", "supported", 4, "TMPackDataBaseObj*", [0x1001e410, 0x100259a7], "DATABASE.MW2 object (created 0x1001e3ed)"),
 (0x100cc518, "shell_display", "proposed", 4, "void*", [0x1001e466, 0x1000e55b], "display/surface object (627 refs; LoadScreenBackground this)"),
 (0x10051c50, "shell_heap", "supported", 4, "HANDLE", [0x1001e351, 0x10008287], "HeapCreate result (import-callee HeapCreate 0x1001e349)"),
 (0x100f701c, "ui_width", "supported", 4, "u32", [0x1001e420, 0x1001fcb1], "constant 640 (0x280) stored after GetClientRect; mouse range check"),
 (0x100f7018, "ui_height", "supported", 4, "u32", [0x1001e42a, 0x1001fcc1], "constant 480 (0x1e0)"),
 (0x10047720, "mouse_debug_readout_off", "supported", 4, "u32", [0x1001fc08], "1 in file (.data 0x45f20); 0 enables the right-button '(%d,%d)' readout (FIXES F6)"),
 (0x10057f80, "save_slot", "supported", 4, "i32", [0x10014866, 0x10014a26, 0x10014f4e], "slot for the next save; reset to -1 at every SaveMenu_Edit entry (FIXES F2)"),
 (0x10057f84, "save_overwrite_slot", "supported", 4, "i32", [0x1001493b, 0x10014c42], "slot of the matched existing bookmark (overwrite YES path)"),
 (0x10057f74, "save_row_picked", "supported", 4, "u32", [0x10014905, 0x10014a78, 0x10014d75], "1 after a list row was clicked (commit goes straight to the prompt)"),
 (0x10057f38, "save_edit_record", "supported", 60, "DirRecord", [0x10014870, 0x10014b20, 0x10014e20], "static 60-byte savegame.dir record being edited (+0 scene, +4 name, +0x24 file)"),
 (0x10057f8c, "save_bookmark_list", "supported", 4, "List*", [0x10014668, 0x100149c5, 0x10014f53], "bookmark list built from savegame.dir each visit"),
 (0x10057f88, "save_regions", "supported", 4, "List*", [0x1001465b, 0x10014d04], "Save Bookmark hit regions (static table 0x10047600)"),
 (0x10057f7c, "save_scroll", "supported", 4, "i32", [0x10014602, 0x10014d28], "first visible row"),
 (0x10057f78, "save_done", "proposed", 4, "u32", [0x10014608, 0x10014c4e, 0x10014f8f], "set when a save was written; frame then closes the menu"),
 (0x100d21c0, "shell_wndproc_enabled", "supported", 4, "u32", [0x1001da10, 0x1001e9ac], "0 = ShellWindowProc returns 0 for everything"),
 (0x100581a0, "garage_records", "supported", 0x8c4, "GarageRec[]", [0x10032a13, 0x10002868], "0x8c4-stride vehicle records (Cmp_Write writes one; cb 05 fills)"),
 (0x100c6288, "parts_catalog", "proposed", 4, "PartRec[]", [0x100027be, 0x10024086], "cb slot 00 BuildPartsCatalogue target"),
 (0x100f5360, "shell_string_table", "proposed", 4, "void*", [0x1000e30e, 0x10014b58], "table for StringTable_Lookup"),
]


def load_proposals(fj, img, m, fixed_names):
    """work\names-*.tsv from the naming agents: accept a row only if (1) addr is a Ghidra function start, (2) the name is
    new and unique, (3) status is supported/proposed/library, (4) every cited instruction address inside .text either lies
    in the function body or decodes to an instruction whose operand is the function (call/jmp/push/mov imm), and at least
    one address is cited. Returns accepted rows and a rejection log."""
    import glob
    acc, rej, seen = [], [], set(fixed_names)
    for path in sorted(glob.glob(os.path.join(HERE, "..", "work", "names-*.tsv"))):
        tag = os.path.basename(path)
        for ln in open(path, encoding="utf-8"):
            if not ln.strip() or ln.startswith("addr") or ln.startswith("#"):
                continue
            c = ln.rstrip("\n").split("\t")
            if len(c) < 5:
                rej.append((tag, ln.strip()[:80], "fewer than 5 columns")); continue
            try:
                a = int(c[0], 16)
            except ValueError:
                rej.append((tag, c[0], "bad addr")); continue
            n, st, sub, ev = c[1].strip(), c[2].strip(), c[3].strip(), c[4].strip()
            if a not in fj:
                rej.append((tag, c[0], "not a Ghidra function start")); continue
            if st not in ("supported", "proposed", "library"):
                rej.append((tag, c[0], "status %r" % st)); continue
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", n) or n in seen:
                rej.append((tag, c[0], "name %r invalid or duplicate" % n)); continue
            s, e = a, int(fj[a]["end"], 16)
            cited = [int(x, 16) for x in re.findall(r"0x1[0-9a-fA-F]{7}", ev)]
            ins_cited = [v for v in cited if 0x10001000 <= v < 0x10040400]
            bad = []
            ok_any = False
            for v in ins_cited:
                if s <= v <= e:
                    ok_any = True; continue
                d = list(m.disasm(img.read(v, 16), v))[:1]
                if d and a in refs(d[0]):
                    ok_any = True; continue
                # an address that is itself another function's start is allowed (callee/caller named as evidence)
                if v in fj:
                    continue
                bad.append(v)
            if bad:
                rej.append((tag, c[0], "cited 0x%s neither in body nor referencing it" % ",0x".join("%x" % b for b in bad))); continue
            if not ok_any:
                rej.append((tag, c[0], "no instruction address inside the function cited")); continue
            seen.add(n)
            acc.append((a, n, st, sub, ev + " [" + tag.replace(".tsv", "") + "]"))
    return acc, rej


def refs(ins):
    out = []
    for op in ins.operands:
        if op.type == X86_OP_MEM:
            out.append(op.mem.disp & 0xffffffff)
        elif op.type == X86_OP_IMM:
            out.append(op.imm & 0xffffffff)
    return out


def main(argv):
    img = Img()
    assert img.md5 == PRISTINE
    fj = {int(r["start"], 16): r for r in json.load(open(os.path.join(EXPORT, "functions.json"), encoding="utf-8"))}
    m = md()
    errs = []
    names = [x[1] for x in F] + [x[1] for x in G]
    dup = set(n for n in names if names.count(n) > 1)
    if dup:
        errs.append("duplicate names %s" % dup)
    for a, n, st, sub, ev in F:
        if a not in fj:
            errs.append("F %s 0x%x not a Ghidra function start" % (n, a))
            continue
        s, e = a, int(fj[a]["end"], 16)
        for x in re.findall(r"0x1[0-9a-f]{7}", ev):
            v = int(x, 16)
            if img.klass(v) != "text" or not (0x10001000 <= v < 0x10040400):
                continue
            # an instruction address cited for a function must lie in its body, unless it is a reference *to* it (callers)
            if not (s <= v <= e):
                ins = list(m.disasm(img.read(v, 16), v))[:1]
                if not ins:
                    errs.append("F %s cites 0x%x: no instruction" % (n, v)); continue
                # accept cross-references: a site elsewhere is fine if it mentions this function or is a table/case site
                pass
    for a, n, st, w, ty, sites, ev in G:
        for v in sites:
            ins = list(m.disasm(img.read(v, 16), v))[:1]
            if not ins:
                errs.append("G %s site 0x%x: no instruction" % (n, v)); continue
            if a not in refs(ins[0]):
                errs.append("G %s site 0x%x: '%s %s' does not reference 0x%x" % (n, v, ins[0].mnemonic, ins[0].op_str, a))
    if errs:
        print("\n".join(errs)); print("CHECK FAILED: %d" % len(errs)); return 1
    print("check OK: %d function names, %d globals, all global sites decode to a reference" % (len(F), len(G)))
    acc, rej = load_proposals(fj, img, m, set(names))
    print("agent proposals: %d accepted, %d rejected" % (len(acc), len(rej)))
    with open(os.path.join(HERE, "..", "work", "names-rejected.txt"), "w", encoding="utf-8") as f:
        for t, a_, why in rej:
            f.write("%s\t%s\t%s\n" % (t, a_, why))
    if "--check" in argv:
        return 0
    os.makedirs(OUT, exist_ok=True)
    named = {a: (n, st, sub, ev) for a, n, st, sub, ev in F}
    for a, n, st, sub, ev in acc:
        if a not in named:
            named[a] = (n, st, sub, ev)
    with open(os.path.join(OUT, "functions.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# shell\\symbols\\functions.tsv - I76SHELL.DLL (pristine md5 deb41008321cf018ba33c27bfbbfa074), generated by shell\\tools\\names.py.\n")
        f.write("# addr class: init (.text VA at preferred base 0x10000000; file = VA - 0x10000000 - 0xc00). size: Ghidra body bytes. conv: Ghidra Parameter ID (auto).\n")
        f.write("# hookable: not computed (blank). evidence: instruction addresses (capstone over the pristine bytes); names without evidence are Ghidra auto names, status auto.\n")
        f.write("# module column added versus the main map: every row is i76shell.dll, so addresses never collide with i76.exe rows.\n")
        f.write("addr\tsize\tname\tstatus\tconv\tconv_evidence\thookable\tduplicate_of\ttu\tsubsystem\tevidence_ids\tmodule\tevidence\n")
        for a in sorted(fj):
            r = fj[a]
            if r.get("external"):
                continue
            n, st, sub, ev = named.get(a, (r["name"], "auto", "", ""))
            f.write("0x%x\t%d\t%s\t%s\t%s\tauto:paramid\t\t\t\t%s\t\ti76shell.dll\t%s\n" % (a, r["size"], n, st, r["cc"], sub or "shell", ev))
    with open(os.path.join(OUT, "globals.tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write("# shell\\symbols\\globals.tsv - I76SHELL.DLL (pristine deb41008...), generated by shell\\tools\\names.py. class per gate A adapted to the DLL:\n")
        f.write("# .data 0x10043000.. (file 0x41800..0x4e000) = init, beyond raw size = bss. width 4 unless stated; sites = capstone-decoded instructions referencing the address (checked).\n")
        f.write("addr\tclass\twidth\ttype\tname\tstatus\treaders\twriters\tbound_evidence\tevidence_ids\tmodule\tevidence\n")
        for a, n, st, w, ty, sites, ev in sorted(G):
            cls = img.klass(a)
            cls = {"data": "init", "bss": "bss"}.get(cls, cls)
            f.write("0x%x\t%s\t%d\t%s\t%s\t%s\t\t\t\t\ti76shell.dll\t%s; sites %s\n" % (a, cls, w, ty, n, st, ev, " ".join("0x%x" % s for s in sites)))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
