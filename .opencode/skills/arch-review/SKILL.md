---
name: arch-review
description: Review system architecture for coupling, cohesion, single responsibility, and extensibility. Focus on LLM pipeline and provider abstraction.
compatibility: opencode
metadata:
  audience: sa, be
  workflow: planning, review
---

# Architecture Review

## Focus areas
1. Module coupling — do services import each other directly?
2. Provider abstraction — can a new LLM provider be added without changing pipeline?
3. Pipeline cohesion — does each stage have ONE responsibility?
4. Data flow — is the data transformation chain explicit?
5. Error boundaries — what happens when stage 3 crashes mid-way?

## Review checklist
- [ ] Each service module has single responsibility
- [ ] Pipeline stages are independent and testable in isolation
- [ ] LLM provider selection is configurable, not hardcoded
- [ ] Database session lifecycle is managed (not leaked)
- [ ] File I/O has cleanup on failure
- [ ] Async chains handle cancellation properly
- [ ] Configuration is externalized (env/config file)

## Pipeline-specific
For LLM pipelines (5-stage etc):
- Each stage output should be validatable independently
- Stage failure should be catchable without losing prior work
- Audit stage should have access to ALL prior stage outputs
- Token usage and cost should be trackable per stage
