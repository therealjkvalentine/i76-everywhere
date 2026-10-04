# symbols

Machine-readable map tables (method doc section 6):
functions.tsv (addr size name status conv conv_evidence hookable duplicate_of tu subsystem evidence_ids),
globals.tsv (addr class width type name status readers writers bound_evidence evidence_ids),
heaptypes.tsv (source key(heap|pool,size,retaddr) struct owner lifetime instances),
strings.tsv imports.tsv tables.tsv regions.tsv modules.tsv (Task 3, `tools/gen_tables.py`).
Every address carries a class tag (gate A); every count its method (gate C); one writer (the merge script).
