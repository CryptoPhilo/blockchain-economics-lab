# CRO-005: FOR Pipeline Architectural Rationale

**Agent**: CRO  
**Date**: 2026-04-19  
**Issue**: [BCE-450](/BCE/issues/BCE-450)  
**Status**: Analysis Complete

---

## Executive Summary

The FOR (Forensic) report pipeline **requires a separate architecture** from ECON/MAT pipelines due to fundamental differences in input source, processing workflow, and automation requirements. This is not a redundancy but a necessary architectural distinction.

**Key Insight**: FOR reports originate as human-authored Korean drafts in Google Drive, while ECON/MAT reports are LLM-generated from structured data. This input difference necessitates a completely different ingestion and monitoring workflow.

---

## 1. Architectural Comparison

### 1.1 ECON/MAT Pipeline (Standard Orchestrator)

```
Project Data (JSON) 
  → Stage 0: Data Collection (APIs)
  → Stage 1: LLM Text Generation
  → Stage 1.5: Translation (7 languages)
  → Stage 2: PDF Generation
  → Stage 3: Upload to GDrive
```

**Trigger**: Manual/on-demand via `orchestrator.py`  
**Input**: Structured project data from `data/projects.json`  
**Control**: Direct Python script execution

### 1.2 FOR Pipeline (GDrive Watcher)

```
Human Draft (.md in GDrive)
  → Scan GDrive drafts/FOR/ folder
  → Download new .md files
  → Strip equation images (GDocs artifact)
  → Translation (ko → 6 other languages)
  → PDF Generation (7 languages)
  → QA Verification
  → Upload to GDrive (project folders)
  → Update Supabase (coming_soon → published)
```

**Trigger**: Automated cron (every 30 minutes)  
**Input**: Manual Korean drafts uploaded to Google Drive  
**Control**: GitHub Actions workflow + state tracking

---

## 2. Why FOR Cannot Use Standard Orchestrator

### 2.1 Input Source Mismatch

| Aspect | ECON/MAT | FOR | Implication |
|--------|----------|-----|-------------|
| **Origin** | LLM-generated | Human-authored | Different data sources |
| **Format** | Structured JSON → Markdown | Google Docs → Markdown | Different parsing needs |
| **Location** | Local filesystem | Google Drive cloud | Requires GDrive API |
| **Timing** | Synchronous (on-demand) | Asynchronous (uploaded anytime) | Requires polling |

### 2.2 Workflow Differences

**ECON/MAT**: "Push model" (we generate content)
- Deterministic: input data → output report
- Single execution path
- No monitoring required

**FOR**: "Pull model" (we consume external content)
- Non-deterministic: drafts appear unpredictably
- Requires continuous scanning
- Needs state tracking (processed files)
- Requires retry logic for failures

### 2.3 Special Processing Requirements

FOR pipeline includes unique steps not needed in ECON/MAT:

1. **Equation Image Stripping** (`_strip_equation_images`)
   - Google Docs exports LaTeX math as base64 PNG images
   - Must be cleaned before translation
   - ECON/MAT don't have this issue (LLM output is clean markdown)

2. **Processed Files Tracking** (`_for_processed.json`)
   - Prevents reprocessing same drafts
   - Tracks retry attempts and failures
   - Handles stale "processing" states
   - ECON/MAT are one-shot operations (no tracking needed)

3. **Project Slug Extraction** (from filename + content)
   - Must infer project identity from draft filename
   - ECON/MAT receive explicit `--project` argument

4. **GDrive Folder Scanning**
   - Case-insensitive folder matching
   - Handles "drafts/FOR/", "drafts/for/", etc.
   - ECON/MAT work with local filesystem only

---

## 3. Infrastructure Requirements

### 3.1 Automation Method

**ECON/MAT**: Manual trigger sufficient
- Executed when analyst decides to generate report
- Runs in foreground with immediate feedback

**FOR**: Continuous monitoring required
- Drafts uploaded by external stakeholders (analysts, researchers)
- Must detect new files without manual intervention
- GitHub Actions cron (every 30 minutes)
  - Previously used Paperclip routine (BCE-364)
  - Migrated to GitHub Actions for better reliability

### 3.2 State Management

**ECON/MAT**: Stateless
- Each run is independent
- No need to remember previous runs

**FOR**: Stateful
- Must track which files already processed
- Must handle partial failures and retries
- Must detect stale "processing" locks (30-minute timeout)
- Stores state in `scripts/pipeline/output/_for_processed.json`

### 3.3 Error Handling

**ECON/MAT**: Fail-fast
- If generation fails, operator sees error immediately
- Can fix and re-run manually

**FOR**: Resilient retry
- Runs unattended (cron)
- Must retry transient failures automatically
- Must cap retries (max 3) to avoid infinite loops
- Logs failures for manual review

---

## 4. Code-Level Evidence

### 4.1 Orchestrator Cannot Handle FOR's Workflow

From `orchestrator.py:11-16`:
```python
python orchestrator.py --type for --project heyelsaai --version 1 --lang en --data data/elsa_forensic.json
```

This assumes:
- Project slug is known (`--project heyelsaai`)
- Data file exists locally (`--data data/elsa_forensic.json`)
- Operator manually triggers execution

FOR's actual workflow (`ingest_for.py`):
- Scans GDrive for unknown files
- Extracts project slug from filename
- Downloads draft on-the-fly
- Runs unattended on schedule

### 4.2 Special Processing Code

Unique to `ingest_for.py` (not in orchestrator):

```python
# Strip Google Docs equation artifacts (lines 64-92)
def _strip_equation_images(md_text: str) -> tuple[str, int]:
    """Remove base64 equation image definitions..."""

# GDrive folder scanning (lines 98-127)
def _get_drive_service():
    """Build GDrive API client with delegation..."""

# Processed files tracking (lines 130-146)
def _load_processed(service=None, folder_id: str = None) -> dict:
    """Load processed tracker from local file..."""
```

None of these functions exist in the standard orchestrator flow.

---

## 5. Could They Be Unified?

### 5.1 Technical Feasibility: Yes, but...

Theoretically, orchestrator could be extended:
- Add `--watch` flag for GDrive monitoring
- Add `--input-source gdrive` option
- Merge `ingest_for.py` logic into orchestrator

### 5.2 Architectural Recommendation: Keep Separate

**Rationale for separation**:

1. **Single Responsibility Principle**
   - Orchestrator: Execute report generation pipeline
   - Ingest: Monitor external sources and trigger pipeline
   - Mixing creates bloated, complex orchestrator

2. **Operational Independence**
   - FOR automation runs 48x/day (every 30 min)
   - ECON/MAT run on-demand (few times/week)
   - Separate = independent failure domains

3. **Different Maintenance Cadence**
   - FOR: Tuning retry logic, GDrive API handling
   - ECON/MAT: Improving LLM prompts, data collectors
   - Minimal overlap in change patterns

4. **Clear Mental Model**
   - Analysts understand: "Put draft in GDrive → auto-published"
   - vs. "Run orchestrator with correct flags"
   - Separation makes the workflow obvious

---

## 6. Alternative Architectures Considered

### Option A: Unified Orchestrator (❌ Rejected)
```
orchestrator.py --type for --watch --input-source gdrive
```
**Problems**:
- Orchestrator becomes bloated (2-3x code size)
- Tight coupling between watch logic and generation logic
- Hard to run ECON/MAT without loading GDrive dependencies

### Option B: Separate Watcher + Shared Orchestrator (⚠️ Possible but Overkill)
```
watch_for_drafts.py → orchestrator.py --type for --project X --data /tmp/draft.md
```
**Problems**:
- Extra IPC complexity (watcher → orchestrator)
- Orchestrator still needs FOR-specific processing (equation stripping, etc.)
- No clear benefit over current architecture

### Option C: Current Architecture (✅ Adopted)
```
ingest_for.py (self-contained: watch + process + upload)
```
**Benefits**:
- Clear separation of concerns
- Self-contained FOR workflow
- Easy to debug and maintain
- Obvious to operators

---

## 7. Migration History (BCE-364)

### Previous Implementation
- **Method**: Paperclip routine with schedule trigger
- **Frequency**: Every 30 minutes
- **Issue**: External dependency on Paperclip infrastructure

### Current Implementation
- **Method**: GitHub Actions workflow (`.github/workflows/for-pipeline-cron.yml`)
- **Frequency**: Every 30 minutes (cron: `*/30 * * * *`)
- **Benefits**:
  - Integrated with main repository
  - Built-in logging and artifact storage
  - No external infrastructure dependency
  - Visible in GitHub UI

This migration **reinforces** the need for separation: FOR's automation requirements are substantial enough to warrant dedicated CI/CD workflow.

---

## 8. Conclusion

### Summary

The FOR pipeline is separate because it solves a **fundamentally different problem**:

- **ECON/MAT**: "Generate report from structured data"
- **FOR**: "Monitor external source, ingest drafts, publish automatically"

This is not duplication—it's proper architectural separation.

### Recommendations

1. **Keep pipelines separate** ✅
   - Current architecture is sound
   - Separation improves maintainability

2. **Document the distinction** ✅
   - Update CLAUDE.md to clarify input source differences
   - Add flowchart showing two pipeline types

3. **Consider generalization (Future)**
   - If MAT or ECON need draft ingestion in future
   - Extract common "draft watcher" pattern
   - Create shared library (not forced unification)

### Stakeholder Communication

For board/analysts asking "Why two pipelines?", use this analogy:

> **ECON/MAT** is like a **factory** (we control the production line)  
> **FOR** is like a **delivery service** (we wait for packages to arrive)

Different operational models require different automation approaches.

---

## Appendix: Key Files

| Component | File | Purpose |
|-----------|------|---------|
| ECON/MAT Orchestrator | `scripts/pipeline/orchestrator.py` | Main generation pipeline |
| FOR Ingestion | `scripts/pipeline/ingest_for.py` | GDrive watcher + processor |
| FOR Automation | `.github/workflows/for-pipeline-cron.yml` | Cron trigger (30 min) |
| FOR Setup Guide | `doc/FOR_PIPELINE_GITHUB_ACTIONS_SETUP.md` | Deployment docs |
| State Tracker | `scripts/pipeline/output/_for_processed.json` | Processed files log |

---

**Report Prepared By**: CRO Agent  
**Review Status**: Ready for Board Review  
**Next Actions**: None (documentation complete)
