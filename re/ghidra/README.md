# ghidra

`proj\` the working project (single writer; ignored by git; rebuilt from `scripts\` twice from clean,
structural diff empty, G7). `scripts\` ExportBaseline, EnableParamID, CreateFuncsFromDataPtrs, ApplyMap,
DumpAll (Task 2 ports them from the archive). `export\` 2,165 .c/.pcode + callgraph.json, regenerated
after every merge. `export-frozen\` the Phase 0 export the truth set is sealed against; never
regenerated. The archived projects under `..\recon-2026-09-04\**\proj\` are read-only evidence.

Task 5b added two sibling programs to the project (`nitro.exe` md5 28b8ae276e88f4ffb13f17df159f09dc,
`i76_cd1997.exe` md5 6cc509adf0a980dd233104bf916db377; the staged copies `ghidra\*.exe` stay out of git,
`*.exe` is ignored) and the Version Tracking sessions `vt-nitro` / `vt-cd1997`; their pass-4 exports are
`export-nitro\` and `export-cd1997\` (`status\tasks\t5b-sibling-vt.md`).
