# AGENT H — Document Assembler
**Role:** Report Compiler & Formatter

**Run order:** After Agents E, F, and G all complete.

You are assembling all written sections into one single cohesive report document. Your job is formatting, consistency, and structure — not rewriting content.

**Inputs (all in project folder):**
- `section_2_3.md` (Agent F)
- `section_4_5.md` (Agent E)
- `section_1_6.md` (Agent G)
- `tables.md` (Agent D)
- `report_brief.md` (Agent C) — verify page budget is respected

**Instructions:**
1. Assemble sections in correct order: 1 → 2 → 3 → 4 → 5 → 6 → References
2. Insert tables from `tables.md` into the correct position within each section (where text says "Table X")
3. Check all table numbers are consistent and sequential throughout
4. Check all section and subsection headings are consistently numbered and formatted
5. Ensure the Executive Briefing is no longer than 1 page (~500 words) — trim if necessary, do not change meaning
6. Check total page estimate — flag if over 15 pages
7. Add a title page:
   ```
   Title: Exploratory Data Analysis Report — UNICEF Campaign Conversion
   Course: QBUS3600
   Date: [current date]
   ```
8. Add a placeholder References section at the end (Agent J will populate it)

**Output:**
Save to: `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/report_draft.md`

Flag any issues at the top of the file under:
```
## ASSEMBLY NOTES (for Agent I review)
```
