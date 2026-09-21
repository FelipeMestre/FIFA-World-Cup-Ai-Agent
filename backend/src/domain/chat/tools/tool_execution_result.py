"""Shared handler-result shape. Lives in its own module (not `registry.py`,
which imports every tool module) so both `registry.py` and individual tool
modules can import it without a cycle.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ToolExecutionResult:
    """A tool handler's result, split into the two channels a widget-
    producing tool needs: `content` is what the model reads back (always
    present); `widget_data` is the same result reshaped for the frontend
    (present only on a successful, widget-worthy call -- absent on error
    content, and absent entirely for a tool with no widget of its own, like
    `get_current_utc_time`).
    """

    content: str
    widget_data: dict | None = None
