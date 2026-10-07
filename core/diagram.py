"""
Offline architecture diagram (matplotlib — no Graphviz, no internet).

Security concept: students should be able to point at the payment-switch
hop as the trust boundary that, once bypassed, poisons every ATM.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from core.paths import assets_dir, project_root


def architecture_png_path() -> Path:
    """Return a readable architecture PNG path (bundled copy preferred)."""
    bundled = assets_dir() / "architecture.png"
    return bundled


def _box(ax, x, y, w, h, text, facecolor, edge="#58a6ff") -> None:
    """Draw one labelled architecture node."""
    from matplotlib.patches import FancyBboxPatch

    patch = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        linewidth=1.6,
        edgecolor=edge,
        facecolor=facecolor,
    )
    ax.add_patch(patch)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", color="#e6edf3", fontsize=8.5, wrap=True)


def _arrow(ax, x1, y1, x2, y2, color="#8b949e") -> None:
    """Draw a directed edge between architecture nodes."""
    ax.annotate(
        "",
        xy=(x2, y2),
        xytext=(x1, y1),
        arrowprops=dict(arrowstyle="->", color=color, lw=1.6),
    )


def generate_architecture_png(dest: Optional[Path] = None) -> Path:
    """Render a simple ATM–Switch–Core–SWIFT–SOC diagram to assets/architecture.png."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dest = dest or architecture_png_path()
    dest.parent.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(11, 5.6), dpi=120)
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6)
    ax.axis("off")
    ax.set_title(
        "Cosmos Bank SOC Demo — Logical Architecture (fictional / offline)",
        color="#e6edf3",
        pad=12,
        fontsize=12,
    )

    _box(ax, 0.4, 3.4, 2.2, 1.3, "ATM network\n(IN / UAE / TH / MY)\nfictional terminals", "#161b22", "#3fb950")
    _box(ax, 3.4, 3.4, 2.4, 1.3, "Payment Switch\n(trust boundary)\n+ FIM SHA-256", "#3d0d0d", "#f85149")
    _box(ax, 6.6, 3.4, 2.2, 1.3, "Core Banking\nbalance check\nAPPROVE / DECLINE", "#0d213d", "#58a6ff")
    _box(ax, 9.1, 3.4, 1.6, 1.3, "Ledger\nSQLite", "#161b22", "#8b949e")

    _box(ax, 3.4, 0.7, 2.4, 1.3, "SWIFT gateway\n(fictional msgs)\ndual-control", "#3d3200", "#d29922")
    _box(ax, 6.6, 0.7, 2.2, 1.3, "SOC / SIEM\nrules R1–R6\nNIST response", "#0d3d1a", "#3fb950")
    _box(ax, 0.4, 0.7, 2.2, 1.3, "Analyst UI\nStreamlit\n(this demo)", "#161b22", "#58a6ff")

    _arrow(ax, 2.6, 4.05, 3.4, 4.05)
    _arrow(ax, 5.8, 4.05, 6.6, 4.05)
    _arrow(ax, 8.8, 4.05, 9.1, 4.05)
    _arrow(ax, 4.6, 3.4, 4.6, 2.0, "#d29922")
    _arrow(ax, 5.8, 1.35, 6.6, 1.35, "#3fb950")
    _arrow(ax, 2.6, 1.35, 3.4, 1.35)
    _arrow(ax, 7.7, 3.4, 7.7, 2.0, "#3fb950")

    ax.text(5.5, 5.3, "Authorisation path (normal): ATM → Switch → Core → Switch → ATM", color="#8b949e", ha="center", fontsize=8)
    ax.text(5.5, 0.25, "Compromise path (simulated): Switch ignores Core DECLINE → cash-out + SWIFT fraud", color="#f85149", ha="center", fontsize=8)

    fig.tight_layout()
    fig.savefig(dest, facecolor=fig.get_facecolor())
    plt.close(fig)
    return dest


def ensure_architecture_png() -> Path:
    """Generate the PNG on first run if it is missing (fully offline)."""
    path = architecture_png_path()
    if path.exists():
        return path
    writable = project_root() / "assets" / "architecture.png"
    if writable.exists():
        return writable
    return generate_architecture_png(writable)


if __name__ == "__main__":
    print(generate_architecture_png())
