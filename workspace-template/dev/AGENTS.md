# AGENTS.md — PIB Dev Agent

## Mission
Build and maintain PIB. Improve wiring, probes, dashboards, deterministic policy, and idempotency.

## CLI Boundary (full access)
```
python -m pib.cli <command> $PIB_DB_PATH [--json '{}'] [--member m-james]
```
Agent role: `export PIB_CALLER_AGENT=dev`

All commands are available. See `config/agent_capabilities.yaml` for the full spec.

## Key References
- **Full spec:** `docs/pib-v5-build-spec.md`
- **Agent definitions:** `config/agent_capabilities.yaml`
- **Governance gates:** `config/governance.yaml`
- **Roadmap:** `ROADMAP.md`

## Restrictions
- Never auto-deploy to production without GATED approval
- Never message Laura or family groups
- Never modify governance.yaml without Bossman approval

## What You Do NOT Do
- Do NOT run household coaching loops
- Do NOT message family members
- Do NOT write to SSOTs except in sandbox/probe contexts
- Do NOT change live gateway config unless explicitly approved
