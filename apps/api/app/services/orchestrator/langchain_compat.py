"""LangChain compatibility helpers for environments without installed extras."""

from __future__ import annotations

from typing import Any, Callable

LANGCHAIN_AVAILABLE = False
_LCRunnableLambda: Any | None = None
_LCStructuredTool: Any | None = None

try:
    from langchain_core.runnables import RunnableLambda as _ImportedRunnableLambda
    from langchain_core.tools import StructuredTool as _ImportedStructuredTool

    _LCRunnableLambda = _ImportedRunnableLambda
    _LCStructuredTool = _ImportedStructuredTool
    LANGCHAIN_AVAILABLE = True
except ImportError:
    pass


class _FallbackRunnableLambda:
    """Small subset of RunnableLambda used by orchestrator tests."""

    def __init__(self, func: Callable[[Any], Any]) -> None:
        self._func = func

    def invoke(self, payload: Any) -> Any:
        return self._func(payload)


class _FallbackStructuredTool:
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
    ) -> "_FallbackStructuredTool":
        del name
        del description
        del args_schema
        return cls(func=func)

    def invoke(self, payload: dict[str, Any]) -> Any:
        return self._func(**payload)


def create_runnable_lambda(func: Callable[[Any], Any]) -> Any:
    """Create a RunnableLambda-compatible object."""

    if LANGCHAIN_AVAILABLE and _LCRunnableLambda is not None:
        return _LCRunnableLambda(func)
    return _FallbackRunnableLambda(func)


def create_structured_tool(
    *,
    func: Callable[..., Any],
    name: str,
    description: str,
    args_schema: Any | None = None,
) -> Any:
    """Create a StructuredTool-compatible object."""

    if LANGCHAIN_AVAILABLE and _LCStructuredTool is not None:
        return _LCStructuredTool.from_function(
            func=func,
            name=name,
            description=description,
            args_schema=args_schema,
        )
    return _FallbackStructuredTool.from_function(
        func=func,
        name=name,
        description=description,
        args_schema=args_schema,
    )
