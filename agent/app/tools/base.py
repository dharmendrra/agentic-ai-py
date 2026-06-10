"""Tool protocol + Manager (registry that compiles schemas into the prompt).

Mirrors the Go tools.Manager: registration order preserved, BuildPromptSection
renders ``- name: desc`` + a compact ``Input:`` line.
"""
from __future__ import annotations

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class Tool(Protocol):
    def name(self) -> str: ...

    def schema(self) -> Dict[str, Any]: ...

    async def execute(self, input: str) -> str: ...


def format_input_schema(input_schema: Dict[str, Any] | None) -> str:
    """Render required/optional params one-line, sorted; required prefixed '*'."""
    if not input_schema:
        return ""
    props = input_schema.get("properties") or {}
    if not props:
        return ""
    required = set(input_schema.get("required") or [])
    parts: List[str] = []
    for name, spec in props.items():
        typ = (spec or {}).get("type", "")
        prefix = "*" if name in required else ""
        parts.append(f"{prefix}{name}({typ})")
    parts.sort()
    return ", ".join(parts)


class Manager:
    def __init__(self) -> None:
        self._tools: Dict[str, Tool] = {}
        self._order: List[str] = []

    def register(self, tool: Tool) -> None:
        if tool.name() not in self._tools:
            self._order.append(tool.name())
        self._tools[tool.name()] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def names(self) -> List[str]:
        return list(self._order)

    def schemas(self) -> List[Dict[str, Any]]:
        return [self._tools[n].schema() for n in self._order]

    async def execute(self, name: str, input: str) -> str:
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"tool '{name}' not found")
        return await tool.execute(input)

    def build_prompt_section(self) -> str:
        lines: List[str] = []
        for s in self.schemas():
            lines.append(f"- {s['name']}: {s['description']}")
            props = format_input_schema(s.get("input_schema"))
            if props:
                lines.append(f"  Input: {props}")
        return "\n".join(lines) + ("\n" if lines else "")
