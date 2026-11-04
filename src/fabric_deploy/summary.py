"""Resumo legível do plano e do deploy (terminal e GitHub Actions)."""

from __future__ import annotations

import os
from pathlib import Path

ICONS = {
    "CREATE": "🆕",
    "UPDATE": "✏️",
    "MOVE": "📁",
    "DELETE": "🗑️",
    "NOOP": "➖",
    "BLOCKED": "⛔",
    "FAILED": "❌",
    "SKIPPED": "⏭️",
}


def _value(obj, name: str, default=""):
    value = getattr(obj, name, default)
    return getattr(value, "value", value) if value is not None else default


def plan_rows(plan) -> list[list[str]]:
    return [
        [
            f"{ICONS.get(_value(a, 'action'), '')} {_value(a, 'action')}",
            f"{a.display_name or '-'}.{a.item_type}",
            str(_value(a, "reason")),
            a.detail or "",
        ]
        for a in getattr(plan, "actions", [])
    ]


def report_rows(report) -> list[list[str]]:
    return [
        [
            f"{ICONS.get(str(_value(r, 'action')).upper(), '')} {_value(r, 'action')}",
            f"{r.display_name or '-'}.{r.item_type}",
            f"{r.duration_seconds:.1f}s",
            r.error or "",
        ]
        for r in getattr(report, "results", [])
    ]


def markdown(
    title: str, header: list[str], rows: list[list[str]], notes: list[str], empty: str = "Nenhum item a implantar."
) -> str:
    lines = [f"### {title}", ""]
    lines += [f"> {n}" for n in notes]
    if notes:
        lines.append("")
    if not rows:
        lines.append(empty)
        return "\n".join(lines) + "\n"
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))
    lines += ["| " + " | ".join(c.replace("|", "\\|") for c in row) + " |" for row in rows]
    return "\n".join(lines) + "\n"


def publish(text: str) -> None:
    """Imprime e, no GitHub Actions, grava no resumo da execução."""
    print(text)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a", encoding="utf-8") as fh:
            fh.write(text + "\n")
