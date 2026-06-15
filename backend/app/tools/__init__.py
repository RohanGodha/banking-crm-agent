"""Eager imports register every tool with the registry."""
from __future__ import annotations


def bootstrap_tools() -> None:
    # Importing the modules triggers the @tool decorator side-effect.
    from . import (  # noqa: F401
        compute_value,
        create_outreach_batch,
        generate_whatsapp,
        get_transactions,
        predict_propensity,
        query_customers,
        recommend_products,
        search_interactions,
    )
