import ghidra.app.script.GhidraScript;
public class EnableAggressive extends GhidraScript {
    @Override public void run() throws Exception {
        setAnalysisOption(currentProgram, "Decompiler Parameter ID", "true");
        setAnalysisOption(currentProgram, "Aggressive Instruction Finder", "true");
        println("EnableAggressive: Aggressive Instruction Finder + Decompiler Parameter ID enabled");
    }
}
