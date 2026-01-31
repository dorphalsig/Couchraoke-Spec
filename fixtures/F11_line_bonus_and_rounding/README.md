# F11 — Line bonus + rounding (perfect performance)

Derived from Appendix E.4.

Purpose:
- validate MaxSongPoints=9000 / LineBonusPool=1000 split (Section 6.5)
- validate line perfection and distribution across two non-empty lines
- validate rounding rules to tens, and that totals do not exceed 10000 (Section 6.6)

Expected perfect performance results:
- Normal line (beats 0..3) yields 3000 points total (750 per beat)
- Golden line (beats 4..7) yields 6000 points total (1500 per beat)
- Line bonus yields 1000 total
- Total displayed score = 10000
