"""LangChain compatibility helpers for environments without installed extras."""

from __future__ import annotations

from typing import Any, Callable

LANGCHAIN_AVAILABLE = False

try:
    from langchain_core.runnables import RunnableLambda as LCRunnableLambda
    from langchain_core.tools import StructuredTool as LCStructuredTool

    RunnableLambda = LCRunnableLambda
    StructuredTool = LCStructuredTool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    class RunnableLambda:
        """Small subset of RunnableLambda used by orchestrator tests."""

        def __init__(self, func: Callable[[Any], Any]) -> None:
            self._func = func

        def invoke(self, payload: Any) -> Any:
            return self._func(payload)

    class StructuredTool:
        """Small subset of StructuredTool used by orchestrator tests."""

        def __init__(self, func: Callable[..., Any]) -> None:
            self._func = func

        @classmethod
        def from_function(
            cls,
            *,
            func: Callable[..., Any],
            name: str,
            description: str,
            args_schema: Any | None = None,
        ) -> "StructuredTool":
            del name
            del description
            del args_schema
            return cls(func=func)

        def invoke(self, payload: dict[str, Any]) -> Any:
            return self._func(**payload)

