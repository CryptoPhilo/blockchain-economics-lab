---
report_id: OPS-004
date: 2026-04-17
type: board_report
author: COO
classification: INTERNAL - CONFIDENTIAL
title: "프롬프트 및 에이전트 지시사항 티켓화 감사 보고서"
references:
  - BCE-202 (Operations audit task)
  - BCE-34 (Previous prompt audit 2026-04-15)
  - BCE-78 (Agent instruction audit)
---

# OPS Board Report OPS-004
## 프롬프트 및 에이전트 지시사항 티켓화 감사 보고서

> **Report ID**: OPS-004 | **Date**: 2026-04-17 | **Author**: COO
> **Classification**: INTERNAL — CONFIDENTIAL

---

## 1. 요약 (Executive Summary)

Conducted comprehensive audit of all active prompts and agent-to-agent instructions to verify ticketing coverage. **Finding: Most agent instructions exist but are NOT individually ticketed.** The instructions are maintained as configuration files but lack dedicated tracking issues for creation, updates, and governance. While Gemini Deep Research prompts have adequate issue coverage, core agent instruction files (HEARTBEAT.md, SOUL.md, AGENTS.md) have no corresponding governance tickets.

---

## 2. 현황 분석 (Analysis)

### 2.1 Active Agent Instructions Inventory

Reviewed instruction files for all 6 company agents:

#### CEO (606a7f2d-5fea-43f4-b3a8-fd670445c082)
**Location:** `/companies/7f3e87fc-1d55-457d-98a9-dd1c3f5c01eb/agents/606a7f2d-5fea-43f4-b3a8-fd670445c082/instructions/`

- **HEARTBEAT.md** — 73 lines
  - Heartbeat execution checklist
  - Local planning procedures
  - Approval follow-up workflow
  - Assignment and checkout procedures
  - Delegation rules
  - Fact extraction protocol
  
- **SOUL.md** — 34 lines
  - CEO persona definition
  - Strategic posture guidelines
  - Voice and tone standards
  - Decision-making framework
  
- **AGENTS.md** — 55 lines
  - CEO delegation workflow
  - Department routing rules (CTO/CMO/CRO/COO)
  - Personal vs delegated responsibilities
  - Memory and planning requirements
  
- **TOOLS.md** — 4 lines
  - Placeholder for tool documentation (currently empty)

**Ticketing Status:** ❌ No dedicated issues for these instruction files

---

#### CTO (1233f0c1-263c-4d31-b663-0f7eac703dcd)
**Location:** `/companies/7f3e87fc-1d55-457d-98a9-dd1c3f5c01eb/agents/1233f0c1-263c-4d31-b663-0f7eac703dcd/instructions/`

- **AGENTS.md** — 38 lines
  - CTO delegation rules to engineers
  - Technical leadership responsibilities
  - Code review and architectural decisions
  - Escalation procedures

**Ticketing Status:** ❌ No dedicated issues

---

#### CRO (94f2a81f-bd8c-4491-9068-cd4d938b006d)
**Location:** `/companies/7f3e87fc-1d55-457d-98a9-dd1c3f5c01eb/agents/94f2a81f-bd8c-4491-9068-cd4d938b006d/instructions/`

- **AGENTS.md** — 8 lines
  - CRO research pipeline responsibilities
  - Research analyst coordination
  - Quality review and publication

**Ticketing Status:** ❌ No dedicated issues

---

#### CMO (b16d82aa-16ac-44f2-a2bd-d284d5e99c0d)
**Location:** `/companies/7f3e87fc-1d55-457d-98a9-dd1c3f5c01eb/agents/b16d82aa-16ac-44f2-a2bd-d284d5e99c0d/instructions/`

- **AGENTS.md** — 8 lines
  - CMO marketing strategy responsibilities
  - Content marketing and growth
  - Community building and GTM execution

**Ticketing Status:** ❌ No dedicated issues

---

#### COO (af0ff624-b2c6-438a-b52c-2436edd7a04b)
**Location:** `/companies/7f3e87fc-1d55-457d-98a9-dd1c3f5c01eb/agents/af0ff624-b2c6-438a-b52c-2436edd7a04b/instructions/`

- **AGENTS.md** — 4 lines
  - Basic Paperclip agent workflow instructions
  - Work progression and escalation

**Ticketing Status:** ❌ No dedicated issues  
**Gap:** Minimal content compared to other C-level agents

---

#### FullStackEngineer (199839dc-bcd4-40c2-b369-df9358a12244)
**Location:** Not found

**Status:** ❌ **No instruction files exist**  
**Gap:** Critical — engineer hired but has no guidance documentation

---

### 2.2 Agent-to-Agent Communication Protocols

**CEO Delegation Chain:**
- CEO → CTO (code, bugs, features, infrastructure, technical tasks)
- CEO → CMO (marketing, content, social media, growth, devrel)
- CEO → CRO (research pipeline, analyst coordination, quality review)
- CEO → COO (operations, publishing pipeline, data infrastructure, QA)

**CTO Delegation Chain:**
- CTO → FullStackEngineer (implementation work, frontend/backend development)

**Escalation Chain (via chainOfCommand):**
- All C-level reports → CEO
- Engineers → CTO → CEO
- Standard escalation for blockers and cross-team issues

**Ticketing Status:** ❌ No dedicated issues for these protocols. Embedded in AGENTS.md files but not tracked as governance/process issues.

---

### 2.3 Research Prompts Audit

**Gemini Deep Research Prompt:**
- **Status:** Actively being improved via research pipeline
- **Related Issues:**
  - [BCE-89](/BCE/issues/BCE-89) — "딥리서치 프롬프트 개선방안 검토" (done)
  - [BCE-98](/BCE/issues/BCE-98) — "개선된 프롬프트 결과 비교" (done)
  - [BCE-104](/BCE/issues/BCE-104) — "v3.0 파이프라인 설계: Gemini Deep Research 보완 전략" (done)
- **Ticketing Status:** ✅ Adequately tracked
- **Prompt Location:** Embedded in issue descriptions (BCE-89)
- **Content:** Detailed forensic analyst persona, analysis philosophy, 7-step research methodology

---

### 2.4 Previous Audit History

**Similar audits conducted:**
- [BCE-34](/BCE/issues/BCE-34) — "프롬프트/에이전트 지시 티켓화 점검" (done, 2026-04-15)
- [BCE-78](/BCE/issues/BCE-78) — "에이전트 간 지시사항 티켓화 감사" (done)
- [BCE-169](/BCE/issues/BCE-169), [BCE-76](/BCE/issues/BCE-76), [BCE-68](/BCE/issues/BCE-68), [BCE-58](/BCE/issues/BCE-58), [BCE-52](/BCE/issues/BCE-52), [BCE-44](/BCE/issues/BCE-44) — "티켓 생성 점검" (all done)

**Finding:** Recurring pattern of audit requests suggests systemic ticketing gap remains unresolved despite multiple reviews.

---

## 3. 핵심 발견사항 (Key Findings)

### Critical Gaps (Priority 0)

1. **FullStackEngineer missing instructions** — **High priority**
   - Agent exists (hired 2026-04-16) and is assigned work
   - No instruction files exist
   - Risk: Inconsistent behavior and unclear delegation boundaries

2. **COO instructions underdeveloped** — **Medium priority**
   - Current AGENTS.md is only 4 lines (vs 38-73 for other C-level agents)
   - Missing: operations workflow details, delegation rules, tool usage guidelines
   - Risk: Operational inefficiency and unclear COO scope

### Systemic Gaps (Priority 1)

3. **No ticketing for agent instruction creation/updates**
   - Agent instruction files exist as configuration artifacts
   - No issues track their creation, review cycles, or version control
   - Changes are made ad-hoc without formal approval workflow
   - Impact: Governance risk as team scales

4. **Agent-to-agent protocols not tracked separately**
   - Communication protocols embedded in AGENTS.md files
   - No centralized governance issue for cross-agent workflow rules
   - Risk: Protocol drift as agents are added/modified

5. **No instruction maintenance lifecycle**
   - No scheduled reviews of instruction file accuracy
   - No deprecation process for outdated guidelines
   - No validation that instructions match current practices
   - Impact: Instructions may diverge from actual agent behavior

---

## 4. 권고사항 (Recommendations)

### Immediate Actions (Priority 0)

**Recommendation 1: Create FullStackEngineer instructions**
- **Owner:** CTO
- **Timeline:** Within 48 hours
- **Action:** Draft AGENTS.md with delegation boundaries, tech stack, and escalation rules
- **Reference:** Use CTO AGENTS.md as template
- **Suggested Issue:** Create BCE-XXX for tracking

**Recommendation 2: Expand COO instructions**
- **Owner:** CEO (to review and approve COO scope expansion)
- **Timeline:** Within 1 week
- **Action:** Expand COO AGENTS.md to include:
  - Operations workflow details
  - Tool usage guidelines (Gmail MCP, Resend, exec-report, gdrive-upload)
  - Delegation to report editors and data engineers
  - QA process ownership
- **Suggested Issue:** Create BCE-XXX for tracking

### Process Improvements (Priority 1)

**Recommendation 3: Create instruction governance framework**
- **Owner:** CEO
- **Timeline:** Within 2 weeks
- **Action:**
  - Define instruction file lifecycle (create → review → update → deprecate)
  - Establish approval workflow for instruction changes
  - Set quarterly review schedule for all AGENTS.md files
  - Create version control policy
- **Suggested Issue:** Create BCE-XXX for tracking

**Recommendation 4: Document cross-agent protocols centrally**
- **Owner:** COO
- **Timeline:** Within 1 week
- **Action:**
  - Extract delegation chains from individual AGENTS.md files
  - Create company-wide protocol reference document
  - Link protocols to org chart and chainOfCommand structure
  - Publish in doc/ directory
- **Suggested Issue:** Create BCE-XXX for tracking

**Recommendation 5: Migrate to issue-driven instruction updates**
- **Owner:** CEO
- **Timeline:** Implement for all future changes
- **Action:**
  - Require new issue for any AGENTS.md changes
  - Include diff, rationale, and approval before merge
  - Link instruction changes to agent performance issues
  - Track in Paperclip as governance work
- **Suggested Issue:** Create BCE-XXX for tracking

---

## 5. 다음 단계 (Next Steps)

### Board Decision Required

**Question:** "프롬프트와 에이전트 간 지시가 모두 티켓화 되었는지?"

**Answer:** **No.** Agent instructions and protocols exist as configuration files but are **not ticketed**. While the Gemini Deep Research prompt has dedicated tracking issues, the core agent instruction files (HEARTBEAT.md, SOUL.md, AGENTS.md) have no corresponding issues for creation, updates, or governance.

**Root Cause:** Instructions treated as static configuration rather than living governance artifacts.

**Impact Assessment:**
- **Immediate Risk:** Low (instructions exist and function)
- **Medium-term Risk:** Medium (governance risk as team scales and protocols evolve without formal change control)

### Decision Options for Board

The board should decide on governance approach:

**(A) Accept current state and only ticket future instruction changes**
- Pros: No retroactive work, clean going forward
- Cons: No audit trail for existing instructions
- Recommended for: Lean teams prioritizing speed

**(B) Retroactively create governance issues for existing instruction files**
- Pros: Complete audit trail, formal review opportunity
- Cons: Administrative overhead, potential churn
- Recommended for: Teams requiring full compliance documentation

**(C) Implement lightweight version control (git blame + changelog) without full ticketing**
- Pros: Balance between audit trail and overhead
- Cons: Not integrated with Paperclip workflow
- Recommended for: Teams with strong git discipline

### Immediate Follow-up

Regardless of board decision on retroactive ticketing:
1. **FullStackEngineer instructions** must be created immediately (blocker for productive work)
2. **COO instructions** should be expanded (current gap affects operational efficiency)
3. **Instruction governance framework** should be defined (prevents future audit requests)

### Timeline

- **Week 1 (Apr 17-23):** Create FullStackEngineer instructions, expand COO instructions
- **Week 2 (Apr 24-30):** Board decision on governance approach, implement chosen option
- **Week 3 (May 1-7):** Create central protocol documentation
- **Ongoing:** Quarterly instruction file reviews (starting Q3 2026)

---

**Report compiled by:** COO (af0ff624-b2c6-438a-b52c-2436edd7a04b)  
**Audit duration:** 1 heartbeat  
**Files reviewed:** 8 instruction files across 6 agents  
**Issues searched:** 224 company issues  
**Related Issue:** [BCE-202](/BCE/issues/BCE-202)

---
*End of Report — OPS-004*
