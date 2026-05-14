#!/usr/bin/env python3
"""QA Audit script for Unified_Notebook.ipynb"""
import json
import re
import os

NB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "Shared Modelling", "Unified NOTEBOOK", "Unified_Notebook.ipynb"
)

print(f"Reading: {NB_PATH}")
print(f"File size: {os.path.getsize(NB_PATH):,} bytes")
print()

with open(NB_PATH, "r", encoding="utf-8") as f:
    nb = json.load(f)

cells = nb["cells"]
total = len(cells)
code_cells = [(i, c) for i, c in enumerate(cells) if c["cell_type"] == "code"]
md_cells = [(i, c) for i, c in enumerate(cells) if c["cell_type"] == "markdown"]
raw_cells = [(i, c) for i, c in enumerate(cells) if c["cell_type"] == "raw"]

# ================================================================
# SECTION 6: CELL COUNT & BREAKDOWN
# ================================================================
print("=" * 80)
print("SECTION 6: CELL COUNT & BREAKDOWN")
print("=" * 80)
print(f"Total cells:    {total}")
print(f"Code cells:     {len(code_cells)}")
print(f"Markdown cells: {len(md_cells)}")
print(f"Raw cells:      {len(raw_cells)}")
print()

# ================================================================
# SECTIONS 1-3: FILE-SAVING OPERATIONS
# ================================================================
print("=" * 80)
print("SECTIONS 1-3: FILE-SAVING OPERATIONS IN CODE CELLS")
print("=" * 80)

save_patterns = [
    (r"\.to_csv\s*\(", ".to_csv("),
    (r"\.to_parquet\s*\(", ".to_parquet("),
    (r"\.to_excel\s*\(", ".to_excel("),
    (r"savefig\s*\(", "savefig("),
    (r"joblib\.dump\s*\(", "joblib.dump("),
    (r"pickle\.dump\s*\(", "pickle.dump("),
    (r"shutil\.copy", "shutil.copy"),
    (r"\.save\s*\(", ".save("),
    (r"json\.dump\s*\(", "json.dump("),
    (r"open\s*\([^)]*[\"'][wWaA]", "open(w/a)"),
    (r"np\.save", "np.save"),
    (r"pd\.ExcelWriter", "pd.ExcelWriter"),
    (r"\.to_json\s*\(", ".to_json("),
]

# Patterns to extract file path arguments
path_extract_patterns = [
    (r"\.to_csv\s*\(\s*(.+?)[\s,)]", "to_csv"),
    (r"\.to_parquet\s*\(\s*(.+?)[\s,)]", "to_parquet"),
    (r"\.to_excel\s*\(\s*(.+?)[\s,)]", "to_excel"),
    (r"savefig\s*\(\s*(.+?)[\s,)]", "savefig"),
    (r"joblib\.dump\s*\(.+?,\s*(.+?)[\s,)]", "joblib.dump"),
    (r"json\.dump\s*\(.+?,\s*(.+?)[\s,)]", "json.dump"),
]

save_count = 0
for idx, cell in code_cells:
    lines = cell["source"]
    cell_hits = []
    for line_no, line in enumerate(lines):
        line_stripped = line.strip()
        if line_stripped.startswith("#"):
            continue
        for pat, label in save_patterns:
            if re.search(pat, line):
                # Try to extract file path
                path_str = ""
                for ppat, plabel in path_extract_patterns:
                    m = re.search(ppat, line)
                    if m:
                        path_str = f"  --> PATH: {m.group(1).strip()}"
                        break
                cell_hits.append((line_no + 1, label, line.rstrip(), path_str))
    if cell_hits:
        print(f"\n--- Cell {idx} ---")
        for ln, label, text, path in cell_hits:
            save_count += 1
            print(f"  Line {ln:3d} [{label:20s}]  {text}")
            if path:
                print(f"           {path}")

print(f"\nTotal save operations found: {save_count}")
print()

# ================================================================
# SECTION 4: OUTPUT DIRECTORY REFERENCES
# ================================================================
print("=" * 80)
print("SECTION 4: OUTPUT DIRECTORY VARIABLE REFERENCES")
print("=" * 80)

out_vars = [
    "OUT_EDA", "OUT_LR", "OUT_GLM", "OUT_GAM", "OUT_XGB",
    "OUT_CAT", "OUT_LGB", "OUT_RF", "OUT_NN", "OUT_COMP", "OUTPUTS"
]

for var in out_vars:
    print(f"\n--- {var} ---")
    found = False
    for idx, cell in code_cells:
        lines = cell["source"]
        for line_no, line in enumerate(lines):
            # Use word boundary to avoid partial matches (e.g. OUTPUTS matching OUT_...)
            if re.search(r"\b" + re.escape(var) + r"\b", line) and not line.strip().startswith("#"):
                found = True
                print(f"  Cell {idx:3d}, Line {line_no+1:3d}: {line.rstrip()}")
    if not found:
        print(f"  ** NOT FOUND **")

print()

# ================================================================
# SECTION 5: MARKDOWN HEADERS WITH Phase/Task/Section
# ================================================================
print("=" * 80)
print("SECTION 5: MARKDOWN CELLS WITH 'Phase' / 'Task' / 'Section' HEADERS")
print("=" * 80)

for idx, cell in md_cells:
    source_lines = cell["source"]
    first_line = source_lines[0].strip() if source_lines else ""
    full_text = "".join(source_lines)
    if re.search(r"(?i)(phase|task|section)", full_text):
        matches = []
        for ln, line in enumerate(source_lines):
            if re.search(r"(?i)(phase|task|section)", line):
                matches.append(line.rstrip())
        print(f"\n  Cell {idx:3d} | First line: {first_line}")
        for m in matches:
            print(f"           | Match: {m}")

print()

# ================================================================
# SECTION 7: CELL 2 (MASTER IMPORTS)
# ================================================================
print("=" * 80)
print("SECTION 7: CELL 2 (index 2) -- MASTER IMPORTS CHECK")
print("=" * 80)

if len(cells) > 2:
    c2 = cells[2]
    print(f"Cell type: {c2['cell_type']}")
    src = "".join(c2["source"])
    print(f"Length: {len(src)} chars, {len(c2['source'])} lines")
    print()
    print("--- FULL CONTENT ---")
    for i, line in enumerate(c2["source"]):
        print(f"  {i+1:3d}: {line.rstrip()}")
    print("--- END ---")

    print("\n--- IMPORTS FOUND ---")
    for line in c2["source"]:
        ls = line.strip()
        if ls.startswith("import ") or ls.startswith("from ") or ("import " in ls and not ls.startswith("#")):
            print(f"  {ls}")
else:
    print("  ** Cell index 2 does not exist **")

print()

# ================================================================
# SECTION 7b: CONSTANTS CELL -- OUT_* DEFINITIONS
# ================================================================
print("=" * 80)
print("SECTION 7b: CONSTANTS CELL -- OUT_* VARIABLE DEFINITIONS")
print("=" * 80)

found_constants = False
for idx, cell in code_cells:
    out_defs = [line for line in cell["source"] if re.match(r"\s*(OUT_|OUTPUTS)\w*\s*=", line)]
    if len(out_defs) >= 2:
        found_constants = True
        print(f"\n  Constants cell found at index {idx}")
        print(f"  Full content:")
        for i, line in enumerate(cell["source"]):
            print(f"    {i+1:3d}: {line.rstrip()}")
        print()
        defined = set()
        for line in cell["source"]:
            m = re.match(r"\s*(OUT_\w+|OUTPUTS)\s*=", line)
            if m:
                defined.add(m.group(1))
        print(f"  Defined OUT_* variables: {sorted(defined)}")
        expected = set(out_vars)
        missing = expected - defined
        extra = defined - expected
        if missing:
            print(f"  ** MISSING: {sorted(missing)} **")
        if extra:
            print(f"  EXTRA (not in expected list): {sorted(extra)}")
        if not missing and not extra:
            print(f"  All expected variables are defined.")
        break

if not found_constants:
    print("  ** No constants cell found with multiple OUT_* definitions **")
    # Try to find any cell defining at least one OUT_ variable
    print("  Searching for any OUT_ definitions...")
    for idx, cell in code_cells:
        for line in cell["source"]:
            if re.match(r"\s*OUT_\w+\s*=", line):
                print(f"    Cell {idx}: {line.rstrip()}")

print()

# ================================================================
# SECTION 8: REPRODUCIBILITY CHECKLIST
# ================================================================
print("=" * 80)
print("SECTION 8: REPRODUCIBILITY CHECKLIST (searching near end)")
print("=" * 80)

found_repro = False
# Search from end backwards, then full notebook
for idx in range(len(cells) - 1, max(len(cells) - 40, -1), -1):
    cell = cells[idx]
    source = "".join(cell["source"])
    if re.search(r"(?i)reproduc", source) or re.search(r"(?i)checklist", source):
        print(f"\n  Found at cell index {idx} (type: {cell['cell_type']})")
        print(f"  --- FULL CONTENT ---")
        for i, line in enumerate(cell["source"]):
            print(f"    {i+1:3d}: {line.rstrip()}")
        print(f"  --- END ---")
        found_repro = True

if not found_repro:
    print("\n  Not found in last 40 cells. Searching entire notebook...")
    for idx, cell in enumerate(cells):
        source = "".join(cell["source"])
        if re.search(r"(?i)reproduc", source):
            first = cell["source"][0].rstrip() if cell["source"] else "(empty)"
            print(f"  Cell {idx} ({cell['cell_type']}): {first}")

print()

# ================================================================
# BONUS: ALL MARKDOWN CELLS (structural overview)
# ================================================================
print("=" * 80)
print("BONUS: ALL MARKDOWN CELLS (structural overview)")
print("=" * 80)

for idx, cell in md_cells:
    first = cell["source"][0].strip() if cell["source"] else "(empty)"
    if len(first) > 110:
        first = first[:110] + "..."
    print(f"  Cell {idx:3d}: {first}")

print()

# ================================================================
# BONUS 2: LAST 5 CELLS
# ================================================================
print("=" * 80)
print("BONUS 2: LAST 5 CELLS (for context)")
print("=" * 80)

for idx in range(max(0, len(cells) - 5), len(cells)):
    cell = cells[idx]
    src_lines = cell["source"]
    first = src_lines[0].rstrip() if src_lines else "(empty)"
    if len(first) > 110:
        first = first[:110] + "..."
    print(f"  Cell {idx:3d} ({cell['cell_type']:8s}): {first}")
    if cell["cell_type"] == "code" and len(src_lines) <= 15:
        for i, line in enumerate(src_lines):
            print(f"    {i+1:3d}: {line.rstrip()}")

print()
print("=" * 80)
print("AUDIT COMPLETE")
print("=" * 80)
