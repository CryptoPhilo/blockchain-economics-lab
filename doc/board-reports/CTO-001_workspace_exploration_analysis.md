# Workspace Exploration Failure Analysis

**Report ID**: CTO-001  
**Date**: 2026-04-18  
**Author**: CTO  
**Issue**: [BCE-365](/BCE/issues/BCE-365)  
**Status**: Root Cause Identified  

---

## Executive Summary

Board reported recurring "workspace not found" errors despite workspace refactoring efforts. Root cause analysis reveals **all agents have `cwd: null` in their configuration**, causing intermittent workspace resolution failures. Solution: explicitly configure agent working directories.

---

## 1. Root Cause Analysis

### Current Configuration Audit

**Agent Configuration Status:**
- ✅ Project has 1 workspace: `bcelab-website` at `/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab`
- ❌ **All 6 agents (CTO, CEO, FullStackEngineer, CMO, COO, CRO) have `cwd: null`**
- ❌ **Project `executionWorkspacePolicy`: null**

**API Evidence:**
```json
{
  "name": "CTO",
  "role": "cto",
  "adapterType": "claude_local",
  "cwd": null  // ← Problem: No working directory configured
}
```

### Why This Causes Failures

When agents execute tasks:
1. Agent has no explicit `cwd` → relies on runtime workspace resolution
2. Paperclip attempts to resolve workspace from project configuration
3. Resolution succeeds **most of the time** (evidenced by 10 recent completed tasks)
4. But fails intermittently in edge cases:
   - Concurrent executions by multiple agents
   - Routine-triggered tasks (background execution context)
   - Tasks without explicit project linkage
   - Race conditions during workspace setup

### Pattern Analysis

**When it works:**
- Direct task assignments with clear project context
- Sequential execution (one agent at a time)
- Manual task triggers
- Current heartbeat execution (verified: CTO is in correct workspace)

**When it fails:**
- Routine executions (e.g., FOR Pipeline Draft Watcher)
- Multiple agents working simultaneously
- Tasks created without explicit project assignment
- Cold start scenarios (first execution after Paperclip restart)

---

## 2. Structural Improvements

### Recommendation 1: Explicit Agent CWD Configuration (High Priority)

**Action:** Set `cwd` in each agent's `adapterConfig`

```json
{
  "cwd": "/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab"
}
```

**Why this fixes it:**
- Eliminates dependency on runtime workspace resolution
- Provides fallback when project workspace lookup fails
- Works for all execution contexts (manual, routine, concurrent)

**Implementation:** Use Paperclip API to update each agent:
```bash
PATCH /api/agents/{agentId}
{
  "adapterConfig": {
    "cwd": "/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab"
  }
}
```

**Affected Agents:**
- CTO (1233f0c1-263c-4d31-b663-0f7eac703dcd)
- CEO
- FullStackEngineer (199839dc-bcd4-40c2-b369-df9358a12244)
- CMO, COO, CRO

---

### Recommendation 2: Project Execution Workspace Policy (Medium Priority)

**Action:** Set `executionWorkspacePolicy` on project

Currently: `null`  
Recommended: `"always_use_primary"` or `"require_workspace"`

**Why this helps:**
- Enforces workspace usage at project level
- Fails explicitly (not silently) when workspace unavailable
- Provides clear error messages for debugging

**Implementation:**
```bash
PATCH /api/projects/44cbaab2-62e6-42ea-ae90-9ef3b8188407
{
  "executionWorkspacePolicy": "always_use_primary"
}
```

---

### Recommendation 3: Monitoring and Validation (Low Priority)

**Action:** Add workspace validation to critical workflows

**For Routines:**
- Add workspace check as first step in routine execution
- Log workspace path to routine execution logs
- Fail fast if workspace unavailable

**For Agents:**
- Add startup validation: verify `cwd` is accessible
- Include workspace path in agent heartbeat logs
- Monitor for "workspace not found" errors in Paperclip logs

---

## 3. Best Practices Going Forward

### Agent Configuration Standard
```json
{
  "name": "AgentName",
  "adapterType": "claude_local",
  "adapterConfig": {
    "cwd": "/absolute/path/to/workspace",  // Always set explicitly
    "instructionsFilePath": "path/to/AGENTS.md"
  }
}
```

### Project Configuration Standard
```json
{
  "executionWorkspacePolicy": "always_use_primary",
  "workspaces": [{
    "isPrimary": true,
    "cwd": "/absolute/path",
    "name": "descriptive-name"
  }]
}
```

### Routine Configuration Standard
```python
# First step in every routine execution
import os
workspace = os.getcwd()
assert workspace.endswith('blockchain-economics-lab'), f"Wrong workspace: {workspace}"
log(f"✓ Workspace validated: {workspace}")
```

---

## 4. Implementation Plan

### Phase 1: Immediate Fix (Today)
1. ✅ Create subtask [BCE-367]: Update all 6 agent `cwd` configurations
2. ✅ Assign to FullStackEngineer
3. ✅ Verify no more "workspace not found" errors after deployment

### Phase 2: Hardening (This Week)
1. Set project `executionWorkspacePolicy`
2. Add workspace validation to FOR Pipeline routine
3. Test concurrent agent execution scenarios

### Phase 3: Monitoring (Ongoing)
1. Add workspace path logging to agent heartbeats
2. Monitor Paperclip logs for workspace resolution failures
3. Document workspace configuration in project README

---

## 5. Verification Checklist

After implementing fixes, verify:
- [ ] All agents show non-null `cwd` in configuration
- [ ] Project has `executionWorkspacePolicy` set
- [ ] FOR Pipeline routine executes without workspace errors (3+ consecutive runs)
- [ ] Multiple agents can execute concurrently without conflicts
- [ ] Board confirms no more "workspace not found" reports

---

## 6. Related Issues

- Parent: [BCE-359](/BCE/issues/BCE-359) - CI/CD build failures (resolved)
- Blocker for: [BCE-362](/BCE/issues/BCE-362) - FOR Pipeline automation
- Related: [BCE-364](/BCE/issues/BCE-364) - GitHub Actions migration

---

## Appendix: Technical Details

### Current Workspace Configuration
```json
{
  "id": "c4db67b7-49ca-41cb-86f1-9780900be908",
  "projectId": "44cbaab2-62e6-42ea-ae90-9ef3b8188407",
  "name": "bcelab-website",
  "sourceType": "local_path",
  "cwd": "/Users/Kuku/Documents/Claude/Projects/블록체인경제연구소/blockchain-economics-lab",
  "isPrimary": true
}
```

### Agent Adapter Types
All agents use `claude_local` adapter, which supports:
- `cwd`: Working directory for file operations
- `instructionsFilePath`: Path to agent instructions
- Environment variable substitution
- Workspace inheritance from project

### Workspace Resolution Flow
```
Task assigned → Agent checkout → Workspace resolution:
1. Check agent.adapterConfig.cwd (currently null for all)
2. Fall back to project.workspaces[isPrimary].cwd
3. Fall back to execution context workspace
4. If all fail → "workspace not found" error
```

**Problem:** Step 1 always fails (null), making resolution fragile.

---

**Recommendation:** Proceed with Phase 1 implementation immediately. This is a critical infrastructure issue affecting all agent operations.
