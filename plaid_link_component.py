"""Minimal Streamlit component wrapper for Plaid Link."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import streamlit.components.v1 as components


_component = components.declare_component(
    "budget_analysis_plaid_link",
    path=str(Path(__file__).parent / "plaid_link_frontend"),
)


def plaid_link(
    link_token: str,
    button_text: str = "Connect account",
    key: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Render Plaid Link and return its success payload."""
    return _component(
        link_token=link_token,
        button_text=button_text,
        key=key,
        default=None,
    )
