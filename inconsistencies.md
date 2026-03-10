# Spec Inconsistencies and Gaps

During the spec splitting process, the following minor gaps or potential inconsistencies were noted:

1. **Results Section Placholders:**
   - The master spec referenced a post-song flow and medley results flow. These were initially missing or marked as placeholders in the new spec, but were subsequently populated from the original text.

2. **Cross-Platform Muting Behavior:**
   - The companion specs indicate that "when enabled, the phone MUST continue to stay connected but MUST stream frames as unvoiced (equivalent to `toneValid=false` and `midiNote=255`) so the TV scores silence." This behavior is consistent, but it relies on the TV trusting the phone's muted state without a distinct control message indicating "muted", meaning the TV can't render a "Player Muted" icon.
   - *Resolution proposed:* Add a `muted` boolean to `pitchFrame` or use a separate control message in a future protocol version if a UI indicator is desired.

3. **Background HTTP Server on iOS:**
   - The spec notes a known limitation: "iOS may suspend the process after approximately 30 seconds... users must keep the phone app in the foreground during a song."
   - *Resolution proposed:* Consider documenting this heavily in user-facing onboarding, or investigating if iOS "Audio" background mode could be legitimately claimed given the microphone usage, which might keep the app alive longer.

No other major contradictions were found that would block MVP implementation.