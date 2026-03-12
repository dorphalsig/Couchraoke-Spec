# Constitution Merge Design

## 1. Unified `constitution.md`
We will create a deeply-merged `constitution.md` with standard numerical headers (1, 2, 3...) combining the rules from `android_constitution.md` and `tv_constitution.md`.
- Shared rules (Testing, Architecture, Code Quality) will be grouped.
- Platform-specific rules (TV playback engine, Phone audio capture) will be explicitly placed in subsections.

## 2. Separate Routing CSV
Instead of prefixing headers to avoid collisions with `couchraoke_spec.md`, we will create a dedicated `constitution_split_plan.csv` to map the numerical sections of `constitution.md` to their target platforms.

## 3. `split_spec.py` Modifications
The `split_spec.py` script will be generalized to handle any markdown file with an accompanying CSV:
- **CLI Arguments**: It will take `<source_file>`, `<csv_file>`, and `<target_prefix>`.
  - Example: `python3 split_spec.py couchraoke_spec.md split_plan.csv spec` -> produces `spec_tv.md`, `spec_android.md`, etc.
  - Example: `python3 split_spec.py constitution.md constitution_split_plan.csv constitution` -> produces `constitution_tv.md`, `constitution_android.md`, etc.
- **Remove Hardcoded Edge Cases**: The hardcoded "Section 9 blanket rule" will be removed from the python script.
- **Update Existing CSV**: The existing `split_plan.csv` will be updated to explicitly route Section 9 and its sub-sections to `tv` to maintain current behavior.