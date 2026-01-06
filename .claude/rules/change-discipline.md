# Change Discipline

Rules for how to approach changes to the codebase.

## Before Writing Code

1. **Look for existing patterns**: Before writing new code, look for an existing pattern and match it.
2. **Check roadmap**: Review `ROADMAP.md` before starting work.
3. **Check PRDs**: Review existing PRDs in `.claude/prds/` before implementing new features.
4. **Understand the code**: Never propose changes to code you haven't read. Read first, then modify.

## Core Principles

- Optimise for clarity, maintainability, and consistency with existing project patterns.
- Preserve existing public APIs and behaviours unless explicitly instructed otherwise.
- Prefer small, testable units. Avoid cleverness.

## Avoid Over-Engineering

Only make changes that are directly requested or clearly necessary. Keep solutions simple and focused.

### Don't Add Unrequested Features

```python
# Asked to fix a bug in calculate_total()
# Bad: Also "cleaned up" surrounding code, added docstrings, refactored
# Good: Just fixed the bug

# Asked to add a simple feature
# Bad: Added configuration options, feature flags, extensibility points
# Good: Implemented the minimal feature that solves the problem
```

### Don't Add Speculative Code

- Don't add error handling for scenarios that can't happen
- Don't add feature flags for hypothetical future requirements
- Don't create abstractions for one-time operations
- Three similar lines of code is better than a premature abstraction

### Don't Add Backwards Compatibility Hacks

- Don't rename unused variables to `_var`
- Don't re-export removed types for backwards compatibility
- Don't add `# removed` comments for deleted code
- If something is unused, delete it completely

## Breaking Changes

If a change could be breaking:

1. Propose a non-breaking alternative first
2. Explain the trade-offs of each approach
3. Get explicit approval before proceeding with breaking changes

## Planning for Extensibility

When implementing a feature that might be related to planned future work:

1. **Check for planned features**: Look in `ROADMAP.md` and PRDs
2. **Design for extensibility upfront**: If a planned feature would benefit from shared abstractions, create them now
3. **Don't bodge solutions**: If implementing properly requires changes outside the immediate scope, stop and ask first
4. **Propose architectural changes early**: If a different architecture would be better, propose it before writing code

## When Uncertain

- Ask a targeted question instead of guessing at conventions
- Prefer asking to assuming
- It's better to clarify than to implement the wrong thing

## Security Considerations

Be careful not to introduce security vulnerabilities:

- Command injection
- XSS (Cross-Site Scripting)
- SQL injection
- Other OWASP top 10 vulnerabilities

If you notice insecure code, fix it immediately.

## After Making Changes

### Validation

Run all checks before considering work complete:

```bash
make check  # Runs lint, format, types, coverage
```

### Documentation

- Update `README.md` to reflect new or modified behaviour
- Update `ROADMAP.md` to reflect completed features or progress

### Self-Check

Before submitting:

- Confirm imports are correct and minimal
- Confirm types line up (no obvious mypy failures)
- Confirm tests match the behaviour and run in isolation
- Confirm no secrets, tokens, or private data are introduced
