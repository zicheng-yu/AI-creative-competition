"""Benchmark ampacity lookup.

The pass/fail relation is the one in GB 50054-2011 clause 6.3.3:
``Ib <= In <= Iz``. The numeric Iz column is an ElectroBench evaluation
table (copper XLPE, order-of-magnitude alignment with publicly discussed
YJV ratings). It is not a transcription of GB/T 16895.15.
"""

from __future__ import annotations

# (section_mm2, Iz_A). Monotone by construction.
AMPACITY_TABLE: tuple[tuple[int, int], ...] = (
    (2, 16),
    (4, 28),
    (6, 36),
    (10, 50),
    (16, 66),
    (25, 87),
    (35, 110),
    (50, 134),
    (70, 171),
    (95, 207),
    (120, 239),
    (150, 271),
    (185, 310),
    (240, 367),
    (300, 430),
)

_BY_SECTION = dict(AMPACITY_TABLE)


def iz_of(section_mm2: int) -> int:
    try:
        return _BY_SECTION[int(section_mm2)]
    except KeyError as exc:
        raise KeyError(f"section {section_mm2} mm² is not in the ElectroBench ampacity table") from exc


def select_section(current_a: int) -> tuple[int, int]:
    """Smallest tabulated section whose Iz is at least ``current_a``."""
    for section, iz in AMPACITY_TABLE:
        if iz >= current_a:
            return section, iz
    raise ValueError(f"no tabulated section covers {current_a} A")


def undersized_section(current_a: int) -> tuple[int, int]:
    """Largest tabulated section whose Iz is strictly below ``current_a``."""
    choice: tuple[int, int] | None = None
    for section, iz in AMPACITY_TABLE:
        if iz < current_a:
            choice = (section, iz)
    if choice is None:
        raise ValueError(f"no undersized section for {current_a} A")
    return choice


def _pe_section(phase_mm2: int) -> int:
    """Smallest conventional PE size at least half the phase conductor."""
    for candidate in (2, 4, 6, 10, 16, 25, 35, 50, 70, 95, 120, 150, 185, 240):
        if candidate >= phase_mm2 / 2:
            return candidate
    return phase_mm2


def cable_spec(section_mm2: int, *, pe_mm2: int | None = None) -> tuple[str, int]:
    iz = iz_of(section_mm2)
    pe = pe_mm2 if pe_mm2 is not None else _pe_section(section_mm2)
    spec = f"YJV-4x{section_mm2}+1x{pe}"
    return spec, iz
