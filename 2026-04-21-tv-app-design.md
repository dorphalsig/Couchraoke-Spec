# TV App UI Design Spec

## 1. Scope

This document defines the visual system, sizing tokens, screen composition, and screen-level VFX budget for the TV app.

This spec preserves the existing screen purposes, route structure, and major wireframe block placement from `tv_app.md`. The changes in this document are limited to visual system, scale, spacing, readability, emphasis, and per-screen presentation.

## 2. Design Intent

The app uses a dark concert-like presentation with competitive karaoke HUD structure. The visual language prioritizes:

1. gameplay readability during singing
2. stable remote navigation and focus clarity
3. song recognition from the browse grid
4. restrained motion that does not compete with scoring, playback, or video decode

The singing screen is designed for video backgrounds as the default case. The overlay system must remain fully readable over moving footage.

## 3. Hard Constraints

### 3.1 Performance hierarchy

1. gameplay correctness and smoothness
2. readability and input response
3. decorative motion

If a treatment risks singing stability, preview responsiveness, or focus reliability, the treatment is not permitted.

### 3.2 Allowed rendering style

The app uses flat rendering only.

The following treatments are not permitted:
- runtime blur
- bloom
- glow
- frosted glass
- shader-heavy full-screen effects
- particle systems during gameplay
- background animation that repaints large parts of the screen during active singing

### 3.3 Wireframe preservation rule

The existing screen structures remain in place unless a future revision explicitly changes product structure.

This spec changes:
- proportions
- spacing
- sizing
- typography
- emphasis
- component presentation
- motion policy

This spec does not change:
- route order
- major screen purpose
- core focus model
- major block placement across screens

## 4. Foundation Tokens

### 4.1 Spacing

| Token | Value |
|---|---:|
| Space8 | 8dp |
| Space12 | 12dp |
| Space16 | 16dp |
| Space24 | 24dp |
| Space32 | 32dp |
| Space48 | 48dp |

### 4.2 Radius

| Token | Value |
|---|---:|
| RadiusSmall | 8dp |
| RadiusMedium | 12dp |
| RadiusLarge | 16dp |

### 4.3 Border and focus

| Token | Value |
|---|---:|
| BorderThin | 1dp |
| FocusBorderWidth | 3dp |
| FocusBorderInset | 2dp |
| UnfocusedBorderOpacity | 20% |
| FocusInDuration | 150ms |
| FocusOutDuration | 100ms |

### 4.4 Layout

| Token | Value |
|---|---:|
| AppMarginHorizontal | 48dp |
| AppMarginVertical | 36dp |
| HeaderHeight | 76dp |
| StandardButtonHeight | 72dp |
| StandardRowHeight | 76dp |
| DenseRowHeight | 56dp |
| PrimaryModalWidth | 960dp |
| PrimaryModalPadding | 32dp |
| QRCodeSize | 400dp |

### 4.5 Typography

#### Display face

Use the decorative squared face only for the following tokens.

| Token | Value |
|---|---:|
| DisplayHeroNumber | 160sp |
| DisplayHeroTitle | 56sp |
| DisplayAccentTitle | 44sp |

#### Operational sans

Use the operational sans for all other text.

| Token | Value |
|---|---:|
| ScreenTitle | 40sp |
| SectionTitle | 32sp |
| PanelTitle | 28sp |
| SongCardTitle | 24sp |
| SongCardArtistFocused | 18sp |
| PreviewTitle | 32sp |
| PreviewArtist | 24sp |
| TagChipLabel | 16sp |
| BodyPrimary | 24sp |
| BodySecondary | 20sp |
| ButtonLabel | 22sp |
| FieldLabel | 20sp |
| Caption | 18sp |
| LyricsCurrent | 40sp |
| LyricsNext | 32sp |
| LiveScore | 56sp |
| SentenceRating | 28sp |
| TopMetadataMinimal | 20sp |
| SingerBadge | 22sp |
| Timer | 24sp |
| ResultBreakdownLabel | 22sp |
| ResultBreakdownValue | 28sp |
| ResultTotalValue | 64sp |
| MedleyRowText | 22sp |
| MedleyTotalValue | 48sp |

## 5. Color and Surface System

### 5.1 Semantic colors

| Role | Use |
|---|---|
| AppBackground | darkest cool graphite base |
| SurfacePrimary | standard dark surface |
| SurfaceElevated | elevated modal and overlay surface |
| SurfaceLaneBand | dark translucent graphite lane plate |
| SurfaceLyricsBand | darkest overlay plate on singing screen |
| BorderSubtle | unfocused structure border |
| BorderFocus | focused border |
| TextPrimary | highest-priority text |
| TextSecondary | secondary metadata |
| TextDisabled | disabled state |
| Player1Accent | cyan |
| Player2Accent | magenta |
| RewardAccent | gold |
| Success | success state |
| Warning | warning state |
| Error | error state |

### 5.2 Usage rules

- Player identity uses cyan for P1 and magenta for P2.
- Gold is reserved for reward treatment only.
- Focus uses `BorderFocus`, not cyan, magenta, or gold.
- Lane bodies remain neutral. Player color appears in accents only.

### 5.3 Surface levels

| Token | Use |
|---|---|
| SurfaceLevel0 | app background |
| SurfaceLevel1 | standard cards, rows, and panels |
| SurfaceLevel2 | modal, pause, disconnect, error, and similar interruption surfaces |
| LaneBandAlpha | 68% |
| LyricsBandAlpha | 82% |

## 6. Global Interaction Rules

### 6.1 Focus presentation

Focused components use:
- `FocusBorderWidth`
- `BorderFocus`
- `FocusBorderInset`
- a subtle filled plate on the component body

Unfocused enabled components use:
- `BorderThin`
- `BorderSubtle` at `UnfocusedBorderOpacity`

Focus does not use:
- scale-up
- shadow growth
- blur
- background pulse
- glow

### 6.2 Motion language

- use short directional motion for structural transitions
- use fades for overlays and interruption states
- do not use looping decorative motion as a default screen treatment
- do not animate layout during singing except where the current product state already changes layout

## 7. Scale Tiers

### 7.1 Oversized tier

Use for:
- singing
- countdown
- interruption states
- hero result values

### 7.2 Balanced tier

Use for:
- select players
- join and QR
- settings
- preview metadata on song list

### 7.3 Compact-balanced tier

Use only for:
- song list grid cards

## 8. Screen VFX Budget

### 8.1 Budget scale

| Level | Meaning |
|---|---|
| V0 | static only |
| V1 | one local motion zone |
| V2 | one hero motion or two local motions |
| V3 | not allowed |

### 8.2 Budget by screen

| Screen | Budget | Allowed pattern |
|---|---|---|
| Song List, settled | V2 | local polish only |
| Song List, active navigation | V1 | focus and state motion only |
| Join / QR | V1 | modal entrance, then static |
| Select Players | V1 | focus and short row transitions |
| Settings | V2 | local control motion only |
| Loading / pre-song setup | V0 | static poster or simple progress only |
| Countdown | V2 | one hero number animation |
| Singing | V0 | functional motion only |
| Pause / Disconnect / Error | V1 | modal entrance and focus only |
| Medley segment transition | V0 | text swap only |
| Single-song Results | V2 | one entry payoff, then static |
| Medley Results | V1 | calm table reveal, then static |

## 9. Song List

### 9.1 Layout

The Song List preserves the two-column layout from `tv_app.md`.

- left rail: preview and medley workspace
- right body: search, random actions, song grid

#### Proportions

| Token | Value |
|---|---:|
| SongListLeftRailFraction | 0.34 |
| SongListGridFraction | 0.66 |
| SongListRailGridGap | 32dp |
| SongListHeaderToBodyGap | 24dp |
| SongListRandomRowHeight | 72dp |
| SongListRandomRowGap | 24dp |
| SongListGridColumns1080 | 3 |
| SongListGridColumns4K | 4 |
| SongListGridColumnGap | 24dp |
| SongListGridRowGap | 24dp |

### 9.2 Header

Header composition remains:
- Search field
- Join button
- Settings button

Header rules:
- Search is the visually strongest control.
- Join and Settings are equal secondary controls.
- Header uses `HeaderHeight`.
- Header text uses operational sans only.

### 9.3 Left rail

The left rail remains split between preview and medley.

#### Left rail tokens

| Token | Value |
|---|---:|
| SongListPreviewAspect | 16:9 |
| SongListPreviewToMetaGap | 16dp |
| SongListMetaToPlaylistGap | 24dp |
| SongListPlaylistRowHeight | 52dp |
| SongListPlaylistVisibleRows | 5 |
| SongListPlayMedleyTopGap | 16dp |

#### Left rail rules

- Preview is display-only and non-focusable.
- Focused-song preview metadata always shows full title and artist.
- The medley playlist occupies the lower half of the rail.
- `Play Medley` sits directly below the playlist.
- `Random Medley` remains in the random actions row, not in the left rail.

### 9.4 Random actions row

The random row contains:
- Random Song
- Random Duet
- Random Medley

All three use equal visual weight.

### 9.5 Song cards

Cards are image-led with fixed metadata behavior.

#### Card tokens

| Token | Value |
|---|---:|
| SongCardHeight | 252dp |
| SongCardPadding | 12dp |
| SongCardImageHeight | 148dp |
| SongCardImageCornerRadius | 8dp |
| SongCardTitleMaxLines | 2 |
| SongCardFocusedArtistSlotHeight | 20dp |
| SongCardTitleToArtistGap | 4dp |
| SongCardTagCornerInset | 8dp |
| SongCardTagGap | 6dp |
| SongCardMaxVisibleTags | 3 |

#### Card content rules

Default state shows:
- cover image
- title
- up to three tag chips

Focused state additionally shows:
- one artist line in the reserved artist slot

Artist reveal must not reflow the card.

#### Tag placement and priority

- Tag chips are rendered on-image in the lower-right corner.
- Maximum visible chips: 3.
- Priority order: `D`, `M`, `R`, `I`, `V`.
- When more than three tags apply, the lower-priority chips are omitted.
- `V` is always the first chip omitted.

#### Fallback for weak artwork

If a song has missing art, placeholder art, or unusable art:
- keep title primary
- keep tag chips visible
- show artist in the default state for that card

### 9.6 Motion and focus behavior on Song List

- Settled state uses local preview crossfade and restrained chip or border fade.
- Active navigation uses focus transition only.
- No per-card ambient animation.
- No animated background treatment behind the grid.
- No card scale on focus.

## 10. Select Players

### 10.1 Layout

The Select Players modal preserves the existing structure.

| Token | Value |
|---|---:|
| SelectPlayersPanelWidth | 960dp |
| SelectPlayersSectionGap | 32dp |
| SelectPlayersFieldRowHeight | 76dp |
| SelectPlayersActionRowGap | 24dp |

### 10.2 Visual rules

- Use balanced tier sizing.
- Use operational sans only.
- Emphasize `Start` through placement, size, and surface contrast.
- Do not use gold on `Start`.
- Do not animate background posters or modal backdrops beyond the initial modal entrance.

### 10.3 State-specific presentation

#### Non-duet
- Player 1 block is active and visually primary.
- Player 2 block remains visible but disabled.

#### Duet
- Two player blocks remain symmetric.
- `Swap Parts` is secondary to `Start`.

#### Medley
- Single-flow version only.
- No Player 2 section.
- Subtitle remains `Medley — <n> songs`.

## 11. Join and QR Overlay

### 11.1 Layout

The join overlay preserves the current QR-first structure.

| Token | Value |
|---|---:|
| JoinPanelWidth | 960dp |
| JoinQRCodeSize | 400dp |
| JoinCodeTopGap | 16dp |
| JoinConnectedRowHeight | 56dp |

### 11.2 Visual rules

- QR is the dominant object.
- Join code sits directly below the QR.
- QR remains static.
- No animation may overlap the QR or its quiet zone.
- Entrance animation is a short fade or scale-fade of the modal shell only.

## 12. Settings

### 12.1 Layout

The Settings area preserves the list-first structure from `tv_app.md`.

| Token | Value |
|---|---:|
| SettingsListWidth | 960dp |
| SettingsRowHeight | 76dp |
| SettingsRowGap | 8dp |
| SettingsSectionTopGap | 24dp |

### 12.2 Visual rules

- Use balanced tier sizing.
- Use operational sans only.
- Use broad, readable rows.
- Reuse the same surface, focus, and spacing system as the rest of the app.
- Do not introduce screen-specific decorative treatments.

## 13. Singing

### 13.1 Overall layout

The singing screen preserves the existing high-level structure.

- top metadata strip
- lane region
- full-width bottom lyrics band

### 13.2 Layout tokens

#### Global

| Token | Value |
|---|---:|
| SingingTopIntroStripHeight | 72dp |
| SingingTopMinimalStripHeight | 40dp |
| SingingBottomLyricsBandHeight | 160dp |
| SingingBodyToLyricsGap | 16dp |

#### Single-singer state

| Token | Value |
|---|---:|
| SingingSingleLaneHeight | 192dp |
| SingingSingleLaneVerticalPosition | centered |

#### Two-singer state

| Token | Value |
|---|---:|
| SingingDualLaneHeight | 144dp |
| SingingDualLaneGap | 24dp |

#### Lane internals

| Token | Value |
|---|---:|
| SingingLaneHorizontalPadding | 20dp |
| SingingLaneVerticalPadding | 16dp |
| SingingScoreBoxWidth | 144dp |
| SingingScoreBoxHeight | 88dp |
| SingingScoreBoxRightInset | 16dp |
| SingingScoreBoxToRatingGap | 8dp |
| SingingBadgeHeight | 40dp |
| SingingBadgeTopInset | 8dp |

#### Lyrics band

| Token | Value |
|---|---:|
| LyricsBandPaddingHorizontal | 24dp |
| LyricsBandPaddingTop | 20dp |
| LyricsBandLineGap | 8dp |

### 13.3 Singing state rules

#### Top metadata

- On song start and medley segment change, render the top metadata in the intro strip.
- During active singing, collapse metadata to the minimal strip.
- In medley, render the minimal strip as `<i>/<n>: <Artist> — <Title>`.

#### Lane configuration

- Single-singer song: exactly one centered lane band.
- Two-singer song: exactly two stacked lane bands.
- Lane bands are long horizontal plates with `RadiusMedium` corners.
- Lane fill uses `SurfaceLaneBand` with `LaneBandAlpha`.
- Lane bodies remain neutral.
- P1 uses cyan accents.
- P2 uses magenta accents.
- Do not tint the full lane body with player color.

#### Score and sentence rating

- Each lane has exactly one score box anchored on the right edge.
- Sentence rating is rendered directly under the score box.
- Score text uses `LiveScore`.
- Sentence rating uses `SentenceRating`.

#### Lyrics

- Render lyrics in the bottom band only.
- Bottom band uses `SurfaceLyricsBand` with `LyricsBandAlpha`.
- The band always shows exactly two lines.
- Current line uses `LyricsCurrent`.
- Next line uses `LyricsNext`.
- Current line is stronger in contrast and emphasis.
- Next line is muted.
- Do not render a third line.
- Do not continuously scroll lyric lines.

#### Timer

- Render elapsed time at bottom-right using `Timer`.
- Use `MM:SS` formatting.

### 13.4 Singing motion budget

Allowed during active singing:
- lyric highlight progression
- sentence rating fade
- score update pulse of minimal amplitude
- note lane rendering already required by gameplay

Not allowed during active singing:
- background animation over video
- blur or bloom transitions on lyric change
- multi-panel HUD entrance sequences
- particle feedback on notes or line completion
- full-lane pulses

## 14. Countdown

### 14.1 Layout

Countdown remains a full-screen overlay.

- numeral uses `DisplayHeroNumber`
- numeral is centered
- background remains dimmed and static

### 14.2 Motion

- only the numeral animates
- use one scale-pop per count
- do not add secondary full-screen pulses

## 15. Pause, Disconnect, Confirm, and Error Overlays

### 15.1 Shared shell

All interruption overlays reuse the same centered elevated shell.

| Token | Value |
|---|---:|
| InterruptionModalWidth | 960dp |
| InterruptionModalTitleBottomGap | 16dp |
| InterruptionModalBodyBottomGap | 24dp |
| InterruptionActionRowHeight | 72dp |

### 15.2 Visual rules

- use `SurfaceLevel2`
- use a dark scrim over the underlying scene
- no blurred frozen background
- no large entrance sequences
- use operational sans only

### 15.3 Motion

- one short modal entrance fade or scale-fade
- focus movement only after entry
- when reconnect is in progress, show one small reconnect spinner on the disconnect pause modal only

## 16. Results

### 16.1 Single-song Results

The single-song Results screen preserves the existing two-column comparison structure.

#### Layout tokens

| Token | Value |
|---|---:|
| ResultsHeaderBottomGap | 24dp |
| ResultsPlayerColumnGap | 32dp |
| ResultsPlayerCardPadding | 24dp |
| ResultsBreakdownRowHeight | 44dp |
| ResultsBreakdownRowGap | 12dp |
| ResultsTotalTopGap | 24dp |
| ResultsBackButtonTopGap | 32dp |

#### Presentation

- Header shows screen title and song title line.
- Each player column shows Notes, Golden, Line Bonus, and Song Total.
- Breakdown labels use `ResultBreakdownLabel`.
- Breakdown values use `ResultBreakdownValue`.
- Song Total uses `ResultTotalValue`.
- Winner emphasis uses gold on the winning player marker when one player has the higher Song Total. Ties use no gold winner marker.
- The `Back to Song List` action sits below the results board.

#### Motion

- one entry payoff sequence
- one count-up sequence
- one winner emphasis pass when the result is not a tie
- then fully static

### 16.2 Medley Results

The medley Results screen preserves the static table structure from `tv_app.md`.

#### Layout tokens

| Token | Value |
|---|---:|
| MedleyResultsTableRowHeight | 64dp |
| MedleyResultsTableRowGap | 0dp |
| MedleyResultsTotalRowHeight | 80dp |
| MedleyResultsTotalTopGap | 16dp |
| MedleyResultsBackButtonTopGap | 32dp |

#### Presentation

- Render the table as informational and non-focusable.
- Render the Back to Song List button as the only focusable control.
- Use `MedleyRowText` for normal rows.
- Use `MedleyTotalValue` for Medley Total values.
- Use operational sans only.
- Use row spacing, row weight, and the taller total row to emphasize the Medley Total.
- Do not use gold on the Medley Total row.
- Do not use the decorative display face on the Medley Total row.

#### Motion

- use one 180ms opacity fade on entry
- no celebratory background treatment
- no continuous animation after entry

## 17. Loading and Transition States

### 17.1 Loading / pre-song setup

- static poster or album art is allowed
- one simple spinner or progress pulse is allowed
- no full-screen wipes
- no cinematic transitions

### 17.2 Medley segment transition

- rely on audio crossfade as the primary perceptual transition
- visual transition is limited to text or badge swap
- no full-screen overlay transition

### 17.3 Return from Results to Song List

- use a short crossfade only
- do not animate card cascade or grid rebuild

## 18. Component Definitions

### 18.1 Button variants

- Primary
- Secondary
- Quiet
- Destructive

Usage:
- Primary: local main action for the current surface
- Secondary: peer action with lower emphasis
- Quiet: utility action
- Destructive: quit, delete, or similar destructive actions only

### 18.2 Tag chip definitions

| Chip | Meaning |
|---|---|
| D | duet |
| M | medley |
| R | rap |
| I | instrumental |
| V | video |

### 18.3 Player accent usage

Use player accent color on:
- singer badge
- score box accents
- lane markers and cursor accents
- focused identity cues where player ownership matters

Do not use player accent color for:
- generic focus border
- general app chrome
- default button system

## 19. Acceptance Criteria for Design Conformance

A build conforms to this design spec when:

1. all typography uses the token values in this document
2. all sizes use fixed dp/sp values or explicit proportions in this document
3. song list preserves existing block placement while applying the card, rail, and action rules in this document
4. singing uses the fixed one-lane or two-lane states defined here
5. lyrics remain bottom-banded and two-line only
6. medley total uses the medley table treatment in this document
7. no prohibited glow, blur, bloom, or particle effects appear
8. no gameplay-adjacent decorative effect can interfere with singing smoothness

## 20. Non-Goals

This document does not define:
- implementation classes or Compose structure
- code architecture changes outside UI presentation
- protocol changes
- scoring algorithm changes
- flow changes beyond the preserved screen structures from `tv_app.md`
