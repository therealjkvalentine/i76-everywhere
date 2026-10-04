// ExportBaseline.java - headless post-analysis export for the I76 stock exe baseline.
// Ported 2026-09-04 (Task 2) from recon-2026-09-04/recon/fp-ghidra/scripts; only the default outDir changed.
// Usage: -postScript ExportBaseline.java <outDir>
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.*;
import ghidra.program.model.address.*;
import ghidra.program.model.data.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import ghidra.program.model.symbol.*;
import ghidra.program.model.scalar.Scalar;
import ghidra.program.model.lang.Register;
import java.io.*;
import java.util.*;

public class ExportBaseline extends GhidraScript {
    String outDir;
    Listing listing; ReferenceManager refMgr; Memory mem; FunctionManager fm; SymbolTable st; BookmarkManager bm;
    MemoryBlock textBlk;
    Map<Address,Integer> strRefsPerFunc = new HashMap<>();
    Map<Address,Integer> vcallPerFunc = new HashMap<>();
    Map<Address,Integer> x87PerFunc = new HashMap<>();
    Map<String,Address> iatByName = new HashMap<>();   // import name -> IAT slot address

    PrintWriter open(String name) throws IOException {
        return new PrintWriter(new BufferedWriter(new OutputStreamWriter(new FileOutputStream(new File(outDir, name)), "UTF-8")));
    }
    static String q(String s) { if (s == null) return ""; return "\"" + s.replace("\"", "\"\"").replace("\n","\\n").replace("\r","\\r") + "\""; }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        outDir = args.length > 0 ? args[0] : "C:\\Users\\james\\i76-map\\ghidra\\export";
        new File(outDir).mkdirs();
        new File(outDir, "decomp").mkdirs();
        listing = currentProgram.getListing(); refMgr = currentProgram.getReferenceManager(); mem = currentProgram.getMemory();
        fm = currentProgram.getFunctionManager(); st = currentProgram.getSymbolTable(); bm = currentProgram.getBookmarkManager();
        for (MemoryBlock b : mem.getBlocks()) if (b.getName().equals(".text")) textBlk = b;
        println("ExportBaseline: outDir=" + outDir);
        exportImports();
        exportStrings();
        exportStats();      // fills vcallPerFunc / x87PerFunc
        exportFunctions();  // uses the per-function maps
        exportDataLayout();
        exportDecomp();
        println("ExportBaseline: done");
    }

    // ---------------- functions.csv ----------------
    void exportFunctions() throws IOException {
        PrintWriter w = open("functions.csv");
        w.println("address,name,size,calling_convention,param_count,is_thunk,name_source,fid_named,bookmark_categories,string_refs,vtable_calls,x87_instrs");
        for (Function f : fm.getFunctions(true)) {
            Address a = f.getEntryPoint();
            Bookmark[] bks = bm.getBookmarks(a);
            StringBuilder cats = new StringBuilder(); boolean fid = false;
            for (Bookmark b : bks) { if (cats.length()>0) cats.append('|'); cats.append(b.getTypeString()).append(':').append(b.getCategory()); if (b.getCategory() != null && b.getCategory().contains("Function ID")) fid = true; }
            w.println(a + "," + q(f.getName()) + "," + f.getBody().getNumAddresses() + "," + f.getCallingConventionName() + "," + f.getParameterCount() + "," + f.isThunk() + "," + f.getSymbol().getSource() + "," + fid + "," + q(cats.toString()) + "," + strRefsPerFunc.getOrDefault(a,0) + "," + vcallPerFunc.getOrDefault(a,0) + "," + x87PerFunc.getOrDefault(a,0));
        }
        w.close();
    }

    // ---------------- imports_xrefs.csv ----------------
    void exportImports() throws IOException {
        PrintWriter w = open("imports_xrefs.csv");
        w.println("library,name,iat_slot,iat_refs_from_code,thunk_addr,thunk_refs,total_call_sites,referencing_functions");
        ExternalManager em = currentProgram.getExternalManager();
        for (String lib : em.getExternalLibraryNames()) {
            ExternalLocationIterator it = em.getExternalLocations(lib);
            while (it.hasNext()) {
                ExternalLocation loc = it.next();
                Address ext = loc.getExternalSpaceAddress();
                Set<Address> funcs = new TreeSet<>();
                Address iat = null; int iatRefs = 0; Address thunk = null; int thunkRefs = 0;
                for (Reference r : refMgr.getReferencesTo(ext)) {
                    Address from = r.getFromAddress();
                    if (listing.getInstructionAt(from) != null) { // direct code ref to external (rare)
                        Function cf = fm.getFunctionContaining(from); if (cf != null) funcs.add(cf.getEntryPoint());
                        iatRefs++; continue;
                    }
                    iat = from;
                    for (Reference r2 : refMgr.getReferencesTo(from)) {
                        Address f2 = r2.getFromAddress();
                        Instruction ins = listing.getInstructionAt(f2);
                        if (ins == null) continue;
                        Function cf = fm.getFunctionContaining(f2);
                        if (cf != null && cf.isThunk() && cf.getBody().getNumAddresses() <= 8) {
                            thunk = cf.getEntryPoint();
                            for (Reference r3 : refMgr.getReferencesTo(thunk)) { Function cf3 = fm.getFunctionContaining(r3.getFromAddress()); if (cf3 != null) funcs.add(cf3.getEntryPoint()); thunkRefs++; }
                        } else { if (cf != null) funcs.add(cf.getEntryPoint()); iatRefs++; }
                    }
                }
                if (iat != null) iatByName.put(loc.getLabel(), iat);
                StringBuilder fs = new StringBuilder(); int n=0; for (Address fa : funcs) { if (n++>=40) { fs.append(";..."); break; } if (fs.length()>0) fs.append(';'); fs.append(fa); }
                w.println(lib + "," + q(loc.getLabel()) + "," + iat + "," + iatRefs + "," + thunk + "," + thunkRefs + "," + (iatRefs+thunkRefs) + "," + q(fs.toString()));
            }
        }
        w.close();
    }

    // ---------------- strings_xrefs.csv ----------------
    void exportStrings() throws IOException {
        PrintWriter w = open("strings_xrefs.csv");
        w.println("address,section,type,length,xref_count,referencing_functions,string");
        int total=0, referenced=0;
        for (Data d : listing.getDefinedData(true)) {
            if (!d.hasStringValue()) continue;
            total++;
            Address a = d.getAddress();
            Set<Address> funcs = new TreeSet<>(); int refs=0;
            for (Reference r : refMgr.getReferencesTo(a)) { refs++; Function cf = fm.getFunctionContaining(r.getFromAddress()); if (cf != null) { funcs.add(cf.getEntryPoint()); strRefsPerFunc.merge(cf.getEntryPoint(), 1, Integer::sum);} }
            if (refs>0) referenced++;
            StringBuilder fs = new StringBuilder(); for (Address fa : funcs) { if (fs.length()>0) fs.append(';'); fs.append(fa); }
            MemoryBlock blk = mem.getBlock(a);
            Object v = d.getValue(); String sv = v==null? d.getDefaultValueRepresentation() : v.toString();
            if (sv.length() > 300) sv = sv.substring(0,300) + "...";
            w.println(a + "," + (blk==null?"?":blk.getName()) + "," + d.getDataType().getName() + "," + d.getLength() + "," + refs + "," + q(fs.toString()) + "," + q(sv));
        }
        w.close();
        println("strings: total=" + total + " referenced=" + referenced);
    }

    // ---------------- stats.txt ----------------
    void exportStats() throws Exception {
        PrintWriter w = open("stats.txt");
        w.println("== Program ==");
        w.println("name: " + currentProgram.getName());
        w.println("format: " + currentProgram.getExecutableFormat());
        w.println("language: " + currentProgram.getLanguageID().getIdAsString());
        w.println("compilerSpec: " + currentProgram.getCompilerSpec().getCompilerSpecID().getIdAsString());
        w.println("compiler (from loader): " + currentProgram.getCompiler());
        w.println("imageBase: " + currentProgram.getImageBase());
        w.println("\n== Memory blocks ==");
        for (MemoryBlock b : mem.getBlocks()) w.println(String.format("%-10s %s-%s size=0x%X (%d) init=%b r=%b w=%b x=%b", b.getName(), b.getStart(), b.getEnd(), b.getSize(), b.getSize(), b.isInitialized(), b.isRead(), b.isWrite(), b.isExecute()));

        // functions
        int nFunc=0, nThunk=0, nUnknownCC=0, nDefaultName=0, nFid=0; long covered=0;
        Map<String,Integer> ccHist = new TreeMap<>(); Map<String,Integer> srcHist = new TreeMap<>();
        List<Function> all = new ArrayList<>();
        AddressSet textSet = textBlk==null? new AddressSet() : new AddressSet(textBlk.getStart(), textBlk.getEnd());
        for (Function f : fm.getFunctions(true)) {
            nFunc++; all.add(f);
            if (f.isThunk()) nThunk++;
            String cc = f.getCallingConventionName(); ccHist.merge(String.valueOf(cc),1,Integer::sum);
            if (cc == null || cc.equals("unknown") || cc.equals(Function.UNKNOWN_CALLING_CONVENTION_STRING)) nUnknownCC++;
            if (f.getName().startsWith("FUN_")) nDefaultName++;
            srcHist.merge(f.getSymbol().getSource().toString(),1,Integer::sum);
            for (Bookmark b : bm.getBookmarks(f.getEntryPoint())) if (b.getCategory()!=null && b.getCategory().contains("Function ID")) { nFid++; break; }
            covered += f.getBody().intersect(textSet).getNumAddresses();
        }
        long textSize = textBlk==null?0:textBlk.getSize();
        // instruction bytes in .text
        long instrBytes=0; long nInstr=0, nX87=0, nSSE=0, nCallDirect=0, nCallReg=0, nCallMemReg=0, nCallMemImm=0, nCallMemImmIAT=0, nJmpComputed=0, nJmpTable=0;
        Map<Long,Integer> vtOff = new TreeMap<>(); Map<String,Integer> mnem = new HashMap<>();
        Set<Address> fnPtrGlobals = new TreeSet<>();
        for (Instruction ins : listing.getInstructions(true)) {
            nInstr++; instrBytes += ins.getLength();
            String m = ins.getMnemonicString(); mnem.merge(m,1,Integer::sum);
            Function cf = fm.getFunctionContaining(ins.getAddress());
            if (m.startsWith("F")) { nX87++; if (cf!=null) x87PerFunc.merge(cf.getEntryPoint(),1,Integer::sum); }
            if (m.endsWith("PS") || m.endsWith("SS") || m.startsWith("MOVAP") || m.startsWith("CVT")) nSSE++;
            if (m.equals("CALL")) {
                String rep = ins.getDefaultOperandRepresentation(0);
                boolean memory = rep.contains("[");
                boolean hasReg=false, hasScalar=false, hasAddr=false; long off=0;
                for (Object o : ins.getOpObjects(0)) { if (o instanceof Register) hasReg=true; else if (o instanceof Scalar) { hasScalar=true; off=((Scalar)o).getSignedValue(); } else if (o instanceof Address) hasAddr=true; }
                if (!memory) { if (hasReg) nCallReg++; else nCallDirect++; }
                else if (hasReg) { nCallMemReg++; vtOff.merge(off,1,Integer::sum); if (cf!=null) vcallPerFunc.merge(cf.getEntryPoint(),1,Integer::sum); }
                else { nCallMemImm++; boolean iat=false; for (Reference r : refMgr.getReferencesFrom(ins.getAddress())) { Address t = r.getToAddress(); if (r.isExternalReference()) iat=true; else if (t!=null && !t.isExternalAddress()) { for (Reference r2 : refMgr.getReferencesFrom(t)) if (r2.isExternalReference()) iat=true; if (!iat && mem.getBlock(t)!=null && !mem.getBlock(t).isExecute()) fnPtrGlobals.add(t);} }
                       if (iat) nCallMemImmIAT++; }
            }
            if (m.equals("JMP") && ins.getFlowType().isComputed()) { nJmpComputed++; String rep = ins.getDefaultOperandRepresentation(0); if (rep.contains("*")) nJmpTable++; }
        }
        int nSwitchData=0; SymbolIterator si = st.getSymbolIterator("switchdataD_*", true); while (si.hasNext()) { si.next(); nSwitchData++; }
        int nSwitchLbl=0; si = st.getSymbolIterator("switchD_*", true); while (si.hasNext()) { si.next(); nSwitchLbl++; }

        w.println("\n== Functions ==");
        w.println("function_count: " + nFunc);
        w.println("thunks: " + nThunk);
        w.println("fid_named (Function ID Analyzer bookmark): " + nFid);
        w.println("default_named (FUN_*): " + nDefaultName);
        w.println("name_source_histogram: " + srcHist);
        w.println("calling_convention_histogram: " + ccHist);
        w.println("unknown_calling_convention: " + nUnknownCC);
        w.println(".text size: " + textSize + " bytes");
        w.println("bytes in function bodies (within .text): " + covered + String.format(" (%.1f%%)", textSize==0?0:100.0*covered/textSize));
        w.println("bytes covered by instructions (all blocks): " + instrBytes + String.format(" (%.1f%% of .text)", textSize==0?0:100.0*instrBytes/textSize));
        w.println("\n== Instructions ==");
        w.println("instruction_count: " + nInstr);
        w.println("x87_float_instructions (mnemonic F*): " + nX87 + String.format(" (%.2f%%)", 100.0*nX87/Math.max(1,nInstr)));
        w.println("sse_like_instructions: " + nSSE);
        w.println("call_direct: " + nCallDirect);
        w.println("call_reg (CALL reg): " + nCallReg);
        w.println("call_mem_reg (CALL [reg+off], vtable/fnptr-through-object style): " + nCallMemReg);
        w.println("call_mem_imm (CALL [imm32]): " + nCallMemImm + "  of which IAT/import: " + nCallMemImmIAT + "  non-IAT global fn-ptr slots: " + fnPtrGlobals.size());
        w.println("jmp_computed: " + nJmpComputed + "  jmp with scaled-index table operand: " + nJmpTable);
        w.println("switch tables (switchdataD_* symbols): " + nSwitchData + "  switchD_* symbols: " + nSwitchLbl);
        w.println("\n[reg+off] call offset histogram (offset -> count), top 40:");
        List<Map.Entry<Long,Integer>> vl = new ArrayList<>(vtOff.entrySet()); vl.sort((a,b)->b.getValue()-a.getValue());
        int k=0; for (Map.Entry<Long,Integer> e : vl) { if (k++>=40) break; w.println(String.format("  +0x%X : %d", e.getKey(), e.getValue())); }
        w.println("\nnon-IAT global function-pointer slots called via CALL [imm32] (first 60):");
        k=0; for (Address a : fnPtrGlobals) { if (k++>=60) break; Symbol s = st.getPrimarySymbol(a); w.println("  " + a + " " + (s==null?"":s.getName())); }
        w.println("\nmnemonic histogram top 40:");
        List<Map.Entry<String,Integer>> ml = new ArrayList<>(mnem.entrySet()); ml.sort((a,b)->b.getValue()-a.getValue());
        k=0; for (Map.Entry<String,Integer> e : ml) { if (k++>=40) break; w.println("  " + e.getKey() + " : " + e.getValue()); }

        w.println("\n== Bookmarks by type:category ==");
        Map<String,Integer> bh = new TreeMap<>();
        Iterator<Bookmark> bi = bm.getBookmarksIterator(); while (bi.hasNext()) { Bookmark b = bi.next(); bh.merge(b.getTypeString()+":"+b.getCategory(),1,Integer::sum); }
        for (Map.Entry<String,Integer> e : bh.entrySet()) w.println("  " + e.getKey() + " : " + e.getValue());
        w.println("\n== Functions named by analysis (non-default, non-thunk) ==");
        for (Function f : all) { if (!f.getName().startsWith("FUN_") && !f.isThunk()) w.println("  " + f.getEntryPoint() + " " + f.getName() + " src=" + f.getSymbol().getSource() + " size=" + f.getBody().getNumAddresses()); }

        w.println("\n== Largest 30 functions ==");
        all.sort((a,b)->Long.compare(b.getBody().getNumAddresses(), a.getBody().getNumAddresses()));
        for (int i=0;i<Math.min(30,all.size());i++) { Function f = all.get(i); w.println(String.format("  %s %-24s size=%6d cc=%s params=%d strrefs=%d vcalls=%d x87=%d", f.getEntryPoint(), f.getName(), f.getBody().getNumAddresses(), f.getCallingConventionName(), f.getParameterCount(), strRefsPerFunc.getOrDefault(f.getEntryPoint(),0), vcallPerFunc.getOrDefault(f.getEntryPoint(),0), x87PerFunc.getOrDefault(f.getEntryPoint(),0))); }

        // size histogram
        w.println("\n== Function size histogram ==");
        int[] bins = {16,32,64,128,256,512,1024,2048,4096,8192,1<<20}; int[] cnt = new int[bins.length];
        for (Function f : all) { long s = f.getBody().getNumAddresses(); for (int i=0;i<bins.length;i++) if (s<=bins[i]) { cnt[i]++; break; } }
        long lo=0; for (int i=0;i<bins.length;i++) { w.println(String.format("  %6d..%6d : %d", lo, bins[i], cnt[i])); lo=bins[i]+1; }

        // entry
        w.println("\n== Entry points ==");
        AddressIterator ei = st.getExternalEntryPointIterator();
        DecompInterface di = new DecompInterface(); di.setOptions(new DecompileOptions()); di.openProgram(currentProgram);
        List<Address> entries = new ArrayList<>(); while (ei.hasNext()) entries.add(ei.next());
        for (Address a : entries) {
            Function f = fm.getFunctionContaining(a);
            w.println("entry " + a + " -> " + (f==null?"(no function)":f.getName()+" size="+f.getBody().getNumAddresses()));
            if (f == null) continue;
            w.println("--- decompiled entry ---");
            w.println(decompile(di, f));
            // callees of entry
            w.println("--- callees of entry (with sizes) ---");
            Function winMain = null;
            for (Function c : f.getCalledFunctions(monitor)) {
                w.println("  " + c.getEntryPoint() + " " + c.getName() + " size=" + c.getBody().getNumAddresses() + " thunk=" + c.isThunk() + (c.isThunk()&&c.getThunkedFunction(true)!=null?" -> "+c.getThunkedFunction(true).getName():""));
                if (!c.isThunk() && !c.isExternal() && (winMain==null || c.getBody().getNumAddresses() > winMain.getBody().getNumAddresses())) winMain = c;
            }
            if (winMain != null) {
                w.println("--- largest non-thunk callee of entry (WinMain candidate): " + winMain.getEntryPoint() + " " + winMain.getName() + " ---");
                String c = decompile(di, winMain);
                w.println(c);
                PrintWriter dw = open("decomp/winmain_candidate_" + winMain.getEntryPoint() + ".c"); dw.println(c); dw.close();
            }
        }
        di.dispose();
        w.close();
    }

    String decompile(DecompInterface di, Function f) {
        try { DecompileResults r = di.decompileFunction(f, 120, monitor); if (r.decompileCompleted() && r.getDecompiledFunction()!=null) return r.getDecompiledFunction().getC(); return "// decompile failed: " + r.getErrorMessage(); }
        catch (Exception e) { return "// decompile exception: " + e; }
    }

    // ---------------- data_layout.txt ----------------
    void exportDataLayout() throws Exception {
        PrintWriter w = open("data_layout.txt");
        AddressSet dataSet = new AddressSet();
        for (MemoryBlock b : mem.getBlocks()) {
            if (b.isExecute()) continue;
            AddressSet bs = new AddressSet(b.getStart(), b.getEnd());
            dataSet.add(bs);
            long defined=0; int nItems=0; Map<String,long[]> byType = new TreeMap<>();
            List<Data> items = new ArrayList<>();
            for (Data d : listing.getDefinedData(bs, true)) { defined += d.getLength(); nItems++; String t = d.getDataType().getName(); long[] v = byType.computeIfAbsent(t, x->new long[2]); v[0]++; v[1]+=d.getLength(); items.add(d); }
            long instrB=0; for (Instruction ins : listing.getInstructions(bs, true)) instrB += ins.getLength();
            w.println(String.format("== Block %s %s-%s size=%d init=%b ==", b.getName(), b.getStart(), b.getEnd(), b.getSize(), b.isInitialized()));
            w.println(String.format("  defined data: %d items, %d bytes (%.1f%%); instructions: %d bytes; undefined: %d bytes (%.1f%%)", nItems, defined, 100.0*defined/b.getSize(), instrB, b.getSize()-defined-instrB, 100.0*(b.getSize()-defined-instrB)/b.getSize()));
            w.println("  by type (count, bytes):");
            List<Map.Entry<String,long[]>> tl = new ArrayList<>(byType.entrySet()); tl.sort((x,y)->Long.compare(y.getValue()[1], x.getValue()[1]));
            int k=0; for (Map.Entry<String,long[]> e : tl) { if (k++>=25) break; w.println(String.format("    %-28s %6d %8d", e.getKey(), e.getValue()[0], e.getValue()[1])); }
            items.sort((x,y)->y.getLength()-x.getLength());
            w.println("  largest 25 defined items:");
            for (int i=0;i<Math.min(25,items.size());i++) { Data d = items.get(i); Symbol s = st.getPrimarySymbol(d.getAddress()); w.println(String.format("    %s len=%6d type=%-20s label=%s refs=%d", d.getAddress(), d.getLength(), d.getDataType().getName(), s==null?"":s.getName(), refMgr.getReferenceCountTo(d.getAddress()))); }

            if (!b.isInitialized()) { w.println(); continue; }
            // raw pointer scan: runs of dwords pointing at function starts (vtable/function-table candidates) and at data
            w.println("  raw dword scan (4-byte aligned) for pointer runs:");
            List<long[]> fnRuns = new ArrayList<>(); List<long[]> dataRuns = new ArrayList<>();
            long runStart=-1; int runLen=0; long drunStart=-1; int drunLen=0; long nFnPtr=0, nDataPtr=0;
            Address cur = b.getStart(); long end = b.getEnd().getOffset();
            for (long off = cur.getOffset(); off + 4 <= end + 1; off += 4) {
                Address a = cur.getNewAddress(off);
                int v; try { v = mem.getInt(a); } catch (Exception e) { break; }
                Address t = null; try { t = cur.getNewAddress(v & 0xffffffffL); } catch (Exception e) {}
                boolean isFn = t!=null && textBlk!=null && textBlk.contains(t) && fm.getFunctionAt(t)!=null;
                boolean isData = t!=null && !isFn && mem.getBlock(t)!=null && !mem.getBlock(t).isExecute() && v!=0;
                if (isFn) { nFnPtr++; if (runStart<0) { runStart=off; runLen=0; } runLen++; } else { if (runStart>=0 && runLen>=2) fnRuns.add(new long[]{runStart,runLen}); runStart=-1; runLen=0; }
                if (isData) { nDataPtr++; if (drunStart<0) { drunStart=off; drunLen=0; } drunLen++; } else { if (drunStart>=0 && drunLen>=4) dataRuns.add(new long[]{drunStart,drunLen}); drunStart=-1; drunLen=0; }
            }
            if (runStart>=0 && runLen>=2) fnRuns.add(new long[]{runStart,runLen});
            if (drunStart>=0 && drunLen>=4) dataRuns.add(new long[]{drunStart,drunLen});
            w.println("    dwords pointing at function starts: " + nFnPtr + "  runs(>=2): " + fnRuns.size() + "  dwords pointing into data: " + nDataPtr + "  runs(>=4): " + dataRuns.size());
            Map<Integer,Integer> rl = new TreeMap<>(); for (long[] r : fnRuns) rl.merge((int)r[1],1,Integer::sum);
            w.println("    fn-pointer run length histogram: " + rl);
            fnRuns.sort((x,y)->Long.compare(y[1],x[1]));
            w.println("    top 40 function-pointer runs (vtable / dispatch table candidates):");
            for (int i=0;i<Math.min(40,fnRuns.size());i++) { long[] r = fnRuns.get(i); Address a = cur.getNewAddress(r[0]); Symbol s = st.getPrimarySymbol(a); StringBuilder sb = new StringBuilder();
                for (int j=0;j<Math.min(6,r[1]);j++) { int v = mem.getInt(a.add(j*4)); Function f = fm.getFunctionAt(cur.getNewAddress(v&0xffffffffL)); sb.append(f==null?"?":f.getName()).append(' '); }
                w.println(String.format("      %s len=%3d refs=%d label=%s : %s", a, r[1], refMgr.getReferenceCountTo(a), s==null?"":s.getName(), sb)); }
            dataRuns.sort((x,y)->Long.compare(y[1],x[1]));
            w.println("    top 25 data-pointer runs (object/string table candidates):");
            for (int i=0;i<Math.min(25,dataRuns.size());i++) { long[] r = dataRuns.get(i); Address a = cur.getNewAddress(r[0]); Symbol s = st.getPrimarySymbol(a);
                int v0 = mem.getInt(a); Address t0 = cur.getNewAddress(v0&0xffffffffL); Data d0 = listing.getDataAt(t0); String sample = d0!=null && d0.hasStringValue()? String.valueOf(d0.getValue()) : (d0!=null? d0.getDataType().getName():"undefined");
                if (sample.length()>60) sample = sample.substring(0,60);
                w.println(String.format("      %s len=%3d refs=%d label=%s first->%s (%s)", a, r[1], refMgr.getReferenceCountTo(a), s==null?"":s.getName(), t0, q(sample))); }
            w.println();
        }
        // hot globals
        w.println("== Top 60 most-referenced addresses in non-executable blocks (hot globals) ==");
        List<Object[]> hot = new ArrayList<>();
        AddressIterator ai = refMgr.getReferenceDestinationIterator(dataSet, true);
        while (ai.hasNext()) { Address a = ai.next(); int n=0, rd=0, wr=0; Set<Address> fs = new HashSet<>();
            for (Reference r : refMgr.getReferencesTo(a)) { n++; if (r.getReferenceType().isWrite()) wr++; if (r.getReferenceType().isRead()) rd++; Function cf = fm.getFunctionContaining(r.getFromAddress()); if (cf!=null) fs.add(cf.getEntryPoint()); }
            hot.add(new Object[]{a,n,rd,wr,fs.size()}); }
        hot.sort((x,y)->(Integer)y[1]-(Integer)x[1]);
        w.println(String.format("  %-10s %6s %5s %5s %6s %-10s %-20s %s", "addr", "refs", "read", "write", "funcs", "block", "type", "label"));
        for (int i=0;i<Math.min(60,hot.size());i++) { Object[] h = hot.get(i); Address a=(Address)h[0]; Data d = listing.getDataAt(a); Symbol s = st.getPrimarySymbol(a); MemoryBlock b = mem.getBlock(a);
            String extra = ""; if (d!=null && d.hasStringValue()) { extra = q(String.valueOf(d.getValue())); if (extra.length()>50) extra = extra.substring(0,50)+"..."; }
            w.println(String.format("  %-10s %6d %5d %5d %6d %-10s %-20s %s %s", a, h[1], h[2], h[3], h[4], b==null?"?":b.getName(), d==null?"undefined":d.getDataType().getName(), s==null?"":s.getName(), extra)); }
        w.println("  total distinct referenced data addresses: " + hot.size());
        // full hot list to a csv as well
        PrintWriter hw = open("hot_globals.csv"); hw.println("address,refs,reads,writes,funcs,block,type,label");
        for (Object[] h : hot) { Address a=(Address)h[0]; Data d = listing.getDataAt(a); Symbol s = st.getPrimarySymbol(a); MemoryBlock b = mem.getBlock(a);
            hw.println(a + "," + h[1] + "," + h[2] + "," + h[3] + "," + h[4] + "," + (b==null?"?":b.getName()) + "," + (d==null?"undefined":d.getDataType().getName()) + "," + q(s==null?"":s.getName())); }
        hw.close();
        w.close();
    }

    // ---------------- decompilation samples ----------------
    void exportDecomp() throws Exception {
        DecompInterface di = new DecompInterface(); di.setOptions(new DecompileOptions()); di.openProgram(currentProgram);
        PrintWriter idx = open("decomp/INDEX.txt");
        List<Function> mid = new ArrayList<>();
        for (Function f : fm.getFunctions(true)) { long s = f.getBody().getNumAddresses(); if (s>=250 && s<=3500 && !f.isThunk()) mid.add(f); }
        Set<Address> chosen = new LinkedHashSet<>();
        // (1) top 3 by string refs
        mid.sort((a,b)->strRefsPerFunc.getOrDefault(b.getEntryPoint(),0)-strRefsPerFunc.getOrDefault(a.getEntryPoint(),0));
        for (int i=0;i<Math.min(3,mid.size());i++) { chosen.add(mid.get(i).getEntryPoint()); idx.println("string-heavy: " + mid.get(i).getEntryPoint() + " strrefs=" + strRefsPerFunc.getOrDefault(mid.get(i).getEntryPoint(),0)); }
        // (2) callers of DirectX creation imports and a few others
        for (String imp : new String[]{"DirectDrawCreate","DirectDrawEnumerateA","DirectSoundCreate","DirectInputCreateA","timeGetTime","CreateWindowExA","joyGetPosEx"}) {
            Address iat = iatByName.get(imp); if (iat==null) { idx.println("import " + imp + " not found in IAT map"); continue; }
            List<Function> callers = new ArrayList<>();
            for (Reference r : refMgr.getReferencesTo(iat)) { Function cf = fm.getFunctionContaining(r.getFromAddress()); if (cf!=null && !callers.contains(cf)) callers.add(cf); }
            callers.sort((a,b)->Long.compare(b.getBody().getNumAddresses(), a.getBody().getNumAddresses()));
            StringBuilder sb = new StringBuilder(); for (Function c : callers) sb.append(c.getEntryPoint()).append('(').append(c.getBody().getNumAddresses()).append(") ");
            idx.println("callers of " + imp + ": " + sb);
            int added=0; for (Function c : callers) { long s=c.getBody().getNumAddresses(); if (s>=250 && s<=3500 && chosen.add(c.getEntryPoint())) { idx.println("  chosen " + c.getEntryPoint()); if (++added>=1) break; } }
        }
        // (3) most vtable-style calls
        mid.sort((a,b)->vcallPerFunc.getOrDefault(b.getEntryPoint(),0)-vcallPerFunc.getOrDefault(a.getEntryPoint(),0));
        for (int i=0;i<Math.min(2,mid.size());i++) { chosen.add(mid.get(i).getEntryPoint()); idx.println("vcall-heavy: " + mid.get(i).getEntryPoint() + " vcalls=" + vcallPerFunc.getOrDefault(mid.get(i).getEntryPoint(),0)); }
        // (4) most x87
        mid.sort((a,b)->x87PerFunc.getOrDefault(b.getEntryPoint(),0)-x87PerFunc.getOrDefault(a.getEntryPoint(),0));
        for (int i=0;i<Math.min(2,mid.size());i++) { chosen.add(mid.get(i).getEntryPoint()); idx.println("x87-heavy: " + mid.get(i).getEntryPoint() + " x87=" + x87PerFunc.getOrDefault(mid.get(i).getEntryPoint(),0)); }
        idx.close();
        for (Address a : chosen) {
            Function f = fm.getFunctionAt(a); if (f==null) continue;
            PrintWriter dw = open("decomp/" + a + "_" + f.getName() + ".c");
            dw.println("// " + f.getEntryPoint() + " " + f.getName() + " size=" + f.getBody().getNumAddresses() + " cc=" + f.getCallingConventionName() + " params=" + f.getParameterCount() + " strrefs=" + strRefsPerFunc.getOrDefault(a,0) + " vcalls=" + vcallPerFunc.getOrDefault(a,0) + " x87=" + x87PerFunc.getOrDefault(a,0));
            dw.println(decompile(di, f)); dw.close();
        }
        di.dispose();
    }
}
