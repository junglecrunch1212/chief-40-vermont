# PIB v5 Bootstrap Readiness — Full Capability Task Plan

This plan defines the implementation tasks required to move PIB from current state to production-grade launch readiness on a Mac mini, with full family profiles and connected services.

## Exit Criteria (Definition of Done)

PIB is launch-ready when all are true:
- Mac mini bootstrap is reproducible and idempotent for production and staging.
- OAuth/key onboarding is complete for Anthropic, Google (Console, Gmail, Calendar, Drive), Twilio, BlueBubbles.
- Inbound + outbound messaging works end-to-end with delivery receipts and retries.
- Tasks, Calendar, and Finance run as SSOTs with deterministic ingest/sync/reconciliation.
- Multi-user auth with role-based access and per-member privacy isolation is enforced.
- Backups, observability, runbooks, and restore drills are operational.

---

## P0 — Foundation, Security, and Bootstrap Hardening

### T-001: Environment and Secrets Model
- Define required env vars and secret provenance by service.
- Add startup validation that fails fast if required secrets are missing in non-dev mode.
- Add secret-rotation metadata (last rotated, owner, expiry target).
- Add encrypted-at-rest secret storage guidance for Mac deployment.
- **DoD:** service refuses startup on missing critical secrets; `/health` reports secrets posture without exposing values.

### T-002: Bootstrap Script Production Mode
- Extend `scripts/bootstrap.sh` with:
  - mode flags (`--dev`, `--prod`, `--noninteractive`)
  - preflight checks (python/node/sqlite versions, disk space, write permissions)
  - secure file permissions (`.env`, key files, logs, db)
  - post-bootstrap smoke tests.
- Add rollback guidance if bootstrap step fails.
- **DoD:** one-command production bootstrap with deterministic output and failure diagnostics.

### T-003: AuthN/AuthZ Architecture
- Implement user login (OIDC or managed identity provider).
- Create user-account table(s), session management, passwordless/2FA policy if needed.
- Map identity to `common_members` and enforce per-request membership context.
- Add RBAC (parent, child, admin, viewer, service-account).
- **DoD:** every `/api/*` request has authenticated principal, role checks, and scoped data access.

### T-004: Webhook Security Hardening
- Enforce fail-closed signature/secret checks for Twilio/BlueBubbles/Siri/Sheets in production.
- Add replay-protection windows and nonce/idempotency checks.
- Add per-source IP allowlist support where feasible.
- **DoD:** invalid webhook attempts are rejected, audited, and rate-limited.

### T-005: Privacy and PII Guardrails
- Formalize redaction and privilege fences at read-layer boundaries.
- Add canary tests to assert privileged data never enters LLM context.
- Add PII/PHI-safe logging policy and sanitizer middleware.
- **DoD:** privacy policy enforced by code paths and tests, not prompts.

---

## P0 — Core Integrations (Google, Twilio, BlueBubbles, Anthropic)

### T-010: Google Cloud Project Setup Automation
- Define setup checklist/script for APIs:
  - Gmail API
  - Calendar API
  - Drive API
  - Sheets API
- Create OAuth consent screen and scopes set (least privilege).
- Add credential import flow (service account and/or OAuth refresh token storage).
- **DoD:** documented and script-assisted Google project onboarding reproducible in <30 min.

### T-011: Google OAuth Token Lifecycle
- Implement OAuth start/callback/refresh/revoke flows.
- Persist tokens securely, with rotation and revocation support.
- Add token health endpoint and renewal alerts.
- **DoD:** tokens auto-refresh; expired/revoked tokens produce actionable diagnostics.

### T-012: Gmail Adapter (Read + Incremental Sync)
- Implement initial backfill and incremental sync by history ID/time cursor.
- Parse metadata/snippets/threads and map to `ops_comms` with idempotency.
- Add label mapping for triage states.
- **DoD:** new Gmail messages appear in inbox domain within SLA target.

### T-013: Google Calendar Adapter (Read-Only SSOT Feed)
- Implement calendar discovery, source classification proposal, and confirmation flow.
- Add incremental and full resync jobs with cursor checkpointing.
- Respect privacy tier mapping (`full`, `privileged`, `redacted`).
- **DoD:** calendar state powers schedule/whatNow with stale detection and degradation behavior.

### T-014: Google Drive Adapter (Reference + Artifact Ingest)
- Implement folder/file listing, metadata capture, optional text extraction pipeline.
- Link relevant artifacts to tasks/items/memory entries.
- Add ACL-aware visibility filtering.
- **DoD:** Drive docs can be referenced in workflows without violating access boundaries.

### T-015: Twilio Inbound/Outbound Full Delivery
- Complete outbound send adapter with status callbacks.
- Persist provider message SID, delivery status, error reason, retry count.
- Implement retry/backoff and dead-letter handling.
- **DoD:** reply from console reaches recipient and status is observable in UI and DB.

### T-016: BlueBubbles Inbound/Outbound Full Delivery
- Implement outbound send via BlueBubbles bridge with ack/status persistence.
- Add reconnect/error handling if bridge unavailable.
- **DoD:** iMessage channel parity with Twilio for core comms workflows.

### T-017: Anthropic Reliability and Budget Controls
- Add model failover policy (primary/fallback IDs), timeout/retry policy.
- Track token usage and budget alerts at member/domain granularity.
- Add prompt/context guardrails and truncation observability.
- **DoD:** controlled LLM spend and graceful fallback on provider issues.

---

## P0 — SSOT Completion (Tasks, Calendar, Finance)

### T-020: Tasks SSOT Determinism Audit
- Verify all task mutations are append-only or auditable state transitions.
- Add invariants tests for recurrence, undo, and idempotency.
- **DoD:** task store behavior deterministic and recoverable.

### T-021: Calendar SSOT Completion
- Ensure all schedule surfaces read from canonical classified events + daily state tables.
- Add stale-source indicators and “last sync age” telemetry.
- **DoD:** schedule pages and `whatNow()` remain safe under partial outages.

### T-022: Finance Source Adapter + Reconciliation
- Implement finance ingestion connector(s) and normalization pipeline.
- Add deduping, merchant/category mapping, and human override flow.
- Add reconciliation states (new/matched/ignored/disputed).
- **DoD:** finance SSOT supports accurate budget context and transaction querying.

### T-023: Cross-Source Extraction to SSOT Workflow
- Standardize extraction proposals from comms into task/event/transaction proposals.
- Add confidence thresholds, approval UX, and audit trail.
- **DoD:** message-derived items enter SSOT only through deterministic approval gates.

---

## P1 — Family Profiles, UX, and Access Separation

### T-030: User Profile Domain Model
- Add profile preferences: channels, quiet hours, digest mode, coaching style, permissions.
- Separate identity account from household member entity where appropriate.
- **DoD:** each family member has a first-class profile with independent settings.

### T-031: Login UX + Session Management
- Implement login/logout/session timeout/re-auth flows.
- Add account recovery and admin invitation flows.
- **DoD:** secure and usable multi-user login lifecycle.

### T-032: View-Level Privacy Enforcement
- Enforce per-member visibility in APIs and frontend rendering.
- Add tests for cross-profile data leakage attempts.
- **DoD:** one member cannot access restricted items of another.

### T-033: Family Console Role Experiences
- Parent dashboard, child-safe view, optional coparent constraints.
- Explicit legal/privacy boundary handling for privileged calendars and notes.
- **DoD:** role-tailored UX aligns to policy and permissions.

---

## P1 — Observability, Ops, and Reliability

### T-040: Structured Logging + Correlation IDs
- Add request IDs and job IDs across API, scheduler, adapters.
- Emit machine-parsable events for ingest/sync/send failures.
- **DoD:** any failure traceable end-to-end in logs.

### T-041: Health and Status Panel Completion
- Extend `/health` to include integration-specific checks:
  - token freshness
  - last successful sync ages
  - queue depth + dead-letter counts
  - DB integrity checks.
- **DoD:** operator can diagnose degraded state from one panel.

### T-042: Backup/Restore Production Validation
- Hourly/daily backup verification + checksum catalog.
- Quarterly restore drill script and runbook.
- **DoD:** restore success proven, not assumed.

### T-043: Migration and Rollback Safety
- Add migration prechecks, backup-before-migrate, and rollback docs.
- **DoD:** schema changes are reversible with tested procedure.

---

## P1 — Deployment and Networking

### T-050: Launchd Service Hardening
- Ensure launchd config references immutable runtime paths and env.
- Add automatic restart policy with crash-loop protection.
- **DoD:** stable daemon behavior on reboot and failures.

### T-051: Remote Access Security
- Cloudflare tunnel (or equivalent) with strict access policies.
- TLS cert automation and domain hardening.
- **DoD:** remote access without exposing raw service endpoints.

### T-052: CORS/CSRF and API Security Controls
- Lock `PIB_CORS_ORIGINS` for production origins.
- Add CSRF defenses if browser sessions are cookie-based.
- **DoD:** browser attack surface reduced to acceptable baseline.

---

## P2 — Capability Completeness and Quality

### T-060: End-to-End Test Matrix
- Build E2E tests for all core service integrations (mock + live test mode).
- Add synthetic fixture datasets for tasks/calendar/finance/comms.
- **DoD:** CI gate verifies critical flows before release.

### T-061: Performance and Capacity Validation
- Load test API, scheduler jobs, and ingestion bursts.
- Define SLOs for message latency, sync freshness, and dashboard load.
- **DoD:** system meets target performance on Mac mini hardware.

### T-062: Cost Governance
- Per-service and per-feature monthly spend tracking.
- Budget alerts and auto-degrade policies when thresholds hit.
- **DoD:** predictable operating cost envelope.

### T-063: Compliance and Data Retention Policy
- Define retention windows by domain; implement purge/archival jobs.
- Add export/delete workflows for household data portability.
- **DoD:** transparent lifecycle management for all retained data.

---

## Suggested Execution Sequence

1. P0 foundation/security (T-001..T-005)
2. P0 integrations (T-010..T-017)
3. P0 SSOT completion (T-020..T-023)
4. P1 profile/auth UX (T-030..T-033)
5. P1 ops/deployment hardening (T-040..T-052)
6. P2 quality/completeness (T-060..T-063)

---

## Final Go-Live Checklist

- [ ] Production secrets configured and validated.
- [ ] OAuths connected and token refresh verified.
- [ ] Webhooks verified with signature checks and replay protection.
- [ ] Inbound/outbound messaging tested on Twilio + BlueBubbles.
- [ ] Google Gmail/Calendar/Drive/Sheets sync running with stale-age telemetry.
- [ ] Tasks/Calendar/Finance SSOTs validated with sample and real data.
- [ ] Multi-user login/RBAC/privacy tests passing.
- [ ] Backups + restore drill completed.
- [ ] Runbooks complete (on-call, outage, key rotation, disaster recovery).
- [ ] UAT signoff by each family member profile.

