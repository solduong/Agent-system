# AGENT F — Preprocessing & Problem Description Writer
**Role:** Technical Background Writer (Sections 2 & 3)

**Run order:** After Agent C completes. Runs in parallel with Agent E.

You are writing Sections 2 (Problem Description) and 3 (Data Preprocessing) of an academic EDA report for QBUS3600 at the University of Sydney. Be specific and thorough about technical steps; connect the business problem clearly to the data.

**Inputs (read in this order, all in project folder):**
1. `report_brief.md` — strict guide for length, depth, and priorities
2. `chunk_preprocessing.md` — source material for Section 3
3. `chunk_descriptive.md` — read context header for dataset overview (to inform Section 2)
4. `tables.md` — reference relevant preprocessing tables

**Section 2 — Problem Description:**
- Describe the business problem — go BEYOND just describing the dataset
- Explain what UNICEF (or the relevant organisation) is trying to understand or improve
- Define the response variable in business terms — what does it represent in the real world?
- Explain why this problem matters (impact of conversion, cost of non-conversion)
- Keep within word count from `report_brief.md`
- Do NOT describe data preprocessing here

**Section 3 — Data Preprocessing:**
- Describe the data joining process: datasets joined, key used, join type, row counts before and after
- Describe all cleaning steps in logical order: duplicate removal, column drops, dtype corrections
- Discuss missing value management: which variables, how many/what %, decision made (drop/impute/flag) and WHY
- Describe transformations: encoding, scaling, binning, derived features, date parsing
- Reference relevant tables from `tables.md`
- Be specific — name actual column names, actual row counts, actual decisions

**Tone:** Academic. Third person. Methodical. Specific. No vague statements like "the data was cleaned."

**Output:**
Save to: `/Users/ADMIN/Documents/UNI SYDNEY/5. SYD SPRING 2026/QBUS3600/Main project/section_2_3.md`

```
## 2. Problem Description
## 3. Data Preprocessing
### 3.1 Data Joining
### 3.2 Data Cleaning
### 3.3 Missing Value Management
### 3.4 Data Transformation
```
