# Verification gate report (2026-10-03d)

Written by `verify/gate.py` (VERIFICATION-PROGRAM.md 2.8 / section 6). The game was not run; every number comes from result files under `verify/`. Nothing is demoted; FAILs are listed in `verify/disputes.tsv` for review. The batch `status/tasks/verify-2026-10-03d.json` is written here and applied by `tools/merge.py` (not by this script).

## Inputs

- phase-1 census: 70 runs, 1999 functions seen (`verify/runs/phase1-all-summary.json`); cadence claims: 150 with an enum of 388 canonical results; census-grade results: 136 (98 script, 38 model)
- oracle: `verify/oracles/REPORT.md`, 20 recorded drive runs; rows with verdict PASS in 'Claims these oracles now support'
- blind: 950 judged functions (final = Sonnet re-judge where present): [('compatible', 558), ('different', 263), ('same', 129)]; second reader (`reader2`): 283 judged: [('compatible', 172), ('same', 62), ('different', 49)]

## Functions by status

| status | before | after |
|---|---|---|
| anchored | 143 | 143 |
| supported | 583 | 670 |
| proposed | 1410 | 1323 |
| synthetic | 74 | 74 |
| library | 7 | 7 |

**87 functions qualify for `supported`** (census PASS and oracle or blind PASS; or two independent blind PASS, any prefix, since pass 4): [('census+blind', 87)]; 0 globals (oracle PASS).

Batch rows carry conv `auto` / `auto:paramid` (gate K); 1 promoted rows had another conv in functions.tsv, which the merge will reset: image_RegisterMapSet 0x44aa20 (__cdecl; call-cleanup@0x449b34:add esp,0x4)

## Census outcomes (functions with a cadence claim)

| verdict | script | model |
|---|---|---|
| PASS | 55 | 7 |
| FAIL | 9 | 22 |
| INCONCLUSIVE | 34 | 9 |

Model column: Haiku first; its 29 FAILs were re-graded by Sonnet (`--suffix sonnet`), whose verdict is final (Haiku -> Sonnet: [(('FAIL', 'FAIL'), 22), (('FAIL', 'INCONCLUSIVE'), 5), (('FAIL', 'PASS'), 2)]).

Functions without a claim (no cadence vocabulary, or claim `unknown`) take the census class as their cadence record; 1039 of them have a definite class.

## Per prefix

| prefix | rows | proposed | supported | anchored | census_PASS | census_FAIL | inconclusive_early_attach | never | blind_judged | blind_PASS | blind_different | blind2_judged | oracle_PASS | promoted | census_only | two_readers | two_readers_different | one_reader_of_two | utility_one_reader |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| renderer | 415 | 306 | 109 | 0 | 205 | 4 | 3 | 154 | 228 | 145 | 83 | 62 | 0 | 16 | 119 | 0 | 9 | 12 | 0 |
| ai | 211 | 174 | 37 | 0 | 140 | 5 | 0 | 51 | 60 | 46 | 14 | 9 | 0 | 3 | 104 | 0 | 1 | 1 | 0 |
| entity | 160 | 123 | 37 | 0 | 91 | 3 | 3 | 48 | 72 | 50 | 22 | 21 | 0 | 8 | 59 | 0 | 2 | 0 | 0 |
| object | 134 | 74 | 60 | 0 | 97 | 1 | 3 | 24 | 89 | 73 | 16 | 22 | 0 | 10 | 43 | 0 | 0 | 0 | 0 |
| net | 130 | 127 | 3 | 0 | 0 | 2 | 1 | 102 | 13 | 11 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| bwd2 | 107 | 25 | 12 | 70 | 62 | 0 | 0 | 43 | 20 | 16 | 4 | 5 | 0 | 8 | 10 | 0 | 0 | 0 | 0 |
| weapon | 102 | 72 | 30 | 0 | 55 | 6 | 3 | 38 | 67 | 42 | 25 | 14 | 0 | 6 | 24 | 0 | 3 | 3 | 0 |
| shell | 99 | 63 | 9 | 27 | 7 | 1 | 0 | 75 | 23 | 11 | 12 | 15 | 0 | 0 | 1 | 0 | 4 | 1 | 0 |
| physics | 94 | 59 | 35 | 0 | 68 | 1 | 2 | 14 | 52 | 40 | 12 | 12 | 2 | 1 | 35 | 0 | 2 | 1 | 0 |
| sound | 86 | 55 | 31 | 0 | 57 | 0 | 1 | 17 | 52 | 36 | 16 | 5 | 0 | 7 | 22 | 0 | 1 | 0 | 0 |
| fsm | 83 | 59 | 23 | 1 | 35 | 0 | 1 | 42 | 13 | 12 | 1 | 4 | 0 | 5 | 23 | 0 | 0 | 0 | 0 |
| synthetic | 74 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| image | 60 | 40 | 20 | 0 | 33 | 2 | 4 | 21 | 41 | 29 | 12 | 12 | 0 | 8 | 16 | 0 | 2 | 0 | 0 |
| math | 59 | 22 | 37 | 0 | 42 | 1 | 1 | 15 | 44 | 42 | 2 | 38 | 0 | 0 | 1 | 0 | 1 | 0 | 9 |
| camera | 52 | 42 | 10 | 0 | 37 | 5 | 1 | 7 | 28 | 10 | 18 | 7 | 0 | 0 | 27 | 0 | 3 | 1 | 0 |
| input | 49 | 33 | 16 | 0 | 33 | 0 | 1 | 11 | 30 | 24 | 6 | 4 | 0 | 12 | 10 | 0 | 0 | 1 | 0 |
| font | 46 | 36 | 10 | 0 | 6 | 0 | 0 | 27 | 22 | 17 | 5 | 12 | 0 | 1 | 4 | 0 | 0 | 3 | 0 |
| vfs | 42 | 22 | 20 | 0 | 31 | 0 | 0 | 8 | 30 | 30 | 0 | 19 | 0 | 0 | 0 | 0 | 0 | 0 | 14 |
| world | 40 | 24 | 16 | 0 | 27 | 0 | 1 | 6 | 21 | 15 | 6 | 8 | 0 | 0 | 18 | 0 | 1 | 0 | 0 |
| heap | 31 | 3 | 11 | 17 | 20 | 0 | 0 | 6 | 6 | 6 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| startup | 21 | 11 | 10 | 0 | 5 | 0 | 0 | 11 | 10 | 10 | 0 | 4 | 0 | 2 | 1 | 0 | 0 | 0 | 0 |
| import-thunk | 20 | 0 | 0 | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| simclock | 15 | 5 | 10 | 0 | 5 | 0 | 0 | 2 | 4 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| light | 12 | 10 | 2 | 0 | 11 | 0 | 0 | 1 | 7 | 2 | 5 | 0 | 0 | 0 | 9 | 0 | 0 | 0 | 0 |
| zfs | 12 | 2 | 10 | 0 | 10 | 0 | 0 | 2 | 3 | 3 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| ffb | 11 | 5 | 6 | 0 | 6 | 0 | 1 | 4 | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 0 | 0 |
| crt | 9 | 1 | 4 | 2 | 7 | 0 | 0 | 0 | 5 | 4 | 1 | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| match | 8 | 8 | 0 | 0 | 1 | 0 | 0 | 6 | 2 | 2 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| profiler | 7 | 0 | 7 | 0 | 3 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| salvage | 6 | 6 | 0 | 0 | 0 | 0 | 1 | 6 | 5 | 4 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| lzo | 5 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| (other) | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| player | 3 | 1 | 2 | 0 | 0 | 0 | 0 | 1 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| pool | 3 | 0 | 3 | 0 | 1 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| calc | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| roadwar | 1 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| debug | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| d3d_videolog | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| Geom | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| new | 1 | 0 | 0 | 1 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| image-pcx | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| smacker | 1 | 0 | 1 | 0 | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **all** | **2217** | **1410** | **583** | **143** | **1101** | **31** | **27** | **750** | **950** | **687** | **263** | **283** | **2** | **87** | **532** | **0** | **29** | **23** | **23** |

`census_only` = census PASS but no oracle/blind evidence yet (the blind sample covered 300 of 1,882 proposed rows); `never` = 0 calls in every phase-1 scenario; `inconclusive_early_attach` = init_only claimed, 0 calls because the hooks attach after the player entity exists (early-attach census pending).

## Census FAIL (31) and blind `different` from both readers (29) -> `verify/disputes.tsv`

Script rule: per_frame claimed and 0 calls in every mission scenario (or never claimed and calls seen). Model rule (census-grade prompt): the observation contradicts the claim. The reviewer notes at the end of this file read each one.

| addr | name | claim | observed | graded by | observation | claim reason |
|---|---|---|---|---|---|---|
| 0x401cc0 | renderer_DrawSceneSoftware | per_frame | never | script | Graded by script (grade_census.py): per_frame claimed, 0 calls in every mission scenario. | The contract states 'Order in frame_outline', indicating this function is part of the frame drawing sequence, which runs once per frame. The caller renderer_Dra |
| 0x405b90 | camera_FreeLookA | per_frame | irregular | claude-sonnet-5 | drive: 0 calls across 906 frames, and jump: only 141/1217 frames have calls, contradicting per_frame. | The contract explicitly states the function runs 'once per frame without dt', directly establishing per_frame cadence. |
| 0x405b90 | camera_FreeLookA | camera_FreeLookA | camera_UpdateChaseOrientation / camera_UpdateChaseOrientation | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (camera, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x4061b0 | camera_FreeLookB | per_frame | per_event | claude-sonnet-5 | per_frame predicts ~1 call/frame in drive but drive shows 0 of 906 frames with calls, and camera-cycle shows only 16.5% presence with bursty calls_per_frame_hist (0:1513, 1:298). | The contract explicitly states 'per-frame pitch/yaw steps', establishing per-frame cadence. This is consistent with the spec's pattern of camera mode per-frame  |
| 0x4061b0 | camera_FreeLookB | camera_FreeLookB | camera_UpdateChaseOrientation / camera_UpdateChaseOrientation | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (camera, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x406840 | camera_ClassifyDistance | irregular | per_frame | claude-sonnet-5 | drive shows 10 calls on 904/906 frames and fire-each shows 10 calls on 889/889 frames, consistent per-frame rather than irregular. | The spec_paragraphs describe the camera test at 0x406840 as part of entity_TickVehicle's per-frame vehicle iteration: each vehicle outside the radius takes a br |
| 0x4071a0 | camera_UpdateBinoculars | per_frame | per_event | claude-sonnet-5 | per_frame predicts ~1 call/frame in mission scenarios like drive, but drive shows 0 calls across 906 frames while camera-cycle shows only 87 bursty calls. | The spec_paragraphs table explicitly lists 0x4071a0 in the 'per-frame' column for view 0xd, and the frame rate section states 'head-look eased at 2*dt', confirm |
| 0x4071a0 | camera_UpdateBinoculars | camera_UpdateBinoculars | camera_UpdatePilotOrientation / camera_UpdatePilotOrientation | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (camera, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x407680 | camera_UpdateHoodView | per_frame | per_event | claude-sonnet-5 | drive: 0 calls across 906 frames contradicts per_frame, and camera-cycle shows bursty 69 calls on 69/1811 frames rather than ~1/frame. | The contract specifies '4*dt easing' and the spec_paragraphs describe camera view updates with 'dt-scaled' head-look easing, indicating per-frame operation whil |
| 0x40a130 | ai_MeleeFrameTick | per_frame | per_event | claude-sonnet-5 | drive: 0 calls across 889 frames and fire-each: 0 calls across 890 frames, but per_frame predicts calls in every mission scenario including these. | The contract states 'Frame AI' and the spec (paragraph 2) places `ai_MeleeFrameTick` in the per-frame flow where `ai_FrameTick` is called per frame by WinMain. |
| 0x40acf0 | ai_TakeLosCheckTurn | per_frame | never | script | Graded by script (grade_census.py): per_frame claimed, 0 calls in every mission scenario. | The contract explicitly states 'returns 1 for exactly one caller per frame' and is 'reset in ai_FrameTick', settling the cadence. |
| 0x4171a0 | ai_UpdateRoadFlee | ai_UpdateRoadFlee | ai_UpdateCombatSteerThrottle / ai_UpdateCombatManeuver | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (ai, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x418200 | ai_ShouldFireWeapon | per_frame | irregular | claude-sonnet-5 | fire-each: 0 calls over 889 frames contradicts per_frame, even though melee: 5160 calls over 1688 frames matches it. | The spec_paragraphs state that ai_FireWeapons 'runs every frame for every AI car' and 'asks ai_ShouldFireWeapon for each mounted weapon', establishing per-frame |
| 0x41ef40 | ai_UpdateFollow | per_frame | init_only | claude-sonnet-5 | per_frame predicts sustained calls, but drive shows 0 calls after frame 674 and melee shows 0 calls across 1688 frames. | Spec point 3 states ai_SetBehaviour runs the update function (follow 0x41ef40), and points 1-2 establish that ai_SetBehaviour is called once per frame for every |
| 0x420d30 | ai_UpdateRouteSearch | per_frame | per_event | claude-sonnet-5 | drive: 9/890 frames have calls (presence 0.0101) and melee: event_corr 1.0, contradicting per_frame which predicts ~95%+ frame coverage. | Spec point 3 identifies this as the update function called by ai_SetBehaviour for goto/evade/race behaviors; spec point 2 establishes that ai_SetBehaviour is ca |
| 0x426f70 | renderer_D3DOpenExecBuffer | renderer_D3DOpenExecBuffer | net_BuildNetgameInitPacket / net_InitAndBuildHandshakePacket | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (renderer, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x427300 | renderer_D3DReleaseExecBuffers | renderer_D3DReleaseExecBuffers | object_ClearEntityList / object_FreeAllAndReset | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (renderer, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x427370 | renderer_D3DFanTexTwoPass | renderer_D3DFanTexTwoPass | renderer_SubmitRoadSegmentGeometry / renderer_SubmitVehiclePolyBatch | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (renderer, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x42a830 | renderer_D3DFanTexBlendWrapRawUV | renderer_D3DFanTexBlendWrapRawUV | renderer_SubmitPrimitiveBatch / renderer_SubmitVertexBatch | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (renderer, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x42ea70 | renderer_TexCacheFlush | renderer_TexCacheFlush | object_ShutdownObjectArray / object_ReleaseEntityTable | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (renderer, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x42ede0 | renderer_TexUploadD3D | renderer_TexUploadD3D | renderer_BlitSurfaceConvert / renderer_CreateSurfaceAndBlit | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (renderer, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x432bc0 | renderer_D3DAppCompareModes | renderer_D3DAppCompareModes | math_Compare3Key / math_CompareTriple | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (renderer, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x4389f0 | math_MatrixRotateByAngVel | per_substep | irregular | claude-sonnet-5 | drive: substep_match 0.5388 with mode 5 calls/frame while step_count_hist peaks at 1 (711 frames), contradicting per_substep's 1:1 call-to-substep prediction. | The spec_paragraphs states the pose is rotated by this function 'in a contact substep' as part of contact impulse resolution, and notes 'In a contact substep th |
| 0x43d070 | physics_SnapToGround | per_frame | init_only | claude-sonnet-5 | drive: 0 calls across 908 live frames (3 calls only before frame 183), contradicting per_frame which predicts ~1 call per frame throughout. | The contract states 'once per frame from entity_TickVehicle', and the framerate spec paragraph confirms 'once per frame through physics_SnapToGround 0x43d070'. |
| 0x441440 | world_ResetSmokeEmitterRate | world_ResetSmokeEmitterRate | sound_MarkListItemFlag / sound_MarkListEntryStopped | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (world, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x441cd0 | renderer_FreeTracers | init_only | irregular | claude-sonnet-5 | melee: 1 call at frame 1003 of 600 frames, occurring on a no-live-player condition, which init_only does not explain. | The contract states 'WinMain teardown', which clears resources at program exit once per process. |
| 0x444e90 | renderer_FreeSkidStrips | init_only | irregular | claude-sonnet-5 | melee: 1 call at frame 1003 (not within first 5s), which init_only cannot explain; drive and fire-each show 0 calls throughout. | The contract explicitly labels this 'WinMain teardown', indicating it runs once at program exit as a teardown mirror per the rules. |
| 0x4471e0 | renderer_GeometryCacheWalk | init_only | per_frame | claude-sonnet-5 | drive: 908 calls across frames 0-1462 (last_frame 1462), far beyond an init_only window, contradicting the init_only claim. | The contract states it is 'Called from WinMain 0x40398f'; WinMain runs once at program startup, making this function init_only. |
| 0x447e10 | image_EvictOldestTexture | image_EvictOldestTexture | object_FreeEntityNode / object_DestroyNamed | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (image, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x448e40 | image_BlitEltSpriteScrollY | per_frame | per_event | claude-sonnet-5 | fire-each: 31 calls on only 23/889 frames with event_corr 1.0, drive: 0 calls, contradicting per_frame's expectation of ~1 call on 95%+ of frames. | The spec_paragraphs locates image_BlitEltSpriteScrollY at 0x4a4f44 within the per-frame ammo-digit drawing routine, stating the digits are redrawn with 'one ste |
| 0x4532c0 | net_Pump | per_frame | never | script | Graded by script (grade_census.py): per_frame claimed, 0 calls in every mission scenario. | Contract explicitly labels it 'per-frame network pump'; spec_paragraphs (network doc) confirms 'runs once per frame' at the same address. |
| 0x4559a0 | net_UpdateJoinPrompt | per_frame | never | script | Graded by script (grade_census.py): per_frame claimed, 0 calls in every mission scenario. | The contract explicitly states 'per frame' when describing the function's behavior. |
| 0x461570 | entity_GetRadarArcContact | per_event(shot) | per_frame | claude-sonnet-5 | drive: 23 calls/frame on 909/909 frames with 0 shot events, contradicting per_event(shot) which predicts 0 calls in drive. | The spec_paragraphs state that weapon_FireShot calls 'arc contact 0x461570' as part of target selection during firing, only when weapon_FireShot executes (trigg |
| 0x466180 | entity_Wreck | entity_Wreck | entity_VehicleDestroyedHandler / salvage_EjectVehicleParts | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (entity, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x466e80 | entity_StartTractionLoss | per_event(impact) | never | claude-sonnet-5 | fire-each: 0 calls across 904 frames despite firing each weapon class, which should include the oil-slick ordnance per the claim's named caller weapon_StepOilSlick. | The contract states 'Called when the ground-sweeping ordnance of 0x4aa150 hits a car,' naming the impact trigger. The spec paragraph confirms this: 'Traction lo |
| 0x466eb0 | entity_HazardHitNearestWheel | per_event(impact) | never | claude-sonnet-5 | drive: 1 impact event recorded but 0 calls, contradicting per_event(impact). | The contract states the function runs when 'car hit by a class 0x33 projectile (handgun bullet)', a specific impact event. |
| 0x467700 | entity_SpecialApplyDamage | entity_SpecialApplyDamage | weapon_DeductAmmoCost / weapon_DeductAmmoCost | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (entity, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x469de0 | sound_GetEngineIgnitionName | sound_GetEngineIgnitionName | weapon_GetDamageStateName / weapon_SelectDamageStateName | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (sound, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x46a7f0 | physics_BrakeApplyDamage | physics_BrakeApplyDamage | weapon_ConsumeAmmoPool / weapon_ConsumeAmmoFromBays | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (physics, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x46bd10 | physics_StepAircraft | physics_StepAircraft | physics_ComputeTireContactForces / physics_ResolveWheelGroundContact | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (physics, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x470580 | image_ReleaseForVideoMode | image_ReleaseForVideoMode | crt_StrdupInsertChar / crt_ConcatOrCopyToSharedBuffer | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (image, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x475690 | renderer_SwDDrawPresent | renderer_SwDDrawPresent | ds3d_InitListenerAndBuffer / net_InitAndSyncGameSession | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (renderer, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x494e20 | math_TransformMul | math_TransformMul | math_TransformPointsByMatrix / math_TransformPoints3x3Loop | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers |  |
| 0x496110 | shell_GfxVisibilityRange | shell_GfxVisibilityRange | object_PropertyDispatch / input_HandlePropertyMsg | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (shell, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x497a30 | shell_MenuCancel | shell_MenuCancel | object_NotifyShutdownEntities / object_NotifyStateChange | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (shell, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x49a670 | image_SmkUpdate | per_frame | init_only | claude-sonnet-5 | drive: 662973 calls all before frame 658 then 0 of 906 frames live, which is init_only not per_frame. | The contract explicitly states 'per-frame Smacker pump from WinMain', unambiguously settling the cadence. |
| 0x49cdf0 | shell_ToggleMapScreen | shell_ToggleMapScreen | sound_LoadMissionAudioState / sound_LoadCmapGdsSfx | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (shell, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x49d000 | shell_RunPlayModeKeys | per_frame | irregular | claude-sonnet-5 | drive: calls_per_frame_hist shows 889 frames with 0 calls and only 1 frame with 64+ (65535 total), which contradicts per_frame's expectation of ~1 call on 95%+ of frames. | The contract explicitly states 'per-frame key handler for the non-driving modes', which directly settles the cadence as per_frame. |
| 0x4a2070 | object_ChunkUpdate | per_frame | per_event | claude-sonnet-5 | drive: present on only 292/890 frames (32.7%) with mean 8.06 calls/frame and cv 1.67, not the 95%+ near-1 pattern per_frame requires. | The contract explicitly states 'class 0x35 per-frame update', directly specifying the cadence. |
| 0x4a3560 | weapon_SetTrigger | per_frame | never | script | Graded by script (grade_census.py): per_frame claimed, 0 calls in every mission scenario. | The spec_paragraphs state that ai_FireWeapons 'runs every frame for every AI car' and calls weapon_SetTrigger (0x4a3560) to pull the trigger; the contract confi |
| 0x4a6170 | weapon_LinkSameClassAndMount | weapon_LinkSameClassAndMount | weapon_AssignDamageTargets / weapon_ResolveAmmoAndFireLink | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (weapon, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x4a92e0 | weapon_StepTumblingMine | per_frame | irregular | claude-sonnet-5 | drive: 0 calls across 890 frames contradicts per_frame; fire-each: only 74.5% presence with cv 0.58 indicates irregular/per_event-like bursting, not per_frame. | The contract states 'Every frame a 1 m vertical segment is swept for vehicles', and the spec lists this as a step function for active projectiles (0xf, 0x10) du |
| 0x4aa150 | weapon_StepOilSlick | per_frame | never | script | Graded by script (grade_census.py): per_frame claimed, 0 calls in every mission scenario. | The contract explicitly states 'Each frame it sweeps pd+0x3c 1 m vertical segments', establishing per-frame cadence. The spec confirms this is the oil-slick ste |
| 0x4aa450 | weapon_StepFirePatch | per_frame | never | script | Graded by script (grade_census.py): per_frame claimed, 0 calls in every mission scenario. | The contract states 'every frame with contact it spawns the impact effect', establishing per_frame cadence. The spec_paragraphs entry for 0x11 is truncated but  |
| 0x4aa5b0 | weapon_StepRocket | per_frame | never | script | Graded by script (grade_census.py): per_frame claimed, 0 calls in every mission scenario. | The contract explicitly states 'Smoke trail each frame', establishing per_frame cadence. The spec table confirms this is a step function for FireRite rocket. |
| 0x4ab920 | weapon_StepHeatMissile | per_frame | never | script | Graded by script (grade_census.py): per_frame claimed, 0 calls in every mission scenario. | The contract explicitly states 're-acquires weapon_FindHeatTarget every frame', and the spec table confirms 'every step', both settling the cadence as per_frame |
| 0x4ab920 | weapon_StepHeatMissile | weapon_StepHeatMissile | entity_UpdateMotionStep / entity_StepMotionAndCollide | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (weapon, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x4ace20 | weapon_StepClusterBomb | weapon_StepClusterBomb | entity_UpdatePositionAndCollision / entity_UpdateMovementStep | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (weapon, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x4b5310 | shell_GarageAddWheel | shell_GarageAddWheel | object_AddNamedRecord / object_RegisterClassRecord | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (shell, non-utility; read in verify/BLIND-PASS-4.md) |  |
| 0x4bb5a0 | renderer_DrawShadowPartClass9 | renderer_DrawShadowPartClass9 | object_RenderVisibleFaces / object_RenderVisiblePolygons | claude-sonnet-5 | two-reader rule (section 6): blind `different` from both readers (renderer, non-utility; read in verify/BLIND-PASS-4.md) |  |

## INCONCLUSIVE awaiting the early-attach census (27)

fsm_InitStepCounters 0x414ba0, sound_SetCbEnabled 0x423600, physics_InitCollision 0x4346d0, physics_ShutdownCollision 0x434960, renderer_InitSmoke 0x441150, weapon_FreeFlamers 0x443c50, ffb_Shutdown 0x445b10, object_FreeAllGeometryRecords 0x446870, image_ShutdownTextureCache 0x447c80, image_FreeEltTables 0x447fd0, image_ShutdownFaceTextures 0x44a630, image_ShutdownTexAnims 0x44b100, input_CloseDevices 0x44dcc0, camera_ResetCombatView 0x44df80, net_ClearSpawnPoints 0x451960, entity_FreeTable 0x4571a0, entity_AddUnregisterHook 0x457290, object_HideNonPlayerCockpitInstruments 0x4577f0, renderer_SpanArenaStaticInit 0x472de0, renderer_InitDrawPools 0x48f9b0, world_ClearTerrainObjectList 0x4925e0, math_InitRsqrtTable 0x493c50, weapon_FreeOrdnanceTable 0x49f5c0, weapon_RestoreMountState 0x4a34c0, entity_LabelMapInsert 0x4ad450, salvage_FreeAll 0x4b19d0, object_InstallShadowReleaseHook 0x4b84e0

## Other INCONCLUSIVE (16)

- 0x409270 camera_EnterEndOrbit: claim irregular; No scenario exercises the claimed trigger (network end of match). The call in jump contradicts the claim's singular-event prediction, but the absence of the tri
- 0x4208d0 ai_FindRaceStartNode: claim per_event; Graded by script (grade_census.py): per_event(load) claimed; no phase-1 scenario produces that event.
- 0x4367e0 physics_RebuildCollision: claim per_event; radar-lock shows 82 impact events but 0 calls, yet take-damage (the scenario meant to trigger ApplyDamage callers) is absent from the inputs, so the claim canno
- 0x441260 renderer_ShutdownSmoke: claim init_only; melee frame 1003 is past the measurement window; per rules, teardown functions show 0 calls in every scenario window and are INCONCLUSIVE, not verifiable from m
- 0x446c70 renderer_ShutdownGeometryCache: claim init_only; melee: 1 call at frame 1003 on a non-live frame; drive and fire-each: 0 calls. An init_only teardown function cannot be verified within the measurement window, 
- 0x4524e0 net_WriteScoreFile: claim per_event; Graded by script (grade_census.py): per_event(load) claimed; no phase-1 scenario produces that event.
- 0x460c80 entity_UpdateRadarContact: claim irregular; drive and fire-each both show calls_in_window 0 with only 2 calls before frame ~5s cutoff, so no scenario exercised sustained per-contact radar updates to confi
- 0x461770 entity_ActivateRadarJammer: claim per_event; Graded by script (grade_census.py): per_event(key) claimed; no phase-1 scenario produces that event.
- 0x467e30 renderer_DrawSpecialsPanel: claim per_event; Graded by script (grade_census.py): per_event(key) claimed; no phase-1 scenario produces that event.
- 0x4905e0 renderer_FreeDrawBuffers: claim init_only; radar-lock: 1 call at frame 1686 of 1289 total frames, which is not within the first-5s init window the claim describes, and no scenario captures program teardo
- 0x4970f0 player_LoadPlyrDef: claim irregular; drive: 0 calls; fire-each: 0 calls; melee: 0 calls. None of the scenarios exercise shell menu transitions that the claim reason specifies as the trigger.
- 0x4979a0 shell_MenuDone: claim per_event; Graded by script (grade_census.py): per_event(key) claimed; no phase-1 scenario produces that event.
- 0x4a4a40 weapon_ApplyAmmoBonus: claim per_event; Graded by script (grade_census.py): per_event(spawn) claimed; no phase-1 scenario produces that event.
- 0x4a8240 weapon_ApplyFlameDamage: claim per_event; fire-each: 0 calls despite impact events (1), but inputs don't confirm the flamer was among the weapons fired, so per_event(impact via flame) can't be confirmed
- 0x4b1610 salvage_CollectFromWreck: claim per_event; melee: 218 explosion and 71 impact events but 0 calls, with no telemetry confirming an actual vehicle-destroyed (damage) event as required by the claim.
- 0x4b1a20 salvage_LoadMissionFsi: claim per_event; Graded by script (grade_census.py): per_event(save) claimed; no phase-1 scenario produces that event.

## Blind `different` (263; not disputes under section 6 for non-utility rows, each read in BLIND-SAMPLE-2.md / BLIND-PASS-3.md)

renderer_NextHorizonQuad (blind: entity_AllocWheelContactRecord), renderer_DrawSceneHardware (blind: renderer_RenderFrameSequence), renderer_NextCloudPoly (blind: world_GetNextRoadSegment), camera_PopState (blind: net_InitDPSessionSlot), camera_ApplyViewOptions (blind: camera_InitViewParams), camera_FreeLookA (blind: camera_UpdateChaseOrientation), camera_GetHeadingQuat (blind: math_BuildOrientQuatFromVelocity), camera_FreeLookB (blind: camera_UpdateChaseOrientation), camera_ToggleBinoculars (blind: object_InitTransformStateMachine), camera_UpdateBinoculars (blind: camera_UpdatePilotOrientation), camera_EnterHoodView (blind: entity_InitPlayerEntityState), camera_UpdateHoodView (blind: camera_UpdatePilotOrientation), camera_EnterChaseReverse (blind: object_InitPlayerEntityState), camera_EnterChaseFrontQuarter (blind: entity_InitPlayerEntityState), camera_EnterChaseRearQuarter (blind: entity_InitPlayerEntityState), camera_UpdateTargetView (blind: simclock_AdvanceAndDispatch), camera_EnterEndOrbit (blind: entity_InitPlayerEntity), ai_ActivateGetDownCheat (blind: entity_NotifyDestroyedPlaySound), ai_InsertBridgeCell (blind: object_InsertBinaryTreeNode), ai_PathExpandRoadLegs (blind: math_ClipPolygonPoints), ai_TryRoadShortcut (blind: entity_CheckProximityCollision), ai_AstarRelaxChildren (blind: object_PropagateBoundingVolume), ai_SteerToHeading (blind: physics_ComputeWheelSlipRatio), fsm_RunMachines (blind: entity_PruneLinkedList), ai_UpdateRoadFlee (blind: ai_UpdateCombatSteerThrottle), entity_PredictPosition (blind: entity_ComputeWeaponMuzzlePoint), ai_RamApproachVelocity (blind: physics_ComputeAvoidanceSteerVector), ai_ProbeTerrainAhead (blind: physics_ComputeCollisionTimeStep), ai_TestControlCandidate (blind: ai_AttemptEvasiveManeuver), ai_IsTargetOffRoad (blind: entity_IsSameLinkClass), ai_UpdateFollow (blind: ai_SteerTowardTarget), ai_UpdateRacePath (blind: ai_UpdateThrottleSteer), ai_UpdateEvadePath (blind: ai_UpdateCombatTargeting), sound_FindLoadedSample (blind: object_FindByNameOrFirst), sound_ResumeVoices (blind: sound_StopAllActiveSounds), sound_AllocVoice (blind: net_ProcessPlayerJoinRequest), sound_RestartEvictedLoops (blind: entity_UpdateDamageFlagsList), sound_CullByDistance (blind: entity_UpdateProximityFlags), sound_EvictInstance (blind: object_SetStateFlags), sound_PlayOnObjectSustained (blind: sound_PlayNamedWav), sound_CdWatchdog (blind: net_UpdatePollTimer), sound_CdCacheMode (blind: sound_PollMciMusicStatus), sound_CdReadToc (blind: sound_QueueCdTrackList), sound_PlayHorn (blind: object_CreateFromEntityClassRecord), sound_PlayEngineIgnition (blind: entity_GetNamedPartValue), sound_PlayIfPlayerObject (blind: sound_PlayNamedWav), sound_ReleaseDirectSound (blind: net_ReleaseSessionInterfaces), sound_DestroyInstance (blind: object_DestroyEntity), renderer_D3DOpenExecBuffer (blind: net_BuildNetgameInitPacket), renderer_D3DCloseExecBuffer (blind: net_EmitQueuedPacket), renderer_D3DReleaseExecBuffers (blind: object_ClearEntityList), renderer_D3DFanTexTwoPass (blind: renderer_SubmitRoadSegmentGeometry), renderer_D3DFanFlat (blind: renderer_SubmitSpriteStrip), renderer_D3DFanFlatAlpha (blind: renderer_SubmitSpriteParticleBatch), renderer_D3DFanTexAlpha30 (blind: renderer_SubmitParticleQuads), renderer_D3DFanTexBlendGouraudClamp (blind: renderer_SubmitParticleVertices), renderer_D3DFanTexBlendGouraudWrap (blind: renderer_SubmitVertexBatch), renderer_D3DFanTexBlendClampRawUV (blind: renderer_SubmitPolyParticles), renderer_D3DFanTexBlendWrapRawUV (blind: renderer_SubmitPrimitiveBatch), renderer_D3DFanTexAlpha60RawUV (blind: renderer_SubmitPolyParticles), renderer_D3DFanTexAlpha30RawUV (blind: renderer_SubmitVertexBatch), renderer_D3DFanTexClamp (blind: renderer_SubmitVertexBatch), renderer_D3DFanTexFlatClamp (blind: renderer_SubmitRoadSegmentVertices), renderer_D3DFanTexFlatWrap (blind: renderer_SubmitVehiclePolys), renderer_D3DFanTexGouraudClamp (blind: renderer_SubmitParticleOrSpriteBatch), renderer_PluginDrawEdgeStrips (blind: renderer_SetDualLightState), renderer_BlitBackToFront (blind: net_ReleaseDirectPlaySession), renderer_TexCacheFlush (blind: object_ShutdownObjectArray), renderer_TexUploadD3D (blind: renderer_BlitSurfaceConvert), renderer_AddTextureFormat (blind: sound_RegisterChannelDesc), renderer_D3DAppDestroy (blind: renderer_ReleaseD3DResources), renderer_Dx5DrawHostOpen (blind: renderer_CreateMainWindow), renderer_D3DAppCompareModes (blind: math_Compare3Key), renderer_CardHostOpen (blind: renderer_InitWindowDevice), physics_SweepSegmentVsVehicles (blind: entity_FindNearestCollisionCandidate), physics_BuildNodeCollisionShapes (blind: entity_UpdateChainState), physics_CheckImpact (blind: physics_HandleRolloverRecovery), camera_ComputeCockpitSway (blind: physics_ComputeSuspensionMatrix), physics_StepVehicle (blind: physics_UpdateVehicleCollisionResponse), physics_IntegrateVehicleMotionLite (blind: physics_ComputeWheelContactResponse), physics_ApplySideSlipFriction (blind: physics_ApplyForceImpulse), physics_ApplyFriction (blind: physics_ApplyPointImpulse), physics_SweepPointVsCollider (blind: physics_HandleContactCollisionDispatch), world_CollectWalkableFaces (blind: entity_CollectDamagedParts), world_CollectWalkableFacesTree (blind: entity_CollectDamagedPartsRecursive), world_ResetSmokeEmitterRate (blind: sound_MarkListItemFlag), renderer_QueueSmokePuff (blind: entity_EmitSkidmarkDecal), renderer_InitSmokeTrails (blind: object_InitClassTablesAndFreeList), weapon_AddSmokeTrail (blind: entity_EmitDamageEvent), weapon_ExtendSmokeTrail (blind: entity_UpdateLightSlerpToTarget), weapon_AgeFlamerStreams (blind: weapon_UpdateFlamerInstances), renderer_InitRearMirror (blind: camera_InitFollowCamFromTrack), renderer_DrawRearMirror (blind: camera_RunRearViewEffect), object_CloneGeometryRecord (blind: object_CloneHashEntry), object_SelectGeometryLod (blind: object_UpdateEntityTextureState), renderer_InitGeometryCache (blind: heap_InitPrivateHeaps), image_EvictOldestTexture (blind: object_FreeEntityNode), crt_NextToken (blind: crt_StrtokLikeSplitCopy), image_BlitSpriteToMap (blind: sound_PlayGearShiftWav), image_BlitEltSpriteScrollX (blind: object_LookupClassTripleAndBuildTransform), image_CreateTextureInstance (blind: object_CreateInstanceByClassName), image_CopyFaceTextures (blind: object_BuildInstanceListFromHash), image_UnloadObjectFaceTextures (blind: object_ResetChainFlagsByKey), image_SetFaceTextureFrame (blind: object_SetNamedFieldValue), renderer_GetFaceTexture (blind: sound_LoadWavEntry), image_GetPrivateFaceBitmap (blind: object_LookupOrCreateClassRecord), image_RegisterMapRef (blind: object_CreateRecordAndHashInsert), image_TexAnimTick (blind: object_AnimateTexAnmAndUnlink), input_FindButtonChannel (blind: input_ResolveChannelIndex), input_AddAnalogBinding (blind: menu_RegisterOrFindEntry), input_UpdateControls (blind: ai_UpdateThrottleControllers), input_CloseDevices (blind: shell_ResetGameState), net_SendWeaponFire (blind: net_SendHandshakePacket), renderer_QueueObjectsMirror (blind: entity_CollideSweepAndSpawn), renderer_QueueObjects (blind: entity_ProcessCollisionDamageSweep), object_SetYawMatrix (blind: math_InitRotationLimitsFromAngle), object_GetParent (blind: entity_FindListHead), renderer_DrawTargetBrackets (blind: object_DrawEntityStatusGauge), renderer_QueueTerrainClutter (blind: ai_UpdateTrafficGrid), renderer_BspInsertNode (blind: object_InsertIntoBspTree), renderer_DrawObjectBspAttached (blind: entity_RenderDamageTreeChain), renderer_DrawObjectBspHierarchy (blind: entity_ProcessDestructionTree), renderer_BspEmitSplitterPlane (blind: math_TransformPointIntoGlobalRecord), renderer_BspAddNodeTree (blind: object_PropagateTransformToChildren), renderer_DrawObjectChildrenBsp (blind: entity_UpdateChainAndRender), object_DropRefIfReleased (blind: object_ReleaseEntityRef), entity_RadarSystemInit (blind: world_InitRadmaskAndHeaps), entity_UpdateRadarContact (blind: entity_UpdateOrientation), entity_RadarSelectNextTarget (blind: object_ReassignLinkOwner), entity_RadarSelectPrevTarget (blind: object_PromoteLinkedListMember), entity_RadarSetTarget (blind: object_SelectOrInsertByKey), object_SetClass (blind: object_SetClassAndLink), object_RunPendingInits (blind: object_PurgeClassListEntries), entity_TickAll (blind: object_ProcessDestroyQueue), entity_PostTickAll (blind: object_UpdateClassDispatchList), object_GetVelocity (blind: object_DispatchClassFn), renderer_InitBinocularMask (blind: zfs_InitRouteArchives), entity_FindNearestTurret (blind: entity_FindNearestExcludingFlag), entity_InitVehicle (blind: entity_AssignDamagePartMapping), entity_UpdateState (blind: entity_UpdateDestructionState), entity_ApplyDamage (blind: entity_DecayDamageAccumulators), entity_Wreck (blind: entity_VehicleDestroyedHandler), entity_UpdateDamageSmoke (blind: sound_UpdateEngineLoopByThrottle), entity_HazardHitNearestWheel (blind: ai_NearestNodeSalvageQueue), entity_UpdateLights (blind: entity_ToggleBrakeLightState), entity_SpecialApplyDamage (blind: weapon_DeductAmmoCost), object_GetCachedTravelHeading (blind: entity_RegisterSoundEmitterSlot), object_GetCachedHeading (blind: entity_RegisterSoundEmitter), object_GetCachedBoundRadius (blind: entity_RegisterSoundSource), object_CacheAddEntry (blind: entity_RecordSoundEmitHistory), object_GetCachedBearing (blind: entity_GetOrCalcPairDistance), sound_GetEngineIgnitionName (blind: weapon_GetDamageStateName), physics_ShiftCurveTest (blind: math_PointInTrapezoidTest), physics_BrakeApplyDamage (blind: weapon_ConsumeAmmoPool), object_ScriptDestroy (blind: object_LoadInstance), entity_TickAircraftDt (blind: entity_UpdateDamageFx), physics_StepAircraft (blind: physics_ComputeTireContactForces), net_ApplyAircraftState (blind: entity_ApplyWeaponHitParams), physics_WheelApplyDamage (blind: weapon_ApplyDamageToArmorSection), entity_HandgunAnimTick (blind: ai_UpdateThrottleState), camera_AddHeadSwayImpulse (blind: physics_ApplyScaledForceImpulse), weapon_AimPofPitchAtTarget (blind: ai_SteerTowardPath), entity_VitalPartApplyDamage (blind: math_DeductFromBudgetArray), object_SpinnerApplyDamage (blind: entity_DepleteAmmoAndSpawnDebris), object_BreakableApplyDamage (blind: object_SpawnDebrisEffect), image_ReleaseForVideoMode (blind: crt_StrdupInsertChar), image_LoadM16Variant (blind: vfs_LoadFileHandleWithHashCheck), renderer_ReleaseM16Texture (blind: vfs_ReplaceFileExtension), renderer_LoadTexturePair (blind: image_LoadTextureResolutionInfo), renderer_FreeTexturePair (blind: vfs_FreeAndRebuildPath), camera_Init (blind: camera_BuildViewFrustum), camera_SetViewportRect (blind: physics_BuildBoxCollisionFrame), renderer_SpanStepActiveEdges (blind: crt_RbTreeEraseFixup), renderer_SpanBufferScanPolygon (blind: world_InsertPolygonSplit), renderer_SpanBufferFlush (blind: entity_FlushAndResetChains), renderer_DrawPointSW (blind: entity_SpawnParticleRecord), renderer_SwDDrawClear (blind: sound_InitDs3dListener), renderer_SwDDrawPresent (blind: ds3d_InitListenerAndBuffer), renderer_SwDDrawSetPaletteRange (blind: entity_UpdateDamageTexture), renderer_DisplayOpenWindow (blind: renderer_CreateAndRunWindow), renderer_FillRightBottomEdge (blind: image_FlipDibVertical), font_LoadBitmapFont (blind: object_LoadRecordFile), font_DrawGlyph8 (blind: renderer_BlitSpriteFrame), light_InitTimeOfDay (blind: world_InitMissionMapState), light_AddDynamic (blind: sound_AddListenerSoundEffect), light_CollectVisible (blind: entity_UpdateDebrisCollisionList), light_SelectForObject (blind: ai_FindNearestThreats), light_GetShadowDirection (blind: ai_ComputeAvoidanceVector), renderer_FadePalette (blind: sound_PlayStartupJingle), renderer_SpanFillGouraud (blind: renderer_DrawTexturedSpanBlock), renderer_SpanFillTexAffine (blind: renderer_DrawAffineTexturedSpan), renderer_SpanPolyTexKeyedAffine (blind: entity_AllocAndTransformInstance), renderer_SpanFillTexTranslucentDestKeyAffine (blind: renderer_DrawTexturedPolySpan), renderer_SpanPolyTexTranslucentDestKeyPersp (blind: object_AllocateTransformedLink), renderer_SpanPolyTexLitPerspUvClamp (blind: object_AllocateAndTransformEntity), renderer_SpanPolyTexGouraudAffineUvClamp (blind: object_AllocAndBuildTransform), renderer_SpanFillTexGouraudPerspUvClamp (blind: renderer_RasterizeTexturedSpanTable), renderer_SpanPolyTexKeyedGouraudAffine (blind: object_AllocTransformInstance), renderer_SpanPolyTexKeyedGouraudPersp (blind: physics_ComputeContactBasis), renderer_InitRoadSegments (blind: object_InitPathTablesAndBounds), world_FindNearestRoadVertex (blind: entity_FindNearestEntityAndRecord), renderer_QueueRoadsAndDecals (blind: entity_GenerateDebrisAndRoadSparks), renderer_QueueHeadlightBeam (blind: light_UpdateHeadlight), renderer_DrawBillboardObject (blind: object_RenderLinkedNodeList), renderer_InitDrawPools (blind: heap_InitPools), renderer_FlushDepthBuckets (blind: object_UpdateDamageAndResetFrame), renderer_DrawHeadlightBeam (blind: object_RenderLinkedChainSegments), renderer_SetTerrainResolution (blind: ai_SetDifficultyParams), renderer_QueueTerrain (blind: physics_InitDebrisQuadFromVehicle), world_GetTerrainHeight (blind: math_ClampAndRoundToFixedQ10), renderer_TransformTerrainVerts (blind: entity_UpdateTransformAndBounds), math_TransformMul (blind: math_TransformPointsByMatrix), math_TransformPlane (blind: math_TransformPointByMatrixInverse), shell_GfxMonitorBrightness (blind: renderer_HandleDisplayModeMessage), shell_GfxVisibilityRange (blind: object_PropertyDispatch), shell_GfxClouds (blind: input_HandleToggleMessage), shell_GfxExtInstrumentDisplay (blind: input_HandleConfigOp), shell_GfxTerrainTextures (blind: shell_HandlePauseToggleCallback), shell_AudioSfxLevel (blind: shell_HandleByteOptionCallback), shell_MenuHandleMouse (blind: object_HitTestClickTarget), shell_MenuDone (blind: shell_HandleMessage4), shell_MenuCancel (blind: object_NotifyShutdownEntities), font_InitTextWindows (blind: entity_InitPhysicsRecords), font_CreateTextWindow (blind: entity_CreateFromDef), font_CreateTextField (blind: object_CreateEntityInstance), font_SetPrefix (blind: object_ReplaceNameString), input_TextFieldHandleKey (blind: input_EditTextFieldChar), world_ParseMissionCode (blind: startup_ParseCmdLineOption), shell_ToggleMapScreen (blind: sound_LoadMissionAudioState), entity_RecycleExplosions (blind: entity_RehashDestroyedNames), weapon_ShowMuzzleFlash (blind: sound_UpdateEntityLoopSource), weapon_RegisterOrdnance (blind: weapon_RegisterInstance), weapon_ProjectileAdvance (blind: physics_ApplyImpulseAlongVelocity), weapon_GetVehicleInstances (blind: object_FindRecordByIdAndCopyFields), weapon_ApplyClassDamage (blind: weapon_TransferAmmoToRecord), renderer_InitWeaponPanel (blind: weapon_InitVehicleDamageTextures), weapon_ApplyAmmoBonus (blind: entity_TransferSalvagedParts), weapon_GetInstanceMaxHp (blind: object_FindClassRecordByHandle), weapon_CreateInstance (blind: weapon_CreateImpactRecord), weapon_LinkSameClassAndMount (blind: weapon_AssignDamageTargets), weapon_UpdateInstanceFiring (blind: weapon_UpdateMountHeatAndReload), weapon_SpawnImpactEffect (blind: sound_PlayEntityEventSample), weapon_UpdateDelayedImpacts (blind: weapon_UpdateReloadQueue), weapon_StepFirePatch (blind: entity_ProcessOrdnanceList), weapon_StepRocket (blind: entity_UpdatePathMotion), weapon_StepRadarMissile (blind: ai_UpdateTargetSteerToward), weapon_StepGuidedMissileNoJam (blind: entity_UpdateTowCableTarget), weapon_StepHeatMissile (blind: entity_UpdateMotionStep), weapon_StepBullet (blind: physics_UpdateEntityMotionAndCollision), weapon_StepMortarShell (blind: entity_UpdatePositionAndCollide), weapon_StepGroundFireCanister (blind: entity_UpdateMoveTarget), weapon_StepClusterBomb (blind: entity_UpdatePositionAndCollision), bwd2_BindBodyMapTree (blind: object_FindNodeByNameRecursive), entity_ExportVehicleRecords (blind: entity_BuildStatsSnapshot), salvage_LoadMissionFsi (blind: vfs_LoadIniOverridesForFile), shell_GarageListBrakes (blind: object_InitClassTableEntries), shell_GarageAddWheel (blind: object_AddNamedRecord), bwd2_LoadScroungeSdf (blind: world_LoadWrldPatchFromPath), bwd2_ApplyStructureXdfTree (blind: object_PropagateClassStyleRecursive), bwd2_LoadXdf (blind: world_LoadWrldrRecord), renderer_DrawShadowPart (blind: object_RenderVisibleFaces), renderer_DrawShadowPartClass9 (blind: object_RenderVisibleFaces), renderer_DrawObjectShadow (blind: entity_UpdateLinkedTransforms)

## Second reader (`reader2`) `different` (49)

camera_CompareLookYaw (blind: math_CompareFloatToGlobal), camera_FreeLookA (blind: camera_UpdateChaseOrientation), camera_FreeLookB (blind: camera_UpdateChaseOrientation), camera_UpdateBinoculars (blind: camera_UpdatePilotOrientation), camera_EnterMissileCam (blind: object_SpawnQueuedEntity), ai_UpdateRoadFlee (blind: ai_UpdateCombatManeuver), renderer_D3DOpenExecBuffer (blind: net_InitAndBuildHandshakePacket), renderer_D3DReleaseExecBuffers (blind: object_FreeAllAndReset), renderer_D3DFanTexTwoPass (blind: renderer_SubmitVehiclePolyBatch), renderer_D3DSetDrawState (blind: ffb_EmitStateDeltaCommands), renderer_D3DFanTexBlendWrapRawUV (blind: renderer_SubmitVertexBatch), renderer_TexCacheFlush (blind: object_ReleaseEntityTable), renderer_TexUploadD3D (blind: renderer_CreateSurfaceAndBlit), renderer_D3DAppCompareModes (blind: math_CompareTriple), physics_SweepPointVsNodeTree (blind: physics_FindNearestEntityHit), math_PlaneHeightAtXZ (blind: math_PlaneSolveZ), world_ResetSmokeEmitterRate (blind: sound_MarkListEntryStopped), image_EvictOldestTexture (blind: object_DestroyNamed), math_AngleDiffWrapped (blind: math_WrapAngleDelta), renderer_DrawPlayerNameTag (blind: font_DrawValueAtWorldPos), entity_Wreck (blind: salvage_EjectVehicleParts), renderer_FreeObjectGeometryTree (blind: object_RecurseSiblingChain), entity_SpecialApplyDamage (blind: weapon_DeductAmmoCost), sound_GetEngineIgnitionName (blind: weapon_SelectDamageStateName), physics_BrakeApplyDamage (blind: weapon_ConsumeAmmoFromBays), physics_StepAircraft (blind: physics_ResolveWheelGroundContact), image_ReleaseForVideoMode (blind: crt_ConcatOrCopyToSharedBuffer), renderer_DrawPolyOutline (blind: renderer_DrawPolylineStrip), renderer_SwDDrawPresent (blind: net_InitAndSyncGameSession), font_SetBackgroundColour (blind: crt_FillOrCopyByte256), font_DrawGlyph16 (blind: object_BlitSpriteMaskedRow), renderer_SpanPolyTexLitPersp (blind: object_CreateInstanceWithOrientation), renderer_SpanPolyTexGouraudPerspUvClamp (blind: entity_AllocAndBlendTransform), math_TransformMul (blind: math_TransformPoints3x3Loop), shell_MenuAbortMission (blind: renderer_SelectDeviceDescriptor), shell_OptionArcadePhysics (blind: input_HandleToggleMessage), shell_OptionDifficultyLevel (blind: ffb_AccessAxisByteProperty), shell_GfxVisibilityRange (blind: input_HandlePropertyMsg), shell_GfxShadowDetail (blind: object_PropAccessorByte), shell_MenuCancel (blind: object_NotifyStateChange), shell_ToggleMapScreen (blind: sound_LoadCmapGdsSfx), entity_BuildExplosionDamage (blind: object_LookupNameHash), weapon_LinkSameClassAndMount (blind: weapon_ResolveAmmoAndFireLink), weapon_StepOilSlick (blind: weapon_FireOrdnanceTrace), weapon_StepHeatMissile (blind: entity_StepMotionAndCollide), weapon_StepClusterBomb (blind: entity_UpdateMovementStep), vfs_ReadLine (blind: vfs_ReadConfigLineToken), shell_GarageAddWheel (blind: object_RegisterClassRecord), renderer_DrawShadowPartClass9 (blind: object_RenderVisiblePolygons)

## Holds (35)

- 0x402630 vfs_ParseTaggedNameLine [utility]: blind PASS from one reader (claude-sonnet-5 judged same); section 6 needs two readers
- 0x40b450 object_HealthFraction [oracle]: health_fraction verdict INCONCLUSIVE, PASS: 28 + 72 x min side ratio while engine / suspension / brakes are intact; the unscaled 0..1 component ratio (stock bug) once one is below 0.99 (not a PASS)
- 0x43f030 math_PlaneHeightAtXZ [utility]: blind PASS from one reader (claude-sonnet-5 judged same; the other reader judged different); section 6 needs two readers
- 0x44f180 math_AngleDiffWrapped [utility]: blind PASS from one reader (claude-sonnet-5 judged same; the other reader judged different); section 6 needs two readers
- 0x458a30 math_AngleDiffToOctant [utility]: blind PASS from one reader (claude-sonnet-5 judged same); section 6 needs two readers
- 0x466ca0 entity_UpdateDamageSmoke [oracle]: damage_smoke verdict INCONCLUSIVE, PASS: sets ent+0x454 bit 0x100 on the frame object_HealthFraction x 0.01 drops below 0.75 and keeps it while below (not a PASS)
- 0x46a0c0 physics_ShiftCurveTest [oracle]: physics_ShiftCurveTest: engine_gear 'treats every throttle >= 0.0625 as the full set (the interpolated ShiftCurveTest never passes)'; the oracle never exercised it, so no oracle PASS
- 0x46a320 physics_UpdateEngine [oracle]: drive_power verdict INCONCLUSIVE, PASS: eng+0x10 = eng+0x14 x f x rpm x (7000 - rpm) / 3500^2 on every frame, P read live (not a PASS)
- 0x46a890 physics_BrakeSetStrength [oracle]: brake_effective verdict INCONCLUSIVE, PASS: offline brake+0x10 = 2300 / m with m = ent+0xa4 read live (1951 kg Piranha), no fit (not a PASS)
- 0x46fb30 vfs_CacheInit [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible); section 6 needs two readers
- 0x46fd40 vfs_ReleaseFile [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible); section 6 needs two readers
- 0x470660 vfs_BuildPixPackIndex [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible); section 6 needs two readers
- 0x470ac0 vfs_FreePixPackIndex [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible); section 6 needs two readers
- 0x470bc0 vfs_PixPackReleaseEntry [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible); section 6 needs two readers
- 0x470c40 vfs_PixPackEntrySize [utility]: blind PASS from one reader (claude-sonnet-5 judged same); section 6 needs two readers
- 0x471250 vfs_MountGameArchives [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible); section 6 needs two readers
- 0x4716b0 vfs_ReadPrjInfoValue [utility]: blind PASS from one reader (claude-sonnet-5 judged same); section 6 needs two readers
- 0x479010 math_HsvToRgb [utility]: blind PASS from one reader (claude-sonnet-5 judged same); section 6 needs two readers
- 0x494170 math_MatrixFromQuat [utility]: blind PASS from one reader (claude-sonnet-5 judged same); section 6 needs two readers
- 0x494460 math_MatrixFromAxisAngle [utility]: blind PASS from one reader (claude-sonnet-5 judged same); section 6 needs two readers
- 0x494ef0 math_TransformPlane [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible; the other reader judged different); section 6 needs two readers
- 0x499110 vfs_ReadBufferLine [utility]: blind PASS from one reader (claude-sonnet-5 judged same); section 6 needs two readers
- 0x49c6d0 math_MidpointDisplace [utility]: blind PASS from one reader (claude-sonnet-5 judged same); section 6 needs two readers
- 0x49e0f0 math_Filter2Init [utility]: blind PASS from one reader (claude-haiku-4-5-20251001 judged compatible); section 6 needs two readers
- 0x4ad640 vfs_MakeFileName [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible); section 6 needs two readers
- 0x4b1df0 vfs_ParseZixPathTables [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible); section 6 needs two readers
- 0x4b20f0 vfs_ReadLine [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible; the other reader judged different); section 6 needs two readers
- 0x4b2ac0 vfs_FindNextZixMatch [utility]: blind PASS from one reader (claude-sonnet-5 judged compatible); section 6 needs two readers
- 0x4f8640 (no row) [oracle-field]: engine_rpm PASS: 0x4f8640 gear ratio table has no row in symbols/globals.tsv or tables.tsv; nothing to promote
- 0x4bd144 (no row) [oracle-field]: brake_effective INCONCLUSIVE, PASS: physics_BrakeSetStrength 0x46a890 / 0x4bd144 = 2300 has no row in symbols/globals.tsv or tables.tsv; nothing to promote
- 0x4bc630 (no row) [oracle-field]: health_fraction INCONCLUSIVE, PASS: 0x4bc630 / 0x4bc634 = 72 / -28 has no row in symbols/globals.tsv or tables.tsv; nothing to promote
- 0x4bc634 (no row) [oracle-field]: health_fraction INCONCLUSIVE, PASS: 0x4bc630 / 0x4bc634 = 72 / -28 has no row in symbols/globals.tsv or tables.tsv; nothing to promote
- 0x4bc62c (no row) [oracle-field]: health_fraction INCONCLUSIVE, PASS: 0x4bc62c = 0.9999 has no row in symbols/globals.tsv or tables.tsv; nothing to promote
- 0x4be1e8 (no row) [oracle-field]: damage_smoke INCONCLUSIVE, PASS: 0x4be1e8 = 0.75 (dual use) has no row in symbols/globals.tsv or tables.tsv; nothing to promote
- 0x4fe420 simclock_sim_dt [oracle-field]: step_count PASS used it but 'indistinguishable from 0x4fe428 here' (sim_dt and dt are equal on every frame): the oracle cannot tell the two names apart

## Evidence kinds and merge.py

`tools/merge.py gate_evidence_common` accepts any `kind` (it checks the pristine md5 and that a count carries a method), but `gate_g1_g2` promotes to `supported` only with >= 2 kinds from its PRIMARY/SECONDARY vocabulary and >= 1 primary. This batch uses the section 2.8 kinds `census` / `oracle` / `blind`; G2 rejects every row until `census`, `oracle` join PRIMARY and `blind` joins SECONDARY in merge.py (one-line edit), or regenerate with `gate.py --legacy-kinds`.

### --check (merge.py pure gates, in memory)

{'ACCEPT(G2)': 87}; every REJECT, then the first accepts:

    ACCEPT(G2) 0x401410 renderer_InitHorizonRing
    ACCEPT(G2) 0x40c160 ai_InitAstarNodePool
    ACCEPT(G2) 0x40cc40 ai_BuildBridgeTable
    ACCEPT(G2) 0x40f8f0 ai_ComputeTurnSpeed

## Cost (verify/journal.jsonl)

| kind | calls | USD |
|---|---|---|
| blind-judge | 1515 | 19.271 |
| blind-name | 2251 | 48.069 |
| cadence-claim | 434 | 3.225 |
| census-grade | 86 | 1.021 |
| **all** | 4286 | 71.586 |

<!-- reviewer notes: everything below this line is hand-written and kept by gate.py -->

## Reviewer reading of the 29 census FAILs (Fable, 2026-10-02; the game was not run)

Read against the claim reasons, the census views (callers, first/last frame, step histograms) and the scenario list.
None of the 29 contradicts the function's *name*; they split into three groups.

**A. Conditional per-frame, mode never entered (18): the claim enum lacks "per_frame while active", so the
cadence-claim step committed to `per_frame` and the census saw the mode absent.** The scenario list, not the map, is
what is missing here (camera-cycle, software renderer, network, AI fight with every ordnance type).
- 0x401cc0 renderer_DrawSceneSoftware: runs under Glide (`-glide`), the software path is never taken.
- 0x405b90 camera_FreeLookA, 0x4061b0 camera_FreeLookB, 0x4071a0 camera_UpdateBinoculars, 0x407680 camera_UpdateHoodView:
  camera-mode callbacks; no scenario leaves the default view.
- 0x4532c0 net_Pump, 0x4559a0 net_UpdateJoinPrompt: network game only.
- 0x40acf0 ai_TakeLosCheckTurn: caller ai_HasLostSightUnderJammer; no jammer in any scenario (melee included).
- 0x4a3560 weapon_SetTrigger: AI/network fire path; the function's batch (batch-002) had no melee run, so no AI ever
  fired. INCONCLUSIVE in spirit, FAIL by the rule.
- 0x4aa150 weapon_StepOilSlick, 0x4aa450 weapon_StepFirePatch, 0x4aa5b0 weapon_StepRocket, 0x4ab920 weapon_StepHeatMissile:
  per frame per live projectile of that ordnance; fire-each fires the t01 Piranha's weapons, which do not include these.
- 0x4a92e0 weapon_StepTumblingMine: same shape, but a mine was live: 663 calls on 74.5% of fire-each frames, 0 in drive.
- 0x4a2070 object_ChunkUpdate: per frame per live chunk (32.7% of drive frames, mean 8 calls/frame).
- 0x40a130 ai_MeleeFrameTick, 0x418200 ai_ShouldFireWeapon: per frame in melee (1/frame x 2408 frames; 5160 calls), 0 in
  the t01 scenarios that have no AI. The names say exactly this.
- 0x49a670 image_SmkUpdate: 662,973 calls before frame 658 (the pre-mission Smacker), 0 once driving: per frame while a
  video plays.
- 0x49d000 shell_RunPlayModeKeys: all calls on the one pre-start frame (counter saturated at 65535 in the `64+` bucket:
  the frame counter does not advance on the pre-start screen), 0 while driving: per frame in the non-driving modes, as
  the contract says.

**B. The cadence-claim step misread the contract (7): the observation fits the contract text, the enum did not.**
- 0x441cd0 renderer_FreeTracers, 0x444e90 renderer_FreeSkidStrips: 1 call each at melee frame 1003 from WinMain+0x1a84,
  in melee/20261002-094857 where the player was wrecked at frame 902: WinMain's *mission* teardown, which the contract's "WinMain
  teardown" covers; `init_only` was the wrong bucket. (renderer_ShutdownSmoke / ShutdownGeometryCache show the same
  call and were graded INCONCLUSIVE: the two verdicts on identical data are the model noise section 10 warns about.)
- 0x4471e0 renderer_GeometryCacheWalk: "called from WinMain 0x40398f" was read as init-time; WinMain's frame loop calls
  it once per frame (908/908, 907/907). Contract could say "per frame from WinMain".
- 0x406840 camera_ClassifyDistance: claimed `irregular` for a per-object test; observed exactly 10 calls per frame on
  99.8% of frames (10 vehicles): per_frame x objects. Consistent with the contract.
- 0x4389f0 math_MatrixRotateByAngVel: claimed per_substep from "in a contact substep"; observed 3-44 calls/frame, mode 5:
  once per *contact* per substep. Consistent with the contract; the enum cannot say "per contact".
- 0x448e40 image_BlitEltSpriteScrollY: claimed per_frame from "one step per frame"; observed 31 calls on 23 frames,
  event_corr 1.0 with 23 shots: the ammo digit scrolls one step per frame *while a digit changes*.
- 0x420d30 ai_UpdateRouteSearch: claimed per_frame from "update function run by ai_SetBehaviour"; observed 9 calls per
  run, bursty, melee event_corr 1.0: the route search is on demand, the per-frame part is in the caller.

**C. Genuine contract errors to fix (2): the contract's own cadence text is contradicted, not just the enum.**
- 0x43d070 physics_SnapToGround: contract says "once per frame from entity_TickVehicle"; observed 3 calls, all before
  frame 183 (spawn settle), then 0 in 908 + 905 live frames. The call is conditional (likely a settle flag); the
  contract sentence is wrong. physics_ResolveGroundContact's census shows the same 3 SnapToGround-sourced calls.
- 0x461570 entity_GetRadarArcContact: claimed per_event(shot) from "weapon_FireShot calls arc contact"; observed 23-33
  calls per frame on every frame, 33,649 in drive with 0 shots, caller weapon_UpdateTurretsAndLocks (34,109 calls vs 9
  from weapon_FireShot in fire-each). The contract names the minor caller; the turret/lock update is the main one.
- 0x41ef40 ai_UpdateFollow sits between B and C: observed only in the first frames (init_only in drive/fire-each, 0 in
  melee); follow behaviour 30 runs only while an AI follows a leader. The contract is right about *what*; "per frame"
  holds only while the behaviour is active, which the t01 convoy leaves after the start.

**Program notes from this pass.** (1) `per_frame -> never` should be FAIL only when a scenario entered the mode; the
rule needs a precondition, or the cadence enum a `per_frame_conditional` value that is graded like per_event
(scenario must exercise the trigger). 18 of 29 FAILs disappear under that rule. (2) Haiku graded 24 FAIL; Sonnet kept
16, flipped 6 to INCONCLUSIVE and 2 to PASS: the blind step's "Sonnet re-judge of every small-model negative" rule
should be standard for census-grade too (gate.py already prefers the `.sonnet` result). (3) The census-grade prompt's
scenario list does not describe `melee`; the model inferred it from the event counts. (4) merge.py has no vocabulary
for census / oracle / blind evidence: see "Evidence kinds and merge.py" above.

## Reviewer reading of the 2026-10-03c pass (Fable, 2026-10-03; the game was not run)

Inputs changed since 03b: the jump / radar-lock / camera-cycle never-passes (12 runs, `runs/never-fire.json`: 130 of 880 silent
functions now have a class) and `gate.py --summary runs/phase1-all-summary.json` (70 runs: entity + early-attach + never-pass).
Census-grade: 10 units had new inputs (the never-pass runs hooked them), Haiku 9 FAIL / 1 INCONCLUSIVE, Sonnet re-grade 6 FAIL /
3 INCONCLUSIVE; 28 model units were unchanged and keep their 03b grades; 35 script grades were re-derived on the new runs.

**Census FAILs: 31 (was 29), still 0 name contradictions.**
- The four camera callbacks (FreeLookA/B, UpdateBinoculars, UpdateHoodView) moved from script `per_frame -> never` to Sonnet FAIL
  on camera-cycle data: 298 / 87 / 69 calls on exactly that many frames (FreeLookB 16.5% of the run), i.e. once per frame *while
  that view is active*; FreeLookA fires only in `jump` (141 frames). Group A of the 03b reading (per_frame while active); the enum
  still lacks the value.
- New: entity_StartTractionLoss and entity_HazardHitNearestWheel, per_event(impact) -> never. Sonnet counted the telemetry
  `impact` events (82 radar-lock, 62 jump), but the claims name a *specific* impact (oil-slick ordnance hitting a car; a class 0x33
  handgun bullet). weapon_StepOilSlick itself has 0 calls in every scenario and no AI fired a handgun at the player, so the trigger
  was never exercised: INCONCLUSIVE in spirit, FAIL by the prompt's reading of `impact`. The census-grade prompt should say that
  `impact` in events.csv is any collision, not the claim's named projectile.
- physics_RebuildCollision, weapon_ApplyFlameDamage (Haiku FAIL -> Sonnet INCONCLUSIVE, trigger absent) and renderer_FreeDrawBuffers
  (1 call from WinMain at radar-lock frame 1686: the mission teardown, same shape as FreeTracers / FreeSkidStrips) are not disputes.

**39 promotions, all census + one blind reading (36 reader 1, 3 reader 2): 18 rest on a never-pass class (camera-cycle /
radar-lock / jump: per_event or per_frame while the mode is active) and 21 on an `init_only` record that exists only in the
early-attach pass (mission-idle / menu-idle), which earlier gates did not read (phase1-summary.json was the entity pass).** Both
are the program's intended use of those passes, but the 21 are a new evidence source; listed per row above (`fires only in the
early-attach pass` in `queue/TODO-blind-census-pass.txt` marks the same condition for the unpromoted rows).

**Program notes.** (1) `grade_census.py` compared `meta.inputs_md5` of worker results, which carry none, so every model unit rotated
on each run; it now falls back to the unit file's stamp (28 spurious rotations undone from git). (2) It now rotates
`<addr>.sonnet.result.json` with the canonical result, otherwise a stale Sonnet verdict outranks the fresh grade in gate.py
(object_DetachAsChunk: Sonnet INCONCLUSIVE on 03b inputs, script PASS now that `jump` shows per_event). (3) The 34 `init_only`
INCONCLUSIVEs (27 early-attach + others) could now be graded against the mission-idle runs, but grade_census.py reads
`attach_after_entity` runs only; left as is. (4) The `per_event(key)` INCONCLUSIVE rule ("no phase-1 scenario produces that
event") predates camera-cycle / radar-lock, which do press keys; the rows it still covers had 0 calls there. (5) The "promoted rows
had another conv" line used to list every proposed row with a conv; fixed to the batch rows (0 of 39 have one).
(6) `queue/TODO-blind-census-pass.txt`: 508 proposed rows with census PASS and no judged blind result: 182 never read, 321 read once
and blank (INCONCLUSIVE), 5 read with a name but never judged; 194 of the 508 have only an early-attach `init_only` record.
