"""Deterministic risk gates for project execution. No LLM, no network."""


class GateViolation(Exception):
    """Raised when a project action violates a risk gate."""

    def __init__(self, fence: str, reason: str, requires: str = "approval"):
        self.fence = fence
        self.reason = reason
        self.requires = requires
        super().__init__(f"[{fence}] {reason} (requires: {requires})")


# ─── Actions forbidden by the technical gate ───

FORBIDDEN_ACTIONS = frozenset({
    "modify_config",
    "modify_schema",
    "modify_cron",
    "delete_data",
    "modify_codebase",
    "modify_migration",
    "modify_env",
    "drop_table",
})


def check_financial_gate(project: dict, amount_cents: int, description: str):
    """Check whether a financial action is allowed within project permissions.

    Raises GateViolation if:
    - can_spend is 0
    - amount would exceed budget_limit_cents
    - amount exceeds budget_per_action_limit_cents
    """
    if not project.get("can_spend"):
        raise GateViolation(
            fence="financial",
            reason=f"Project not authorized to spend. Action: {description}",
            requires="budget_approval",
        )

    budget_limit = project.get("budget_limit_cents")
    if budget_limit is not None:
        spent = project.get("budget_spent_cents", 0)
        if spent + amount_cents > budget_limit:
            raise GateViolation(
                fence="financial",
                reason=(
                    f"Would exceed project budget: ${budget_limit / 100:.2f} "
                    f"(spent: ${spent / 100:.2f}, this action: ${amount_cents / 100:.2f})"
                ),
                requires="budget_increase",
            )

    per_action_limit = project.get("budget_per_action_limit_cents", 5000)
    if amount_cents > per_action_limit:
        raise GateViolation(
            fence="financial",
            reason=(
                f"Exceeds per-action limit: ${per_action_limit / 100:.2f} "
                f"(this action: ${amount_cents / 100:.2f})"
            ),
            requires="per_action_approval",
        )


def check_reputational_gate(project: dict, contact_handle: str, channel: str):
    """Check whether outbound contact is allowed for this project.

    Raises GateViolation if the project lacks permission for the given channel.
    """
    channel_permissions = {
        "email": "can_email_strangers",
        "gmail": "can_email_strangers",
        "sms": "can_sms_strangers",
        "twilio_sms": "can_sms_strangers",
        "call": "can_call_strangers",
        "twilio_call": "can_call_strangers",
        "phone": "can_call_strangers",
    }

    perm_key = channel_permissions.get(channel)
    if perm_key and not project.get(perm_key):
        raise GateViolation(
            fence="reputational",
            reason=f"Project not authorized to {channel} strangers. Contact: {contact_handle}",
            requires="permission_grant",
        )


def check_technical_gate(action_type: str):
    """Check whether a technical action is permitted.

    Projects NEVER modify PIB's own config, schema, cron, or codebase.
    Raises GateViolation for any forbidden action.
    """
    if action_type in FORBIDDEN_ACTIONS:
        raise GateViolation(
            fence="technical",
            reason=f"Action '{action_type}' is forbidden for projects (Gene 4 / Gene 7)",
            requires="manual_override",
        )
