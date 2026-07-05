---
name: code-review
description: Review code changes for correctness, security, performance, maintainability, and test coverage. Provide prioritized actionable feedback.
compatibility: opencode
metadata:
  audience: be, fe
  workflow: quality
---

# Code Review Skill

## Scope
Review code in any language for common issues.

## Checklist
- Correctness: does code do what it claims?
- Edge cases: null, empty, error, boundary states handled?
- Security: injection, XSS, auth bypass, secrets exposure?
- Performance: N+1 queries, unnecessary allocations, sync bottlenecks?
- Maintainability: clear naming, single responsibility, no dead code?
- Testing: are there tests? Do they cover edge cases and failure modes?
- Consistency: follows project conventions (naming, structure, patterns)?

## Priority levels
- 🔴 BLOCKING: incorrect behavior, security hole, data loss
- 🟡 MAJOR: maintainability concern, missing edge case
- 🔵 MINOR: style nit, optional improvement

## Protocol
1. Read changed files
2. Run through checklist
3. Prioritize findings
4. Provide code examples for each fix
5. Summarize in report format
