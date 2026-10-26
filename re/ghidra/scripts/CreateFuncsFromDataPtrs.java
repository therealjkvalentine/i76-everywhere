// Creates functions at 16-byte-aligned .text addresses that are referenced by raw dword pointers in .data/.rdata
// but are not yet inside any function. Prints a summary line.
// p4-ghidra-fixes: second source, the non-import function-pointer SLOTS. A slot that is 0 in the file and is
// filled at run time by `mov dword ptr [slot], imm32` (C7 05 <slot> <imm32>) hides its targets from the dword
// scan (fold-in C20: 0x406ab0, the cockpit-look callback, is reached only through slot 0x4c2720 `data-init`).
// Method: byte scan of .text for C7 05 <slot LE>; the imm32 sits at site+6 (capstone-verified offline); the target
// must be in .text, 16-byte aligned and not already inside a function. One funnel line per slot.
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.mem.*;
import java.util.*;
public class CreateFuncsFromDataPtrs extends GhidraScript {
    // non-import function-pointer slots written by code (class data-init unless noted)
    static final long[] SLOTS = { 0x4c2720L };
    @Override public void run() throws Exception {
        Memory mem = currentProgram.getMemory(); Listing l = currentProgram.getListing(); FunctionManager fm = currentProgram.getFunctionManager();
        MemoryBlock text = mem.getBlock(".text");
        int created=0, skipped=0, unaligned=0; Set<Address> cands = new TreeSet<>();
        for (MemoryBlock b : mem.getBlocks()) {
            if (b.isExecute() || !b.isInitialized()) continue;
            if (!b.getName().equals(".data") && !b.getName().equals(".rdata")) continue;
            long end = b.getEnd().getOffset();
            for (long off = b.getStart().getOffset(); off + 4 <= end + 1; off += 4) {
                Address a = b.getStart().getNewAddress(off);
                int v; try { v = mem.getInt(a); } catch (Exception e) { break; }
                Address t = a.getNewAddress(v & 0xffffffffL);
                if (!text.contains(t)) continue;
                if (fm.getFunctionContaining(t) != null) continue;
                if ((t.getOffset() & 0xF) != 0) { unaligned++; continue; }
                cands.add(t);
            }
        }
        for (Address t : cands) {
            if (fm.getFunctionContaining(t) != null) continue;
            if (l.getInstructionAt(t) == null) { if (l.getDefinedDataAt(t) != null) { skipped++; continue; } disassemble(t); }
            if (l.getInstructionAt(t) == null) { skipped++; continue; }
            Function f = createFunction(t, null);
            if (f != null) created++; else skipped++;
        }
        println("CreateFuncsFromDataPtrs: candidates=" + cands.size() + " created=" + created + " skipped=" + skipped + " unaligned_rejected=" + unaligned);

        // ---- slot pass: `mov dword ptr [slot], imm32` stores in .text ----
        byte[] buf = new byte[(int) text.getSize()];
        mem.getBytes(text.getStart(), buf);
        long tbase = text.getStart().getOffset();
        for (long slot : SLOTS) {
            int sites = 0, sUnaligned = 0, sInFunc = 0, sCreated = 0, sSkipped = 0;
            Set<Address> targets = new TreeSet<>();
            List<String> siteList = new ArrayList<>();
            for (int i = 0; i + 10 <= buf.length; i++) {
                if ((buf[i] & 0xff) != 0xC7 || (buf[i + 1] & 0xff) != 0x05) continue;
                long d = (buf[i + 2] & 0xffL) | ((buf[i + 3] & 0xffL) << 8) | ((buf[i + 4] & 0xffL) << 16) | ((buf[i + 5] & 0xffL) << 24);
                if (d != slot) continue;
                long v = (buf[i + 6] & 0xffL) | ((buf[i + 7] & 0xffL) << 8) | ((buf[i + 8] & 0xffL) << 16) | ((buf[i + 9] & 0xffL) << 24);
                sites++;
                Address t = text.getStart().getNewAddress(v);
                siteList.add(String.format("%x->%x", tbase + i, v));
                if (!text.contains(t)) continue;
                if ((v & 0xF) != 0) { sUnaligned++; continue; }
                targets.add(t);
            }
            for (Address t : targets) {
                if (fm.getFunctionContaining(t) != null) { sInFunc++; continue; }
                if (l.getInstructionAt(t) == null) { if (l.getDefinedDataAt(t) != null) { sSkipped++; continue; } disassemble(t); }
                if (l.getInstructionAt(t) == null) { sSkipped++; continue; }
                Function f = createFunction(t, null);
                if (f != null) { sCreated++; println(String.format("CreateFuncsFromDataPtrs: slot %x created %s at %s size=%d", slot, f.getName(), t, f.getBody().getNumAddresses())); }
                else sSkipped++;
            }
            println(String.format("CreateFuncsFromDataPtrs: slot %x sites=%d distinct_targets=%d unaligned_rejected=%d already_in_function=%d created=%d skipped=%d sites=[%s]",
                    slot, sites, targets.size(), sUnaligned, sInFunc, sCreated, sSkipped, String.join(",", siteList)));
        }
    }
}
