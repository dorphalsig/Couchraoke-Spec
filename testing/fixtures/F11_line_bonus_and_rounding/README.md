# F11 — Line bonus + rounding (perfect performance)

**Purpose** (§2.2 T6.5 / T6.6):
- Validate MaxSongPoints=9000 / LineBonusPool=1000 split
- Validate line perfection and distribution across two non-empty lines
- Validate rounding rules to tens, totals ≤ 10000

**Expected perfect performance**:
- Normal line (beats 0..3): 3000 points (750/beat)
- Golden line (beats 4..7): 6000 points (1500/beat)
- Line bonus: 1000
- Total: 10000

**Medley aggregation** (§2.6.17):
- `medley_segments.json` defines per-segment score breakdowns
- `expected.medley_total.json` asserts TOTAL fields: `TOTAL.field = round(sum(segment.field) / nSegments)`
- Expected `scoreTotalInt` (9987) demonstrates medley TOTAL is not tens-rounded
