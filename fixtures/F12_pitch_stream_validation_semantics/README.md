# F12 — Pitch stream validation semantics

Purpose: verify receiver-side validation rules from Section 8.3:
- drop frames with decreasing seq
- drop frames with tCaptureMs regressions > 200 ms
- accept toneValid=false with midiNote=null (silence/unvoiced)

Files:
- pitchFrames.jsonl
- expected.validation.json
