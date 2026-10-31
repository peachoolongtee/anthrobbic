"""Regenerate `app/negotiation/airport_limits.py` from the challenge workbook.

Run from outside the data folder, reading the workbook as data only:

    uv run --no-project --with openpyxl python -I scripts/build_airport_limits.py \\
        /path/to/challenge2_operational_constraints.xlsx

openpyxl is used here and nowhere else; it is not a runtime dependency. The
output records the workbook's SHA-256 so a stale table can be spotted.
"""

import hashlib
import sys
from pathlib import Path

import openpyxl

SHEET = "airport_capacity"
HEADER_ROW = 3
COLUMNS = (
    "IATA_CODE",
    "size_class",
    "active_runways",
    "gates",
    "max_runway_ops_per_hour",
    "min_turnaround_min",
    "spare_gates_at_any_time",
)
TARGET = Path(__file__).resolve().parents[1] / "app/negotiation/airport_limits.py"

TEMPLATE = '''"""Challenge workbook airport limits. Generated; do not edit by hand.

Source: challenge2_operational_constraints.xlsx, sheet airport_capacity, which
the organisers label SYNTHETIC planning limits scaled from each airport's
traffic in flights.csv. They are not real airport data and not regulations.
Regenerate with `scripts/build_airport_limits.py`.

Workbook SHA-256: @SHA@
Airports: @COUNT@
"""

from dataclasses import dataclass
from typing import Final

WORKBOOK_FILE: Final = "challenge2_operational_constraints.xlsx"
WORKBOOK_SHA256: Final = "@SHA@"


class AirportDataFault(LookupError):
    """An airport has no row in the workbook. A data fault, never a default."""


@dataclass(frozen=True, slots=True)
class AirportLimits:
    iata: str
    size_class: str
    active_runways: int
    gates: int  # context only; the scenario uses the planned gate plus spares
    max_runway_ops_per_hour: int  # treated as an airport total
    min_turnaround_min: int
    spare_gates_at_any_time: int


# IATA, size class, active runways, gates, ops per hour, min turnaround, spare gates
_ROWS: Final[tuple[tuple[str, str, int, int, int, int, int], ...]] = (
@ROWS@
)

AIRPORT_LIMITS: Final[dict[str, AirportLimits]] = {
    row[0]: AirportLimits(*row) for row in _ROWS
}


def limits_for(iata: str) -> AirportLimits:
    """The workbook's limits for an airport, or `AirportDataFault`."""
    try:
        return AIRPORT_LIMITS[iata]
    except KeyError:
        raise AirportDataFault(f"no workbook row for airport {iata!r}") from None


def find_limits(iata: str) -> AirportLimits | None:
    """Like `limits_for`, but None for an airport with no row, for callers that
    turn the gap into a visible fault themselves."""
    return AIRPORT_LIMITS.get(iata)
'''


def main(workbook: Path) -> None:
    digest = hashlib.sha256(workbook.read_bytes()).hexdigest()
    sheet = openpyxl.load_workbook(workbook, data_only=True)[SHEET]
    rows = list(sheet.iter_rows(min_row=HEADER_ROW, values_only=True))
    header = list(rows[0])
    positions = [header.index(c) for c in COLUMNS]
    lines = []
    for row in rows[1:]:
        if not row[0]:
            continue
        code, size_class, *numbers = (row[i] for i in positions)
        figures = ", ".join(str(int(n)) for n in numbers)
        lines.append(f'    ("{code}", "{size_class}", {figures}),')
    lines.sort()
    TARGET.write_text(
        TEMPLATE.replace("@SHA@", digest)
        .replace("@COUNT@", str(len(lines)))
        .replace("@ROWS@", "\n".join(lines))
    )
    print(f"wrote {len(lines)} airports, sha256 {digest}")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
