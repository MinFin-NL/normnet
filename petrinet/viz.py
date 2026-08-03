"""Rendering: Mermaid diagrams and terminal token traces."""

from __future__ import annotations

from typing import Mapping

from .core import PetriNet


def to_mermaid(net: PetriNet, marking: Mapping[str, int] | None = None) -> str:
    """Render the net as a Mermaid flowchart.

    Places are rounded (circles-ish), transitions are rectangles — the usual
    Petri net convention. Tokens in the current marking are shown as bullets
    and the holding places are highlighted.
    """
    marking = marking or net.initial_marking
    lines = ["flowchart LR"]
    for p in net.places:
        n = marking.get(p.id, 0)
        dots = " " + "●" * n if n else ""
        lines.append(f'    {p.id}(("{p.label}{dots}"))')
    for t in net.transitions:
        owner = t.meta.get("agent") or t.meta.get("owner", "")
        tag = f"<br/><i>{owner}</i>" if owner else ""
        lines.append(f'    {t.id}["{t.label}{tag}"]')
    for t in net.transitions:
        for a in t.inputs:
            w = f"|{a.weight}|" if a.weight > 1 else ""
            lines.append(f"    {a.place} -->{w} {t.id}")
        for a in t.outputs:
            w = f"|{a.weight}|" if a.weight > 1 else ""
            lines.append(f"    {t.id} -->{w} {a.place}")

    lines.append("    classDef marked fill:#2d6a4f,stroke:#95d5b2,color:#fff;")
    lines.append("    classDef auto fill:#1d3557,stroke:#a8dadc,color:#fff;")
    lines.append("    classDef hitl fill:#7f4f24,stroke:#ffd6a5,color:#fff;")
    marked = [p for p, n in marking.items() if n]
    if marked:
        lines.append(f"    class {','.join(marked)} marked;")
    auto = [t.id for t in net.transitions if t.meta.get("autonomy") == "auto"]
    hitl = [t.id for t in net.transitions if t.meta.get("autonomy") == "human_in_loop"]
    if auto:
        lines.append(f"    class {','.join(auto)} auto;")
    if hitl:
        lines.append(f"    class {','.join(hitl)} hitl;")
    return "\n".join(lines)


def marking_bar(net: PetriNet, marking: Mapping[str, int], width: int = 58) -> str:
    """One-line token map, ordered as the places are declared."""
    cells = []
    for p in net.places:
        n = marking.get(p.id, 0)
        cells.append("●" if n == 1 else (str(n) if n else "·"))
    return "".join(cells)[:width]


def place_legend(net: PetriNet) -> str:
    return "  ".join(f"{i}:{p.id}" for i, p in enumerate(net.places))
