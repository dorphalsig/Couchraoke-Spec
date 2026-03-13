#!/usr/bin/env python3
"""Split a monolithic spec into platform-specific files.

Usage:
    python3 split_spec.py [--spec-file FILE] [--csv-file FILE] [--output-dir DIR]
    python3 split_spec.py --verify
    python3 split_spec.py -v

Platform routing:
    general → tv, android, ios
    tv      → tv
    android → android
    ios     → ios
    phone   → android, ios

Heading level normalization:
    A heading's depth in output reflects its depth among included ancestors,
    not its depth in the source.
    Example: ### 3.1.3 (tv) whose parent ## 3.1 is phone-only
             → ## 3.1.3 in TV output, then renumbered to ## 3.1.

Inheritance rules (in priority order):
    1. Preamble headers ("How to Use This Spec", "Table of Contents") → general
    2. Exact match in CSV platform map
    3. Parent strip: "3.1.1" → try "3.1" → try "3"
    4. Inherit from last numbered parent on stack (for unnumbered headers)
    5. Fallback → general
"""

import argparse
import csv
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path


DEFAULT_SPEC_FILE = Path("couchraoke_spec.md")
DEFAULT_CSV_FILE = Path("couchraoke_spec_split_plan.csv")
DEFAULT_OUTPUT_DIR = Path("spec")

PLATFORM_ROUTES = {
    "general": ["tv", "android", "ios"],
    "tv":      ["tv"],
    "android": ["android"],
    "ios":     ["ios"],
    "phone":   ["android", "ios"],
}

PREAMBLE_HEADERS = {"how to use this spec", "table of contents"}

# Set by main() from CLI args
SPEC_FILE: Path = DEFAULT_SPEC_FILE
CSV_FILE: Path = DEFAULT_CSV_FILE
OUTPUT_DIR: Path = DEFAULT_OUTPUT_DIR
OUTPUT_FILES: dict[str, Path] = {}


def compute_output_files(spec_file: Path, output_dir: Path) -> dict[str, Path]:
    stem = spec_file.stem
    return {
        "tv":      output_dir / "tv"      / f"tv_{stem}.md",
        "android": output_dir / "android" / f"android_{stem}.md",
        "ios":     output_dir / "ios"     / f"ios_{stem}.md",
    }


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SectionNode:
    heading_line: str
    level: int
    section_num: str | None
    platform: str
    content: list[str]
    children: list["SectionNode"] = field(default_factory=list)


@dataclass
class GeneratedHeading:
    line_index: int
    level: int
    kind: str
    identifier: str | None
    title: str
    original_line: str


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------

def _csv_key_from_chapter(chapter: str):
    if not chapter or chapter.startswith("("):
        return None
    m = re.match(r"^(\d+)\.", chapter)
    if m:
        return m.group(1)
    m = re.match(r"^Appendix\s+([A-Z])\b", chapter, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    return None


def _csv_key_from_header(header: str):
    if not header or header.startswith("("):
        return None
    m = re.match(r"^(\d+(?:\.\d+)+)\b", header)
    if m:
        return m.group(1)
    m = re.match(r"^([A-Z]\.\d+(?:\.\d+)*)\b", header)
    if m:
        return m.group(1)
    return None


def load_platform_map(csv_path: Path) -> dict:
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
# Heading utilities
# ---------------------------------------------------------------------------

def extract_heading_info(line: str):
    """Return (level, section_num_or_None) from a heading line."""
    m = re.match(r"^(#+)\s+(.*)", line)
    if not m:
        return None, None

    level = len(m.group(1))
    text = m.group(2).strip().rstrip("*").rstrip(":").strip()

    m2 = re.match(r"^(\d+(?:\.\d+)*)[.\s]", text)
    if m2:
        return level, m2.group(1)

    m2 = re.match(r"^Appendix\s+([A-Z])\b", text, re.IGNORECASE)
    if m2:
        return level, m2.group(1).upper()

    m2 = re.match(r"^([A-Z]\.\d+(?:\.\d+)*)\b", text)
    if m2:
        return level, m2.group(1)

    return level, None


def heading_text_lower(line: str) -> str:
    m = re.match(r"^#+\s+(.*)", line.rstrip("\r\n"))
    return m.group(1).strip().lower() if m else ""


def heading_body(line: str) -> str:
    """Heading content without leading # marks (used for level-agnostic verify matching)."""
    m = re.match(r"^#+\s+(.*)", line.rstrip("\r\n"))
    return m.group(1) if m else ""


# ---------------------------------------------------------------------------
# Platform resolution
# ---------------------------------------------------------------------------

def resolve_platform(section_num, parent_stack: list, platform_map: dict) -> str:
    if section_num is None:
        for _, snum, plat in reversed(parent_stack):
            if snum is not None:
                return plat
        return "general"

    if section_num in platform_map:
        return platform_map[section_num]

    parts = section_num.split(".")
    while len(parts) > 1:
        parts.pop()
        parent = ".".join(parts)
        if parent in platform_map:
            return platform_map[parent]

    return "general"


def update_stack(stack: list, level: int, section_num, platform: str):
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, section_num, platform))


# ---------------------------------------------------------------------------
# Tree building
# ---------------------------------------------------------------------------

def parse_sections(lines: list[str]) -> tuple[list[str], list[tuple]]:
    """Parse lines into (preamble_lines, flat_sections).

    Each flat section: (heading_line, level, section_num, content_lines).
    Preamble: lines before the first heading.
    """
    preamble: list[str] = []
    flat: list[tuple] = []
    current_heading: str | None = None
    current_level = 0
    current_section_num: str | None = None
    current_content: list[str] = []

    for line in lines:
        if line.startswith("#"):
            level, section_num = extract_heading_info(line)
            if level is None:
                current_content.append(line)
                continue
            if current_heading is not None:
                flat.append((current_heading, current_level, current_section_num, current_content))
            else:
                preamble = current_content
            current_heading = line
            current_level = level
            current_section_num = section_num
            current_content = []
        else:
            current_content.append(line)

    if current_heading is not None:
        flat.append((current_heading, current_level, current_section_num, current_content))

    return preamble, flat


def build_section_tree(
    flat: list[tuple], platform_map: dict, verbose: bool = False
) -> list[SectionNode]:
    """Build SectionNode tree from flat section list, resolving platforms."""
    root: list[SectionNode] = []
    node_stack: list[SectionNode] = []
    parent_stack: list = []  # [(level, section_num, platform)] for platform resolution

    for heading_line, level, section_num, content in flat:
        if heading_text_lower(heading_line) in PREAMBLE_HEADERS:
            platform = "general"
        else:
            platform = resolve_platform(section_num, parent_stack, platform_map)
        update_stack(parent_stack, level, section_num, platform)

        if verbose:
            sn = section_num or "(unnumbered)"
            dests = PLATFORM_ROUTES.get(platform, PLATFORM_ROUTES["general"])
            print(f"  {'#' * level} [{sn}] → {platform} → {dests}")

        node = SectionNode(heading_line, level, section_num, platform, content)

        while node_stack and node_stack[-1].level >= level:
            node_stack.pop()
        (node_stack[-1].children if node_stack else root).append(node)
        node_stack.append(node)

    return root


# ---------------------------------------------------------------------------
# Platform-filtered write with level normalization
# ---------------------------------------------------------------------------

def write_platform_nodes(
    nodes: list[SectionNode], target_plat: str, out, effective_level: int = 0
):
    """Write nodes for target_plat with heading levels normalized to tree depth.

    When a node is excluded, its children are promoted: written at the same
    effective_level so they inherit the excluded node's parent's depth.
    """
    for node in nodes:
        if target_plat in PLATFORM_ROUTES.get(node.platform, PLATFORM_ROUTES["general"]):
            new_level = effective_level + 1
            m = re.match(r"^(#+)\s+(.*)", node.heading_line.rstrip("\r\n"))
            out.write("#" * new_level + " " + m.group(2) + "\n")
            for line in node.content:
                out.write(line)
            write_platform_nodes(node.children, target_plat, out, new_level)
        else:
            # Excluded: promote children up to current effective level
            write_platform_nodes(node.children, target_plat, out, effective_level)


# ---------------------------------------------------------------------------
# Generated file operations (renumber + verify numbering)
# ---------------------------------------------------------------------------

def parse_generated_heading(line: str, line_index: int) -> GeneratedHeading | None:
    m = re.match(r"^(#+)\s+(.*)$", line.rstrip("\r\n"))
    if not m:
        return None

    level = len(m.group(1))
    text = m.group(2).strip()

    m_num = re.match(r"^(\d+(?:\.\d+)*)(?:\.)?\s+(.*)$", text)
    if m_num:
        return GeneratedHeading(line_index, level, "numeric", m_num.group(1), m_num.group(2), line)

    m_appendix = re.match(r"^Appendix\s+([A-Z])\s*:\s*(.*)$", text)
    if m_appendix:
        return GeneratedHeading(line_index, level, "appendix", m_appendix.group(1), m_appendix.group(2), line)

    m_appendix_sub = re.match(r"^([A-Z]\.\d+(?:\.\d+)*)\s+(.*)$", text)
    if m_appendix_sub:
        return GeneratedHeading(line_index, level, "appendix_subsection", m_appendix_sub.group(1), m_appendix_sub.group(2), line)

    return GeneratedHeading(line_index, level, "unnumbered", None, text, line)


def load_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines(keepends=True)


def find_toc_bounds(lines: list[str]) -> tuple[int, int] | None:
    start = None
    for i, line in enumerate(lines):
        if line.rstrip("\r\n") == "Table of Contents":
            start = i
            break
    if start is None:
        return None

    end = len(lines)
    for i in range(start + 1, len(lines)):
        parsed = parse_generated_heading(lines[i], i)
        if parsed and parsed.kind != "unnumbered":
            end = i
            break
    return (start, end)


def render_heading(
    heading: GeneratedHeading,
    new_identifier: str | None,
    appendix_letter: str | None = None,
) -> str:
    hashes = "#" * heading.level
    if heading.kind == "numeric" and new_identifier:
        suffix = "." if heading.level == 1 else ""
        return f"{hashes} {new_identifier}{suffix} {heading.title}\n"
    if heading.kind == "appendix" and appendix_letter:
        return f"{hashes} Appendix {appendix_letter}: {heading.title}\n"
    if heading.kind == "appendix_subsection" and new_identifier:
        return f"{hashes} {new_identifier} {heading.title}\n"
    return heading.original_line if heading.original_line.endswith("\n") else heading.original_line + "\n"


def renumber_generated_file(path: Path):
    lines = load_lines(path)
    parsed = [parse_generated_heading(line, idx) for idx, line in enumerate(lines)]
    headings = [h for h in parsed if h]

    counters: dict[int, int] = {}
    appendix_letter_index = 0
    current_appendix_letter = None
    appendix_sub_counters: dict[int, int] = {}
    toc_entries: list[tuple[int, str]] = []

    for heading in headings:
        if heading.kind == "numeric":
            counters[heading.level] = counters.get(heading.level, 0) + 1
            for deeper in list(counters.keys()):
                if deeper > heading.level:
                    del counters[deeper]
            parts = [str(counters[level]) for level in sorted(counters) if level <= heading.level]
            new_id = ".".join(parts)
            lines[heading.line_index] = render_heading(heading, new_id)
            toc_entries.append((heading.level, f"{new_id} {heading.title}"))
        elif heading.kind == "appendix":
            appendix_letter_index += 1
            current_appendix_letter = chr(ord("A") + appendix_letter_index - 1)
            appendix_sub_counters = {}
            lines[heading.line_index] = render_heading(heading, None, current_appendix_letter)
            toc_entries.append((heading.level, f"Appendix {current_appendix_letter}: {heading.title}"))
        elif heading.kind == "appendix_subsection" and current_appendix_letter:
            sub_depth = heading.level
            appendix_sub_counters[sub_depth] = appendix_sub_counters.get(sub_depth, 0) + 1
            for deeper in list(appendix_sub_counters.keys()):
                if deeper > sub_depth:
                    del appendix_sub_counters[deeper]
            suffix = ".".join(
                str(appendix_sub_counters[level])
                for level in sorted(appendix_sub_counters)
                if level <= sub_depth
            )
            new_id = f"{current_appendix_letter}.{suffix}"
            lines[heading.line_index] = render_heading(heading, new_id)
            toc_entries.append((heading.level, f"{new_id} {heading.title}"))

    toc = find_toc_bounds(lines)
    if toc:
        start, end = toc
        toc_lines = ["Table of Contents\n"]
        for level, entry in toc_entries:
            indent = "    " * max(level - 1, 1)
            toc_lines.append(f"{indent}{entry}\n")
        toc_lines.append("\n")
        lines[start:end] = toc_lines

    path.write_text("".join(lines), encoding="utf-8")


def verify_local_numbering(path: Path) -> list[str]:
    errors: list[str] = []
    lines = load_lines(path)
    parsed = [parse_generated_heading(line, idx) for idx, line in enumerate(lines)]
    headings = [h for h in parsed if h]

    expected_numeric: dict[int, int] = {}
    appendix_letter_index = 0
    current_appendix_letter = None
    appendix_sub_counters: dict[int, int] = {}
    toc_entries: list[str] = []

    for heading in headings:
        if heading.kind == "numeric":
            expected_numeric[heading.level] = expected_numeric.get(heading.level, 0) + 1
            for deeper in list(expected_numeric.keys()):
                if deeper > heading.level:
                    del expected_numeric[deeper]
            expected = ".".join(
                str(expected_numeric[level])
                for level in sorted(expected_numeric)
                if level <= heading.level
            )
            if heading.identifier != expected:
                errors.append(
                    f"{path}: line {heading.line_index + 1} "
                    f"expected numeric heading {expected}, found {heading.identifier}"
                )
            toc_entries.append(f"{'    ' * max(heading.level - 1, 1)}{expected} {heading.title}")
        elif heading.kind == "appendix":
            appendix_letter_index += 1
            current_appendix_letter = chr(ord("A") + appendix_letter_index - 1)
            appendix_sub_counters = {}
            if heading.identifier != current_appendix_letter:
                errors.append(
                    f"{path}: line {heading.line_index + 1} "
                    f"expected appendix {current_appendix_letter}, found {heading.identifier}"
                )
            toc_entries.append(
                f"{'    ' * max(heading.level - 1, 1)}Appendix {current_appendix_letter}: {heading.title}"
            )
        elif heading.kind == "appendix_subsection" and current_appendix_letter:
            sub_depth = heading.level
            appendix_sub_counters[sub_depth] = appendix_sub_counters.get(sub_depth, 0) + 1
            for deeper in list(appendix_sub_counters.keys()):
                if deeper > sub_depth:
                    del appendix_sub_counters[deeper]
            suffix = ".".join(
                str(appendix_sub_counters[level])
                for level in sorted(appendix_sub_counters)
                if level <= sub_depth
            )
            expected = f"{current_appendix_letter}.{suffix}"
            if heading.identifier != expected:
                errors.append(
                    f"{path}: line {heading.line_index + 1} "
                    f"expected appendix subsection {expected}, found {heading.identifier}"
                )
            toc_entries.append(f"{'    ' * max(heading.level - 1, 1)}{expected} {heading.title}")

    toc = find_toc_bounds(lines)
    if toc:
        start, end = toc
        actual_toc = [line.rstrip("\r\n") for line in lines[start + 1:end] if line.strip()]
        if actual_toc != toc_entries:
            errors.append(f"{path}: TOC entries do not match renumbered headings")
    return errors


# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------

def split_spec(verbose: bool = False):
    """Build section tree and write platform-filtered files with normalized levels."""
    platform_map = load_platform_map(CSV_FILE)
    if verbose:
        print(f"Platform map ({len(platform_map)} entries):")
        for k, v in sorted(platform_map.items()):
            print(f"  {k!r:15} → {v}")

    lines = SPEC_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    preamble, flat = parse_sections(lines)
    root = build_section_tree(flat, platform_map, verbose=verbose)

    for plat, path in OUTPUT_FILES.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as out:
            for line in preamble:
                out.write(line)
            write_platform_nodes(root, plat, out)
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        print(f"  {path}: {line_count} lines")


# ---------------------------------------------------------------------------
# Verify
# ---------------------------------------------------------------------------

def verify_split() -> bool:
    """Verify routing by comparing heading bodies (level-agnostic) across output files."""
    platform_map = load_platform_map(CSV_FILE)

    # Build sets of heading bodies from each output file (level-agnostic: strip #s)
    file_bodies: dict[str, set[str]] = {}
    for key, path in OUTPUT_FILES.items():
        if path.exists():
            file_bodies[key] = {
                heading_body(l)
                for l in path.read_text(encoding="utf-8").splitlines()
                if l.startswith("#")
            }
        else:
            file_bodies[key] = set()
            print(f"  WARNING: {path} does not exist", file=sys.stderr)

    errors: list[str] = []
    parent_stack: list = []

    lines = SPEC_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    _, flat = parse_sections(lines)

    for heading_line, level, section_num, _ in flat:
        if heading_text_lower(heading_line) in PREAMBLE_HEADERS:
            platform = "general"
        else:
            platform = resolve_platform(section_num, parent_stack, platform_map)
        update_stack(parent_stack, level, section_num, platform)

        expected = set(PLATFORM_ROUTES.get(platform, PLATFORM_ROUTES["general"]))
        body = heading_body(heading_line)

        for dest in OUTPUT_FILES:
            in_file = body in file_bodies.get(dest, set())
            should_be = dest in expected
            if in_file and not should_be:
                errors.append(f"FAIL (unexpected in {dest}): {heading_line[:70]!r}")
            elif not in_file and should_be:
                errors.append(f"FAIL (missing from {dest}): {heading_line[:70]!r}")

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
    parser = argparse.ArgumentParser(
        description="Split a spec into platform-specific files.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--spec-file", type=Path, default=DEFAULT_SPEC_FILE,
        help=f"Markdown spec to split (default: {DEFAULT_SPEC_FILE})",
    )
    parser.add_argument(
        "--csv-file", type=Path, default=DEFAULT_CSV_FILE,
        help=f"Routing CSV (default: {DEFAULT_CSV_FILE})",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument("--verify", action="store_true", help="Verify only (no split)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose routing decisions")
    args = parser.parse_args()

    if not args.spec_file.exists():
        print(f"Error: {args.spec_file} not found", file=sys.stderr)
        sys.exit(1)
    if not args.csv_file.exists():
        print(f"Error: {args.csv_file} not found", file=sys.stderr)
        sys.exit(1)

    global SPEC_FILE, CSV_FILE, OUTPUT_DIR, OUTPUT_FILES
    SPEC_FILE = args.spec_file
    CSV_FILE = args.csv_file
    OUTPUT_DIR = args.output_dir
    OUTPUT_FILES = compute_output_files(SPEC_FILE, OUTPUT_DIR)

    if not args.verify:
        print("Splitting spec...")
        split_spec(verbose=args.verbose)

    print("\nVerifying split routing...")
    ok = verify_split()
    if not ok:
        sys.exit(1)

    if not args.verify:
        print("\nRenumbering generated specs...")
        for path in OUTPUT_FILES.values():
            renumber_generated_file(path)


if __name__ == "__main__":
    main()
