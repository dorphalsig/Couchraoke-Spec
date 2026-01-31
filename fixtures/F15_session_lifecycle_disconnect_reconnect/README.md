# F15 — Session lifecycle: hello/assignSinger + reconnect reclaim

Purpose (Appendix F):
- verify reconnect reclaim via stable clientId (Section 7.4; hello in Section 8.2)
- verify role resumption: during an in-progress song, reconnect triggers assignSinger re-send (Section 8.2)
- verify rejection behavior when session is full and cannot match a reconnecting clientId (Section 7.1–7.4)

Notes:
- Disconnect is represented here as an out-of-band transcript event (`type: "disconnect"`) since socket close is not an explicit protocol message.

Files:
- transcript.jsonl
- expected.outcome.json
