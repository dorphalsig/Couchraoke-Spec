# Section Migration Mapping

| Section | Platform Scope / Destination Docs | Relevant Fixtures (manifest `covers`) |
| --- | --- | --- |
| 1.1 Locked Product Decisions | All specs (context duplicated) | None |
| 1.2 Definition of Done | All specs | None |
| 2.1 Components | All specs | F18_http_server_range_coordination (§8.6), F15_session_lifecycle_disconnect_reconnect (§8.1/7.4) |
| 2.2 Data Responsibilities | All specs | F18_http_server_range_coordination (§8.6), F15_session_lifecycle_disconnect_reconnect (§8.1/7.4) |
| 3.1 Storage Access | Android companion (SAF details), iOS companion (bookmark details), TV host (aggregator summary) | F01_song_discovery_validation_acceptance (1.1/1.4), F02_header_parsing_edge_cases (1.2) |
| 3.2 Discovery and Validation Rules | All specs | F01_song_discovery_validation_acceptance (1.1/1.4), F02_header_parsing_edge_cases (1.2), F04_duet_parsing_track_routing (1.3) |
| 3.3 Index Fields (Functional) | All specs (TV emphasized) | F01_song_discovery_validation_acceptance (1.1/1.4), F04_duet_parsing_track_routing (2.3), F16_medley_sequencer (12.1–12.4) |
| 3.4 Song List (Landing Screen) | TV host spec only | No direct fixtures |
| 3.5 Advanced Search (Overlay) | All specs (shared future scope) | None |
| 4.1 Supported Note Tokens | All specs | F03_body_grammar_token_recognition (2.1/2.2/4.4), F04_duet_parsing_track_routing (2.3) |
| 4.2 Supported Header Tags and Semantics | All specs | F02_header_parsing_edge_cases (1.2), F01_song_discovery_validation_acceptance (1.1/1.4) |
| 4.3 Error Handling | All specs | F02_header_parsing_edge_cases (1.2), F03_body_grammar_token_recognition (2.1/2.2/4.4), F04_duet_parsing_track_routing (2.3) |
| 4.4 Header Tags Reference | All specs | F02_header_parsing_edge_cases, F03_body_grammar_token_recognition, F04_duet_parsing_track_routing |
| 4.5 Body Token Reference | All specs | F03_body_grammar_token_recognition |
| 5.1 Authoritative Beat Definitions | All specs | F06_beat_time_conversion_static_bpm (3.1) |
| 5.2 Pitch Frame Timing, Jitter, Mic Delay | All specs (TV consumes, phones produce) | F13_jitter_buffer_selection_staleness (6.1–6.7), F14v2_clock_sync_phone_side (7.1–7.3) |
| 5.2.5 Mic Capture + FFT-YIN Pipeline | Android + iOS companion specs | F17_yin_dsp_pipeline_accuracy (5.2.5.2) |
| 5.3 Beat-Time Conversion | All specs | F06_beat_time_conversion_static_bpm (3.1) |
| 5.4 START/END | All specs | None |
| 6.1 Scoring Overview | TV host spec primary, shared background in companions | F08_scoring_beat_stepping_interval_semantics (4.1), F09_pitch_tolerance_octave_normalization (4.2) |
| 6.2 Note Types | TV host spec | F03_body_grammar_token_recognition (4.4), F09_pitch_tolerance_octave_normalization (4.2) |
| 6.2.1 ScoreFactor constants | TV host spec | F11_line_bonus_and_rounding (4.5) |
| 6.3 Player Level / Tolerance | TV host spec | F09_pitch_tolerance_octave_normalization (4.2) |
| 6.4 Octave Normalization | TV host spec | F09_pitch_tolerance_octave_normalization (4.2) |
| 6.5 Line Bonus | TV host spec | F11_line_bonus_and_rounding (4.5), F16_medley_sequencer (12.1–12.4) |
| 6.6 Rounding and Display | TV host spec | F11_line_bonus_and_rounding (4.5) |
| 7.1 Session States | All specs | F15_session_lifecycle_disconnect_reconnect (8.1–8.4) |
| 7.2 Pairing UX (TV) | TV host spec | None |
| 7.3 Pairing UX (Phone) | Android + iOS companion specs | None |
| 7.4 Disconnect/Reconnect | All specs | F15_session_lifecycle_disconnect_reconnect (8.1–8.4) |
| 8.1 Transport | All specs | F18_http_server_range_coordination (8.6), F14v2_clock_sync_phone_side (7.1–7.3) |
| 8.2 Control Messages | All specs | F15_session_lifecycle_disconnect_reconnect (8.1–8.4), F18_http_server_range_coordination (8.6) |
| 8.3 Pitch Stream Messages | All specs (TV consumes, phones send) | F12v2_binary_pitch_codec (5.1/5.2) |
| 8.4 Versioning and Compatibility | All specs | None |
| 8.5 Sender Identification | All specs | F15_session_lifecycle_disconnect_reconnect (8.1–8.4) |
| 8.6 Song File HTTP Server | All specs (TV consumes; phones host) | F18_http_server_range_coordination (8.6), F19_icloud_eviction_handling (8.6) |
| 8.7 Time Sync and Jitter Handling | All specs | F14v2_clock_sync_phone_side (7.1–7.3), F13_jitter_buffer_selection_staleness (6.x) |
| 9.1 Global navigation and input | TV host spec | None |
| 9.2 Song preview playback | TV host spec | None |
| 9.3 Select Players modal | TV host spec | None |
| 9.4 Settings Screen (9.4.1–9.4.6) | TV host spec | None |
| 9.5 Singing Screen (+ 9.5.1 Medley) | TV host spec | F16_medley_sequencer (12.1–12.4), F11_line_bonus_and_rounding (4.5) |
| 9.6 Results (post-song / medley) | TV host spec | F16_medley_sequencer (12.1–12.4) |
| Appendix A (dependencies) | Split per platform section; shared prohibited patterns | None |
| Appendix B Protocol Schemas | All specs (duplicate) | F12v2 (pitchFrame), F15 (session messages), F18 (requestSongList/http) |
| Appendix C Parsed Song Model | TV host spec (phones reference link) | F01, F02, F03, F04 |
| Appendix D Fixture Policy + Schemas | All specs | None |
| Appendix E Worked Examples | TV host spec (phones reference) | F06, F08, F11 references as contextual |
