"""Decisão do layout: móvel (celular, retrato) ou desktop (barra lateral + barra de título própria)."""
from __future__ import annotations

MOBILE_BREAKPOINT = 700


def use_mobile(is_android: bool, width: float | None) -> bool:
    """No Android sempre; no PC só se a janela já nascer estreita (width 0/None = ainda desconhecida)."""
    return is_android or (bool(width) and width < MOBILE_BREAKPOINT)


def grid_extent(mobile: bool) -> int:
    """Largura máxima de cada cartão da grade de Pokémon: 3 por linha num celular em retrato."""
    return 120 if mobile else 160
