// RunVT_T5b.java - Task 5b (t5b-sibling-vt): headless Version Tracking from a SOURCE program (i76_ref.exe)
// to the current (DESTINATION) program, correlators in a stated order, NO implied matches, no markup applied.
// Usage: analyzeHeadless <proj> i76map -process <dest.exe> -noanalysis
//          -postScript RunVT_T5b.java <sessionName> </path/in/project/of/source.exe> <out.json> [minScore] [minConf]
// Order: ExactData, ExactBytes, ExactInstructions, ExactMnemonics (accept every 1:1 match, score 1.0),
//        then DataReference, FunctionReference, CombinedFunctionAndDataReference, SimilarData
//        (accept only similarity >= minScore [0.95] and confidence >= minConf [10.0], both also passed to the
//        correlator as its SIMILARITY_THRESHOLD / CONFIDENCE_THRESHOLD options; a match whose source or destination
//        already has an accepted association is left unaccepted (related-association rule, as Ghidra AutoVT does)).
// The Exact Symbol Name correlator is NOT run: the destination has only default names and the source carries the
// map names, so a symbol match would only re-import our own names. Implied matches are never created.
//@category Version Tracking
import java.io.*;
import java.util.*;
import ghidra.app.script.GhidraScript;
import ghidra.feature.vt.api.correlator.program.*;
import ghidra.feature.vt.api.db.VTSessionDB;
import ghidra.feature.vt.api.main.*;
import ghidra.feature.vt.api.util.VTOptions;
import ghidra.framework.model.*;
import ghidra.program.model.listing.*;
import ghidra.program.model.symbol.*;

public class RunVT_T5b extends GhidraScript {
    PrintWriter w;
    boolean first = true;

    String q(String s) { return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\""; }

    @Override public void run() throws Exception {
        String[] a = getScriptArgs();
        if (a.length < 3) { println("args: sessionName sourceProjectPath outJson [minScore] [minConf]"); return; }
        String sessionName = a[0], srcPath = a[1], outPath = a[2];
        double minScore = a.length > 3 ? Double.parseDouble(a[3]) : 0.95;
        double minConf  = a.length > 4 ? Double.parseDouble(a[4]) : 10.0;

        Program dest = currentProgram;
        ProjectData pd = state.getProject().getProjectData();
        if (!srcPath.startsWith("/")) srcPath = "/" + new File(srcPath).getName(); // MSYS shells mangle "/x.exe" into a Windows path
        DomainFile srcDF = pd.getFile(srcPath);
        if (srcDF == null) { println("source not found: " + srcPath); return; }
        Program src = (Program) srcDF.getDomainObject(this, false, false, monitor);
        DomainFolder root = pd.getRootFolder();
        DomainFile old = root.getFile(sessionName);
        if (old != null) { println("deleting existing session " + sessionName); old.delete(); }

        end(true); // release the script transaction on dest before VT takes locks (as AutoVersionTrackingScript does)
        VTSession session = null;
        try {
            session = new VTSessionDB(sessionName, src, dest, this);
            root.createFile(sessionName, session, monitor);
            w = new PrintWriter(new BufferedWriter(new OutputStreamWriter(new FileOutputStream(outPath), "UTF-8")));
            w.println("{");
            w.println(" \"session\": " + q(sessionName) + ",");
            w.println(" \"source\": " + q(src.getName()) + ", \"source_md5\": " + q(String.valueOf(src.getExecutableMD5())) + ",");
            w.println(" \"destination\": " + q(dest.getName()) + ", \"destination_md5\": " + q(String.valueOf(dest.getExecutableMD5())) + ",");
            w.println(" \"thresholds\": {\"ref_min_similarity\": " + minScore + ", \"ref_min_confidence\": " + minConf + ", \"function_min_len\": 10, \"data_min_len\": 5},");
            w.println(" \"implied_matches\": false, \"markup_applied\": false, \"symbol_correlator\": false,");
            w.println(" \"correlators\": [");

            runOne(session, src, dest, new ExactDataMatchProgramCorrelatorFactory(), false, 0, 0);
            runOne(session, src, dest, new ExactMatchBytesProgramCorrelatorFactory(), false, 0, 0);
            runOne(session, src, dest, new ExactMatchInstructionsProgramCorrelatorFactory(), false, 0, 0);
            runOne(session, src, dest, new ExactMatchMnemonicsProgramCorrelatorFactory(), false, 0, 0);
            runOne(session, src, dest, new DataReferenceProgramCorrelatorFactory(), true, minScore, minConf);
            runOne(session, src, dest, new FunctionReferenceProgramCorrelatorFactory(), true, minScore, minConf);
            runOne(session, src, dest, new CombinedFunctionAndDataReferenceProgramCorrelatorFactory(), true, minScore, minConf);
            runOne(session, src, dest, new SimilarDataProgramCorrelatorFactory(), true, minScore, minConf);

            w.println(" ],");
            int accF = 0, accD = 0;
            VTAssociationManager am = session.getAssociationManager();
            for (VTAssociation as : am.getAssociations()) {
                if (as.getStatus() == VTAssociationStatus.ACCEPTED) { if (as.getType() == VTAssociationType.FUNCTION) accF++; else accD++; }
            }
            int nSrcF = src.getFunctionManager().getFunctionCount(), nDstF = dest.getFunctionManager().getFunctionCount();
            w.println(" \"accepted_function_associations\": " + accF + ", \"accepted_data_associations\": " + accD + ",");
            w.println(" \"source_functions\": " + nSrcF + ", \"destination_functions\": " + nDstF);
            w.println("}");
            w.close();
            session.save();
            println("RunVT_T5b: accepted functions=" + accF + " data=" + accD + " (src fns " + nSrcF + ", dst fns " + nDstF + ") -> " + outPath);
        } finally {
            if (session != null) session.release(this);
            src.release(this);
        }
    }

    void runOne(VTSession session, Program src, Program dest, VTProgramCorrelatorFactory f, boolean thresholded,
                double minScore, double minConf) throws Exception {
        VTOptions opt = f.createDefaultOptions();
        if (thresholded) {
            opt.setDouble(VTAbstractReferenceProgramCorrelatorFactory.SIMILARITY_THRESHOLD, minScore);
            opt.setDouble(VTAbstractReferenceProgramCorrelatorFactory.CONFIDENCE_THRESHOLD, minConf);
        }
        long t0 = System.currentTimeMillis();
        println("correlator: " + f.getName());
        VTProgramCorrelator c = f.createCorrelator(src, src.getMemory().getLoadedAndInitializedAddressSet(),
            dest, dest.getMemory().getLoadedAndInitializedAddressSet(), opt);
        int total = 0, accepted = 0, skippedRelated = 0, belowThr = 0, notApplicable = 0;
        List<String> rows = new ArrayList<>();
        VTAssociationManager am = session.getAssociationManager();
        int tx = session.startTransaction("t5b " + f.getName()); // correlate() and setAccepted() both need a session transaction
        VTMatchSet ms;
        try {
            ms = c.correlate(session, monitor);
            for (VTMatch m : ms.getMatches()) {
                total++;
                VTAssociation as = m.getAssociation();
                double sim = m.getSimilarityScore().getScore(), conf = m.getConfidenceScore().getScore();
                String verdict;
                if (thresholded && (sim < minScore || conf < minConf)) { verdict = "below-threshold"; belowThr++; }
                else if (!as.getStatus().canApply()) { verdict = "status-" + as.getStatus().name().toLowerCase(); notApplicable++; }
                else {
                    boolean rel = false;
                    for (VTAssociation r : am.getRelatedAssociationsBySourceAndDestinationAddress(as.getSourceAddress(), as.getDestinationAddress())) {
                        if (r != as && r.getStatus() == VTAssociationStatus.ACCEPTED) { rel = true; break; }
                    }
                    if (rel) { verdict = "related-accepted"; skippedRelated++; }
                    else { try { as.setAccepted(); verdict = "accepted"; accepted++; } catch (Exception e) { verdict = "accept-failed"; notApplicable++; } }
                }
                Symbol ss = src.getSymbolTable().getPrimarySymbol(as.getSourceAddress());
                Symbol ds = dest.getSymbolTable().getPrimarySymbol(as.getDestinationAddress());
                rows.add("   {\"src\": " + q("0x" + as.getSourceAddress()) + ", \"dst\": " + q("0x" + as.getDestinationAddress()) +
                    ", \"type\": " + q(as.getType().name()) + ", \"src_len\": " + m.getSourceLength() + ", \"dst_len\": " + m.getDestinationLength() +
                    ", \"similarity\": " + sim + ", \"confidence\": " + conf + ", \"verdict\": " + q(verdict) +
                    ", \"src_name\": " + q(ss == null ? "" : ss.getName()) + ", \"dst_name\": " + q(ds == null ? "" : ds.getName()) + "}");
            }
        } finally { session.endTransaction(tx, true); }
        long dt = System.currentTimeMillis() - t0;
        if (!first) w.println("  ,");
        first = false;
        w.println("  {\"correlator\": " + q(f.getName()) + ", \"class\": " + q(f.getClass().getName()) + ", \"thresholded\": " + thresholded +
            ", \"matches\": " + total + ", \"accepted\": " + accepted + ", \"below_threshold\": " + belowThr + ", \"related_accepted_skipped\": " + skippedRelated +
            ", \"not_applicable\": " + notApplicable + ", \"seconds\": " + (dt / 1000.0) + ",");
        w.println("   \"rows\": [");
        for (int i = 0; i < rows.size(); i++) w.println(rows.get(i) + (i + 1 < rows.size() ? "," : ""));
        w.println("   ]}");
        w.flush();
        println(String.format("  %s: matches=%d accepted=%d below=%d related=%d n/a=%d (%.1fs)", f.getName(), total, accepted, belowThr, skippedRelated, notApplicable, dt / 1000.0));
    }
}
