---
name: test-driven
description: Write tests before implementation. Follow TDD cycle: Red-Green-Refactor. Ensure comprehensive coverage including edge cases.
compatibility: opencode
metadata:
  audience: be, fe
  workflow: development
---

# Test-Driven Development Skill

## TDD Cycle
1. 🔴 RED: Write a failing test for the desired behavior
2. 🟢 GREEN: Write minimal code to make the test pass
3. 🔵 REFACTOR: Clean up code while keeping tests green

## Coverage requirements
- Happy path
- Error states (each error type)
- Edge cases (empty, null, boundary values, duplicates)
- State transitions (if applicable)
- Concurrency (if applicable)

## Test structure
For each function/module:
  describe('function name')
    it('handles happy path')
    it('handles error: specific error')
    it('handles edge case: specific edge')

## Rules
- Test behavior, not implementation
- One assertion per test (or logical group)
- Use descriptive test names
- No test duplication
