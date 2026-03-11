#!/usr/bin/env python3
"""Split couchraoke_spec.md into platform-specific files.

Usage:
    python3 split_spec.py           # Split and verify
    python3 split_spec.py --verify  # Verify only (no split)
    python3 split_spec.py -v        # Verbose routing decisions

Platform routing:
    general → tv, android, ios
    tv      → tv
    android → android
    ios     → ios
    phone   → android, ios

Inheritance rules (in priority order):
    1. Preamble headers ("How to Use This Spec", "Table of Contents") → general
    2. Section 9 blanket rule: any section starting with "9" → tv
    3. Exact match in CSV platform map
    4. Parent strip: "3.1.1" → try "3.1" → try "3"
    5. Inherit from last numbered parent on stack (for unnumbered headers)
    6. Fallback → general
"""

import csv
import re
import sys
from pathlib import Path

SPEC_FILE = Path("couchraoke_spec.md")
CSV_FILE = Path("split_plan.csv")
OUTPUT_DIR = Path("spec")

OUTPUT_FILES = {
    "tv":      OUTPUT_DIR / "tv_spec.md",
    "android": OUTPUT_DIR / "android_spec.md",
    "ios":     OUTPUT_DIR / "ios_spec.md",
}

PLATFORM_ROUTES = {
    "general": ["tv", "android", "ios"],
    "tv":      ["tv"],
    "android": ["android"],
    "ios":     ["ios"],
    "phone":   ["android", "ios"],
}

PREAMBLE_HEADERS = {"how to use this spec", "table of contents"}


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _csv_key_from_chapter(chapter: str):
    """Extract section key from the 'Chapter / Section' column."""
    if not chapter or chapter.startswith("("):
        return None
    # "1. Product Contract" → "1"
    m = re.match(r"^(\d+)\.", chapter)
    if m:
        return m.group(1)
    # "Appendix A" → "A"
    m = re.match(r"^Appendix\s+([A-Z])\b", chapter, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def _csv_key_from_header(header: str):
    """Extract section key from the 'Header' column."""
    if not header or header.startswith("("):
        return None
    # "1.1 Something" or "3.1.1.1 Something"
    m = re.match(r"^(\d+(?:\.\d+)+)\b", header)
    if m:
        return m.group(1)
    # "A.1 Something"
    m = re.match(r"^([A-Z]\.\d+(?:\.\d+)*)\b", header)
    if m:
        return m.group(1)
    return None


def load_platform_map(csv_path: Path) -> dict:
    """Parse CSV → {section_number: platform_string}."""
    platform_map = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            platform = row.get("Target Platform", "").strip()
            if not platform:
                continue
            key = _csv_key_from_chapter(
                row.get("Chapter / Section", "").strip()
            ) or _csv_key_from_header(
                row.get("Header", "").strip()
            )
            if key:
                platform_map[key] = platform
    return platform_map


# ---------------------------------------------------------------------------
# Heading parsing
# ---------------------------------------------------------------------------

def extract_heading_info(line: str):
    """Return (level, section_number_or_None) from a heading line.

    section_number_or_None is the dotted section id, e.g. "3.1.1", "A.2".
    Returns (None, None) if the line is not a heading.
    """
    m = re.match(r"^(#+)\s+(.*)", line)
    if not m:
        return None, None

    level = len(m.group(1))
    text = m.group(2).strip().rstrip("*").rstrip(":").strip()

    # Numeric: "1. X" → "1", "1.1 X" → "1.1", "3.1.1.1 X" → "3.1.1.1"
    m2 = re.match(r"^(\d+(?:\.\d+)*)[.\s]", text)
    if m2:
        return level, m2.group(1)

    # "Appendix A: X" → "A"
    m2 = re.match(r"^Appendix\s+([A-Z])\b", text, re.IGNORECASE)
    if m2:
        return level, m2.group(1).upper()

    # "A.1 X" → "A.1"
    m2 = re.match(r"^([A-Z]\.\d+(?:\.\d+)*)\b", text)
    if m2:
        return level, m2.group(1)

    # Unnumbered
    return level, None


def heading_text_lower(line: str) -> str:
    """Return lowercased heading text (without # marks)."""
    m = re.match(r"^#+\s+(.*)", line.rstrip("\r\n"))
    return m.group(1).strip().lower() if m else ""


# ---------------------------------------------------------------------------
# Platform resolution
# ---------------------------------------------------------------------------

def resolve_platform(section_num, parent_stack: list, platform_map: dict) -> str:
    """Resolve which platform string applies to this heading."""
    if section_num is None:
        # Unnumbered: inherit from most recent numbered parent
        for _, snum, plat in reversed(parent_stack):
            if snum is not None:
                return plat
        return "general"

    # Section 9 blanket rule
    if re.match(r"^9(\.|$)", section_num):
        return "tv"

    # Exact match
    if section_num in platform_map:
        return platform_map[section_num]

    # Parent strip: "3.1.1" → "3.1" → "3"
    parts = section_num.split(".")
    while len(parts) > 1:
        parts.pop()
        parent = ".".join(parts)
        if parent in platform_map:
            return platform_map[parent]

    return "general"


def update_stack(stack: list, level: int, section_num, platform: str):
    """Pop same/deeper entries then push current heading."""
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, section_num, platform))


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def split_spec(verbose: bool = False):
    """Read the master spec and route each line to the correct output file(s)."""
    platform_map = load_platform_map(CSV_FILE)
    if verbose:
        print(f"Platform map ({len(platform_map)} entries):")
        for k, v in sorted(platform_map.items()):
            print(f"  {k!r:15} → {v}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    handles = {k: open(v, "w", encoding="utf-8") for k, v in OUTPUT_FILES.items()}
    current_dests = list(PLATFORM_ROUTES["general"])  # preamble: all three
    parent_stack: list = []

    try:
        with open(SPEC_FILE, encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    level, section_num = extract_heading_info(line)
                    if heading_text_lower(line) in PREAMBLE_HEADERS:
                        platform = "general"
                    else:
                        platform = resolve_platform(section_num, parent_stack, platform_map)
                    update_stack(parent_stack, level, section_num, platform)
                    current_dests = list(
                        PLATFORM_ROUTES.get(platform, PLATFORM_ROUTES["general"])
                    )
                    if verbose:
                        sn = section_num or "(unnumbered)"
                        hashes = "#" * level
                        print(f"  {hashes} [{sn}] → {platform} → {current_dests}")

                for dest in current_dests:
                    handles[dest].write(line)
    finally:
        for h in handles.values():
            h.close()

    for key, path in OUTPUT_FILES.items():
        lines = len(path.read_text(encoding="utf-8").splitlines())
        print(f"  {path}: {lines} lines")


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify_split() -> bool:
    """Replay split logic and assert each heading appears in exactly the
    right output files."""
    platform_map = load_platform_map(CSV_FILE)

    # Load output file lines into sets for O(1) lookup
    file_lines: dict[str, set] = {}
    for key, path in OUTPUT_FILES.items():
        if path.exists():
            file_lines[key] = set(path.read_text(encoding="utf-8").splitlines())
        else:
            file_lines[key] = set()
            print(f"  WARNING: {path} does not exist", file=sys.stderr)

    errors: list[str] = []
    parent_stack: list = []
    current_dests = list(PLATFORM_ROUTES["general"])

    with open(SPEC_FILE, encoding="utf-8") as f:
        for line in f:
            if not line.startswith("#"):
                continue
            level, section_num = extract_heading_info(line)
            if heading_text_lower(line) in PREAMBLE_HEADERS:
                platform = "general"
            else:
                platform = resolve_platform(section_num, parent_stack, platform_map)
            update_stack(parent_stack, level, section_num, platform)
            current_dests = list(
                PLATFORM_ROUTES.get(platform, PLATFORM_ROUTES["general"])
            )

            h = line.rstrip("\r\n")
            expected = set(current_dests)
            for dest in OUTPUT_FILES:
                in_file = h in file_lines.get(dest, set())
                should_be = dest in expected
                if in_file and not should_be:
                    errors.append(f"FAIL (unexpected in {dest}): {h[:70]!r}")
                elif not in_file and should_be:
                    errors.append(f"FAIL (missing from {dest}): {h[:70]!r}")

    if errors:
        print(f"Verification FAILED ({len(errors)} error(s)):")
        for e in errors[:30]:
            print(f"  {e}")
        if len(errors) > 30:
            print(f"  ... and {len(errors) - 30} more")
        return False

    print("Verification PASSED: all headings are in exactly the correct files")
    return True


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    verify_only = "--verify" in sys.argv

    if not SPEC_FILE.exists():
        print(f"Error: {SPEC_FILE} not found", file=sys.stderr)
        sys.exit(1)
    if not CSV_FILE.exists():
        print(f"Error: {CSV_FILE} not found", file=sys.stderr)
        sys.exit(1)

    if not verify_only:
        print("Splitting spec...")
        split_spec(verbose=verbose)

    print("\nVerifying...")
    ok = verify_split()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
