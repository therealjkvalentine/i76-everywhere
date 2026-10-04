import ghidra.app.script.GhidraScript;
public class EnableParamID extends GhidraScript {
    @Override public void run() throws Exception {
        setAnalysisOption(currentProgram, "Decompiler Parameter ID", "true");
        println("EnableParamID: Decompiler Parameter ID enabled");
    }
}
