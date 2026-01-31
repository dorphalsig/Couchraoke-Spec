# F15 — Session lifecycle: hello/assignSinger + reconnect reclaim

Purpose (Appendix F):
- verify reconnect reclaim via stable clientId (Section 7.4; hello in Section 8.2)
- verify role resumption: during an in-progress song, reconnect triggers assignSinger re-send (Section 8.2)
- verify rejection behavior when session is full and cannot match a reconnecting clientId (Section 7.1–7.4)

Notes:
- Disconnect is represented here as an out-of-band transcript event (`eventType: "disconnect"`) since socket close is not an explicit protocol message.
- Kick is represented here as an out-of-band transcript event (`eventType: "kick"`) and corresponds to the TV "Kick device" action (Section 10.4).

Cases (preferred):
- `case_reconnect_reclaim/` — reconnect reclaim + assignSinger resend; third device is rejected while roster is full.
- `case_slot_taken/` — device disconnects, TV kicks it (roster removed), a new device takes the freed slot, and the original clientId is rejected.

Legacy (kept for backward compatibility):
- `transcript.jsonl`
- `expected.outcome.json`
