# Contributing to Blockchain Economics Lab

## Branch Strategy

```
main          ← Production (auto-deploys to Vercel)
  └── develop ← Integration branch
       ├── feat/xxx     ← New features
       ├── fix/xxx      ← Bug fixes
       ├── content/xxx  ← Research content
       └── ops/xxx      ← Operations tasks
```

## Workflow

1. Create issue using appropriate template (Research/Feature/Bug/Ops)
2. Create branch from `develop`: `git checkout -b feat/your-feature`
3. Commit with conventional commits: `feat:`, `fix:`, `docs:`, `ops:`, `content:`
4. Push and create PR against `develop`
5. Pass CI checks (lint, typecheck, test, build)
6. Get review from assigned agent/reviewer
7. Merge to `develop`, then `develop` → `main` for release

## Agent Assignment (Paperclip Framework)

Every issue and PR must include:
- **Assigned Agent** from ORGANIZATION.md
- **Goal Ancestry** tracing back to company mission
- **Issue ID** with department prefix (RES-, OPS-, MKT-, STR-)

## Commit Convention

```
<type>(<scope>): <subject>

[optional body]

Agent: <agent-id>
Refs: #<issue-number>
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `ops`, `content`

## Code Standards

- TypeScript strict mode
- All components must support i18n (7 languages)
- Payment code requires unit tests
- API routes require error handling and logging
