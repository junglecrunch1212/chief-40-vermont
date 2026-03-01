"""API cost tracking per request and monthly accumulation."""

import logging
from datetime import date

from pib.db import get_config, set_config

log = logging.getLogger(__name__)

# Approximate cost per token (update when pricing changes)
COST_PER_TOKEN = {
    "sonnet": {"input": 3.0 / 1_000_000, "output": 15.0 / 1_000_000},
    "opus": {"input": 15.0 / 1_000_000, "output": 75.0 / 1_000_000},
}


async def track_api_cost(db, input_tokens: int, output_tokens: int, model: str):
    """Track API spend per request. Accumulates in pib_config by month."""
    tier = "opus" if "opus" in model else "sonnet"
    costs = COST_PER_TOKEN.get(tier, COST_PER_TOKEN["sonnet"])
    cost = (input_tokens * costs["input"]) + (output_tokens * costs["output"])

    month_key = f"api_spend_{date.today().strftime('%Y_%m')}"
    current = float(await get_config(db, month_key) or "0.0")
    await set_config(db, month_key, str(current + cost), actor="cost_tracker")

    # Check budget alert
    budget_alert = float(await get_config(db, "monthly_api_budget_alert") or "75.0")
    if current + cost > budget_alert:
        log.warning(f"Monthly API spend ${current + cost:.2f} exceeds alert threshold ${budget_alert:.2f}")

    return {"cost": cost, "monthly_total": current + cost}
