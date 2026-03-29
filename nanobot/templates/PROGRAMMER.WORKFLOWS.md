# Programmer Workflows

## Delivery Loop (Design → Build → Test → Review)
- Clarify task goal, constraints, and interfaces.
- Design minimally: data flow, failure modes, edge cases.
- Implement smallest safe change; prefer feature flags when possible.
- Tests: focused unit/behavioral; update fixtures; add regression where riskier.
- Review: self-review checklist (diff scan, tests, logging/errors, docs).
- Release: note rollout/rollback steps.

## Agile Execution
- Break work into thin slices; timebox spikes; surface blockers early.
- Maintain RAD log (Risks/Assumptions/Decisions).
- Standup notes template: Yesterday / Today / Blockers / Risks.

## Quality & Safety
- Guardrails: workspace restriction, shell allowlists, dependency minimalism.
- Observability: logging hotspots and degraded modes.
- Post-change verification: targeted tests first, then suite.
