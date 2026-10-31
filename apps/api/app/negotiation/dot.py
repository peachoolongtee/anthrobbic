"""US DOT on-time rows: typed access, eligibility, sampling and a local cache.

One pass over the CSV builds a SQLite cache next to it. The cache holds the
eligible rows, a lean schedule table of every flight (for the traffic bank and
for a tail's next leg) and each airport's typical taxi-in. Later calls read the
cache and never re-parse the CSV.

Times: HHMM clock values become minutes from 00:00 of the scheduled-departure
date. An arrival that crosses midnight is therefore above 1440. Arrival
minutes are on the destination's local clock, departure minutes on the
origin's local clock; the clock offset is recovered from the scheduled block
time, so no time-zone table is needed.

The outcome columns (arrival, wheels, delay-cause split) live on `DotRow` so the
evaluation can read them, but only `scenario.outcome_of` should touch them.
"""

import csv
import os
import random
import sqlite3
import tempfile
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Final, Literal

DEFAULT_CSV: Final = Path(
    "/Users/ianpong/Hackathons/anthrobbic/data/flight-delays/flights.csv"
)
ENV_CSV: Final = "FLIGHTS_CSV"
CACHE_VERSION: Final = 1

type Cause = Literal["weather", "late_aircraft"]

WEATHER_THRESHOLD_MIN: Final = 15  # eligible when WEATHER_DELAY is above this
LATE_AIRCRAFT_THRESHOLD_MIN: Final = 20  # or LATE_AIRCRAFT_DELAY is above this
EXCLUDED_MONTH: Final = 10  # October's airport codes are numeric, not IATA
MINUTES_PER_DAY: Final = 1440
# Larger offsets than any US clock difference mean the block time is unusable.
MAX_CLOCK_OFFSET_MIN: Final = 420
MIN_TAXI_SAMPLES: Final = 10


class DotError(RuntimeError):
    """The CSV is missing, malformed, or the cache cannot be built."""


@dataclass(frozen=True, slots=True)
class DotRow:
    """One flight, with the CSV's own column meanings. `None` means blank."""

    year: int
    month: int
    day: int
    day_of_week: int
    airline: str
    flight_number: int
    tail_number: str
    origin_airport: str
    destination_airport: str
    scheduled_departure: int  # HHMM
    departure_time: int | None  # HHMM, outcome
    departure_delay: int | None  # outcome
    taxi_out: int | None
    wheels_off: int | None  # HHMM, outcome
    scheduled_time: int | None  # minutes of scheduled block time
    elapsed_time: int | None  # outcome
    air_time: int | None  # outcome
    distance: int | None
    wheels_on: int | None  # HHMM, outcome
    taxi_in: int | None  # outcome
    scheduled_arrival: int  # HHMM
    arrival_time: int | None  # HHMM, outcome
    arrival_delay: int | None  # outcome
    diverted: bool
    cancelled: bool
    cancellation_reason: str | None
    air_system_delay: int | None  # outcome
    security_delay: int | None  # outcome
    airline_delay: int | None  # outcome
    late_aircraft_delay: int | None  # outcome
    weather_delay: int | None  # outcome
    source_row: int  # 1-based data row in the CSV, for traceability

    @property
    def flight_id(self) -> str:
        return f"{self.airline}{self.flight_number}"

    @property
    def day_start_abs(self) -> int:
        """Minute of the scheduled-departure date's midnight on a global axis."""
        return _ordinal(self.year, self.month, self.day) * MINUTES_PER_DAY

    @property
    def cause(self) -> Cause:
        return cause_of(self)


def cause_of(row: DotRow) -> Cause:
    """The row's stratum. A row over both thresholds counts as weather."""
    if row.weather_delay is not None and row.weather_delay > WEATHER_THRESHOLD_MIN:
        return "weather"
    return "late_aircraft"


def is_eligible(row: DotRow) -> bool:
    """Eligibility as the brief states it, plus the two data exclusions."""
    over_weather = (
        row.weather_delay is not None and row.weather_delay > WEATHER_THRESHOLD_MIN
    )
    over_late = (
        row.late_aircraft_delay is not None
        and row.late_aircraft_delay > LATE_AIRCRAFT_THRESHOLD_MIN
    )
    return (
        (over_weather or over_late)
        and row.month != EXCLUDED_MONTH
        and bool(row.tail_number)
    )


_ORDINALS: dict[tuple[int, int, int], int] = {}


def _ordinal(year: int, month: int, day: int) -> int:
    key = (year, month, day)
    found = _ORDINALS.get(key)
    if found is None:
        found = _ORDINALS[key] = date(year, month, day).toordinal()
    return found


def hhmm_to_min(hhmm: int) -> int:
    """HHMM to minutes after midnight. 2400 is the end of the day, 1440."""
    return (hhmm // 100) * 60 + hhmm % 100


def scheduled_arrival_rel(dep_hhmm: int, arr_hhmm: int, sched_time: int | None) -> int:
    """Scheduled arrival in minutes from the departure date's midnight, on the
    destination's clock.

    The clock offset between airports is whatever makes departure plus block
    time land on the scheduled arrival clock time, so a flight that crosses
    midnight comes out above 1440. Without a usable block time the arrival is
    placed after the departure by assuming it is the next clock occurrence.
    """
    dep = hhmm_to_min(dep_hhmm)
    arr = hhmm_to_min(arr_hhmm)
    if sched_time is not None:
        offset = (arr - dep - sched_time + 720) % MINUTES_PER_DAY - 720
        if abs(offset) <= MAX_CLOCK_OFFSET_MIN:
            return dep + sched_time + offset
    return arr + (MINUTES_PER_DAY if arr < dep else 0)


def scheduled_arrival_min(row: DotRow) -> int:
    """`scheduled_arrival_rel` for a row. Schedule columns only."""
    return scheduled_arrival_rel(
        row.scheduled_departure, row.scheduled_arrival, row.scheduled_time
    )


# --- CSV parsing -----------------------------------------------------------

# attribute, CSV column, kind. The order matches `DotRow` (less `source_row`).
_FIELDS: Final[tuple[tuple[str, str, str], ...]] = (
    ("year", "YEAR", "int"),
    ("month", "MONTH", "int"),
    ("day", "DAY", "int"),
    ("day_of_week", "DAY_OF_WEEK", "int"),
    ("airline", "AIRLINE", "str"),
    ("flight_number", "FLIGHT_NUMBER", "int"),
    ("tail_number", "TAIL_NUMBER", "str"),
    ("origin_airport", "ORIGIN_AIRPORT", "str"),
    ("destination_airport", "DESTINATION_AIRPORT", "str"),
    ("scheduled_departure", "SCHEDULED_DEPARTURE", "int"),
    ("departure_time", "DEPARTURE_TIME", "opt_int"),
    ("departure_delay", "DEPARTURE_DELAY", "opt_int"),
    ("taxi_out", "TAXI_OUT", "opt_int"),
    ("wheels_off", "WHEELS_OFF", "opt_int"),
    ("scheduled_time", "SCHEDULED_TIME", "opt_int"),
    ("elapsed_time", "ELAPSED_TIME", "opt_int"),
    ("air_time", "AIR_TIME", "opt_int"),
    ("distance", "DISTANCE", "opt_int"),
    ("wheels_on", "WHEELS_ON", "opt_int"),
    ("taxi_in", "TAXI_IN", "opt_int"),
    ("scheduled_arrival", "SCHEDULED_ARRIVAL", "int"),
    ("arrival_time", "ARRIVAL_TIME", "opt_int"),
    ("arrival_delay", "ARRIVAL_DELAY", "opt_int"),
    ("diverted", "DIVERTED", "bool"),
    ("cancelled", "CANCELLED", "bool"),
    ("cancellation_reason", "CANCELLATION_REASON", "opt_str"),
    ("air_system_delay", "AIR_SYSTEM_DELAY", "opt_int"),
    ("security_delay", "SECURITY_DELAY", "opt_int"),
    ("airline_delay", "AIRLINE_DELAY", "opt_int"),
    ("late_aircraft_delay", "LATE_AIRCRAFT_DELAY", "opt_int"),
    ("weather_delay", "WEATHER_DELAY", "opt_int"),
)
_COLUMN_NAMES: Final = tuple(csv_name for _, csv_name, _ in _FIELDS)


def _to_int(text: str) -> int:
    try:
        return int(text)
    except ValueError:
        return int(float(text))


def _parse(kind: str, text: str) -> int | str | bool | None:
    text = text.strip()
    match kind:
        case "int":
            return _to_int(text)
        case "opt_int":
            return _to_int(text) if text else None
        case "bool":
            return _to_int(text) != 0 if text else False
        case "opt_str":
            return text or None
        case _:
            return text


def _parse_record(record: list[str], positions: list[int]) -> tuple[object, ...]:
    return tuple(
        _parse(kind, record[pos])
        for (_, _, kind), pos in zip(_FIELDS, positions, strict=True)
    )


def _row_from_values(values: tuple[object, ...], source_row: int) -> DotRow:
    named = {attr: v for (attr, _, _), v in zip(_FIELDS, values, strict=True)}
    return DotRow(**named, source_row=source_row)  # type: ignore[arg-type]


# --- cache -----------------------------------------------------------------

_ELIGIBLE_COLUMNS: Final = ", ".join(attr for attr, _, _ in _FIELDS)
_SCHEMA: Final = f"""
CREATE TABLE eligible (
    id INTEGER PRIMARY KEY,
    cause TEXT NOT NULL,
    source_row INTEGER NOT NULL,
    {
    ", ".join(
        f"{attr} {'TEXT' if kind in ('str', 'opt_str') else 'INTEGER'}"
        for attr, _, kind in _FIELDS
    )
}
);
CREATE TABLE flights (
    dest TEXT NOT NULL,
    arr_abs INTEGER NOT NULL,
    origin TEXT NOT NULL,
    dep_abs INTEGER NOT NULL,
    tail TEXT NOT NULL,
    flight TEXT NOT NULL,
    dep_delay INTEGER
);
CREATE TABLE taxi_in (airport TEXT PRIMARY KEY, median_min INTEGER, samples INTEGER);
"""


def csv_path(path: str | os.PathLike[str] | None = None) -> Path:
    """The CSV to read: the argument, else `FLIGHTS_CSV`, else the default."""
    if path is not None:
        return Path(path)
    return Path(os.environ.get(ENV_CSV) or DEFAULT_CSV)


def cache_path(path: str | os.PathLike[str] | None = None) -> Path:
    """Where the cache for this CSV lives: a git-ignored `.cache` beside it."""
    source = csv_path(path)
    try:
        stat = source.stat()
    except FileNotFoundError as error:
        raise DotError(f"flights CSV not found: {source}") from error
    name = f"{source.stem}-v{CACHE_VERSION}-{stat.st_size}-{stat.st_mtime_ns}.sqlite"
    return source.parent / ".cache" / name


def _build_cache(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    (target.parent / ".gitignore").write_text("*\n")
    handle, tmp_name = tempfile.mkstemp(
        dir=target.parent, prefix=target.name, suffix=".tmp"
    )
    os.close(handle)
    tmp = Path(tmp_name)
    try:
        con = sqlite3.connect(tmp)
        con.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;")
        con.executescript(_SCHEMA)
        _fill_cache(con, source)
        con.commit()
        con.close()
        os.replace(tmp, target)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


def _fill_cache(con: sqlite3.Connection, source: Path) -> None:
    taxi: defaultdict[str, defaultdict[int, int]] = defaultdict(
        lambda: defaultdict(int)
    )
    flights: list[tuple[object, ...]] = []
    eligible: list[tuple[object, ...]] = []
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            raise DotError(f"empty CSV: {source}")
        missing = [c for c in _COLUMN_NAMES if c not in header]
        if missing:
            raise DotError(f"CSV lacks columns {missing}: {source}")
        positions = [header.index(c) for c in _COLUMN_NAMES]
        (i_month, i_tail, i_orig, i_dest, i_sdep, i_sarr, i_stime) = (
            header.index(c)
            for c in (
                "MONTH",
                "TAIL_NUMBER",
                "ORIGIN_AIRPORT",
                "DESTINATION_AIRPORT",
                "SCHEDULED_DEPARTURE",
                "SCHEDULED_ARRIVAL",
                "SCHEDULED_TIME",
            )
        )
        i_year, i_day = header.index("YEAR"), header.index("DAY")
        i_airline, i_fno = header.index("AIRLINE"), header.index("FLIGHT_NUMBER")
        i_ddelay, i_taxi = header.index("DEPARTURE_DELAY"), header.index("TAXI_IN")
        i_weather, i_late = (
            header.index("WEATHER_DELAY"),
            header.index("LATE_AIRCRAFT_DELAY"),
        )
        excluded = str(EXCLUDED_MONTH)
        for number, rec in enumerate(reader, start=1):
            if len(flights) >= 200_000:
                _flush(con, flights, eligible)
            if not rec or rec[i_month] == excluded:
                continue
            try:
                ordinal = _ordinal(
                    _to_int(rec[i_year]), _to_int(rec[i_month]), _to_int(rec[i_day])
                )
                dep = _to_int(rec[i_sdep])
                arr = _to_int(rec[i_sarr])
                stime = _to_int(rec[i_stime]) if rec[i_stime] else None
                base = ordinal * MINUTES_PER_DAY
                dep_abs = base + hhmm_to_min(dep)
                arr_abs = base + scheduled_arrival_rel(dep, arr, stime)
                ddelay = _to_int(rec[i_ddelay]) if rec[i_ddelay] else None
            except (ValueError, IndexError):
                continue  # a malformed row cannot join the schedule
            flights.append(
                (
                    rec[i_dest],
                    arr_abs,
                    rec[i_orig],
                    dep_abs,
                    rec[i_tail],
                    f"{rec[i_airline]}{rec[i_fno]}",
                    ddelay,
                )
            )
            if rec[i_taxi]:
                try:
                    taxi[rec[i_dest]][_to_int(rec[i_taxi])] += 1
                except ValueError:
                    pass
            weather, late = rec[i_weather], rec[i_late]
            try:
                over_weather = bool(weather) and _to_int(weather) > (
                    WEATHER_THRESHOLD_MIN
                )
                over_late = bool(late) and _to_int(late) > LATE_AIRCRAFT_THRESHOLD_MIN
            except ValueError:
                continue
            if (over_weather or over_late) and rec[i_tail].strip():
                try:
                    values = _parse_record(rec, positions)
                except ValueError:
                    continue
                eligible.append(
                    ("weather" if over_weather else "late_aircraft", number, *values)
                )
        _flush(con, flights, eligible)

    con.executemany(
        "INSERT INTO taxi_in VALUES (?, ?, ?)",
        [
            (airport, _weighted_median(counts), sum(counts.values()))
            for airport, counts in sorted(taxi.items())
        ],
    )
    con.executescript(
        """
        CREATE INDEX flights_dest_arr ON flights (dest, arr_abs);
        CREATE INDEX flights_tail_dep ON flights (tail, dep_abs);
        CREATE INDEX eligible_cause ON eligible (cause, id);
        """
    )


def _weighted_median(counts: dict[int, int]) -> int:
    """Lower median of minute values given as value-to-count."""
    total = sum(counts.values())
    seen = 0
    for value in sorted(counts):
        seen += counts[value]
        if seen * 2 >= total:
            return value
    raise ValueError("no values")


def _flush(
    con: sqlite3.Connection,
    flights: list[tuple[object, ...]],
    eligible: list[tuple[object, ...]],
) -> None:
    con.executemany("INSERT INTO flights VALUES (?, ?, ?, ?, ?, ?, ?)", flights)
    marks = ", ".join("?" * (2 + len(_FIELDS)))
    con.executemany(
        f"INSERT INTO eligible (cause, source_row, {_ELIGIBLE_COLUMNS}) "
        f"VALUES ({marks})",
        eligible,
    )
    flights.clear()
    eligible.clear()


_connections: dict[Path, sqlite3.Connection] = {}


def clear_connections() -> None:
    """Close every cached connection (tests delete their cache files)."""
    for con in _connections.values():
        con.close()
    _connections.clear()


def ensure_cache(path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    """A read-only connection to the cache, building it first if needed."""
    source = csv_path(path)
    target = cache_path(source)
    con = _connections.get(target)
    if con is not None:
        return con
    if not target.exists():
        _build_cache(source, target)
    con = sqlite3.connect(f"file:{target}?mode=ro", uri=True, check_same_thread=False)
    _connections[target] = con
    return con


def _select_rows(
    con: sqlite3.Connection, where: str, params: tuple[object, ...]
) -> Iterator[DotRow]:
    query = f"SELECT source_row, {_ELIGIBLE_COLUMNS} FROM eligible {where} ORDER BY id"
    for record in con.execute(query, params):
        values = list(record[1:])
        for i, (_, _, kind) in enumerate(_FIELDS):
            if kind == "bool":
                values[i] = bool(values[i])
        yield _row_from_values(tuple(values), record[0])


def iter_eligible_rows(
    path: str | os.PathLike[str] | None = None,
) -> Iterator[DotRow]:
    """Every eligible row in CSV order, October and tail-less rows excluded."""
    yield from _select_rows(ensure_cache(path), "", ())


def sample_rows(
    n: int,
    seed: int,
    cause: Cause | None = None,
    path: str | os.PathLike[str] | None = None,
) -> list[DotRow]:
    """A seeded sample of eligible rows.

    With `cause=None` the sample is half weather and half late-aircraft (the
    extra row of an odd `n` is late-aircraft), because late-aircraft rows are
    about 91% of the eligible set. A stratum smaller than its quota returns
    all of it. The same arguments return the same rows in the same order.
    """
    if n < 0:
        raise ValueError("n must not be negative")
    if cause not in (None, "weather", "late_aircraft"):
        raise ValueError(f"unknown cause {cause!r}")
    con = ensure_cache(path)
    quotas: list[tuple[Cause, int]] = (
        [(cause, n)]
        if cause is not None
        else [("weather", n // 2), ("late_aircraft", n - n // 2)]
    )
    rng = random.Random(seed)
    picked: list[int] = []
    for stratum, quota in quotas:
        ids = [
            r[0]
            for r in con.execute(
                "SELECT id FROM eligible WHERE cause = ? ORDER BY id", (stratum,)
            )
        ]
        picked.extend(rng.sample(ids, min(quota, len(ids))))
    by_id = {
        row_id: row
        for row_id, row in zip(
            sorted(picked),
            _select_by_ids(con, sorted(picked)),
            strict=True,
        )
    }
    return [by_id[i] for i in picked]


def _select_by_ids(con: sqlite3.Connection, ids: list[int]) -> Iterator[DotRow]:
    for start in range(0, len(ids), 500):
        chunk = ids[start : start + 500]
        marks = ", ".join("?" * len(chunk))
        yield from _select_rows(con, f"WHERE id IN ({marks})", tuple(chunk))


# --- schedule queries --------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ScheduledArrival:
    """Another flight scheduled to land at the same airport."""

    flight_id: str
    arrival_min: int  # relative to the subject flight's departure-date midnight


@dataclass(frozen=True, slots=True)
class NextLeg:
    """The same tail's next departure on the same day, from the schedule.

    `departure_delay_min` is as flown: evaluation only, never a scenario input.
    """

    flight_id: str
    destination: str
    scheduled_departure_min: int  # relative to the subject's departure-date midnight
    departure_delay_min: int | None


def traffic_near(
    row: DotRow,
    start_min: int,
    end_min: int,
    path: str | os.PathLike[str] | None = None,
) -> tuple[ScheduledArrival, ...]:
    """Other flights scheduled into this flight's destination in a window.

    Uses scheduled arrival times only, so the bank holds no outcome. The
    subject flight itself is excluded.
    """
    con = ensure_cache(path)
    base = row.day_start_abs
    found = con.execute(
        "SELECT flight, arr_abs, origin, dep_abs FROM flights "
        "WHERE dest = ? AND arr_abs BETWEEN ? AND ? ORDER BY arr_abs, flight, origin",
        (row.destination_airport, base + start_min, base + end_min),
    )
    own_dep = base + hhmm_to_min(row.scheduled_departure)
    return tuple(
        ScheduledArrival(flight_id=flight, arrival_min=arr_abs - base)
        for flight, arr_abs, origin, dep_abs in found
        if not (
            flight == row.flight_id
            and origin == row.origin_airport
            and dep_abs == own_dep
        )
    )


def daily_arrivals(row: DotRow, path: str | os.PathLike[str] | None = None) -> int:
    """Scheduled arrivals into the destination on the row's departure date."""
    con = ensure_cache(path)
    base = row.day_start_abs
    result = con.execute(
        "SELECT COUNT(*) FROM flights WHERE dest = ? AND arr_abs >= ? AND arr_abs < ?",
        (row.destination_airport, base, base + MINUTES_PER_DAY),
    ).fetchone()
    return int(result[0])


def next_leg(row: DotRow, path: str | os.PathLike[str] | None = None) -> NextLeg | None:
    """The same tail's next scheduled departure from this destination, later on
    the same date than this flight's scheduled arrival. None if there is none."""
    con = ensure_cache(path)
    base = row.day_start_abs
    arrival = base + scheduled_arrival_min(row)
    found = con.execute(
        "SELECT flight, dest, dep_abs, dep_delay FROM flights "
        "WHERE tail = ? AND origin = ? AND dep_abs > ? AND dep_abs < ? "
        "ORDER BY dep_abs, flight LIMIT 1",
        (
            row.tail_number,
            row.destination_airport,
            arrival,
            base + MINUTES_PER_DAY,
        ),
    ).fetchone()
    if found is None:
        return None
    flight, destination, dep_abs, dep_delay = found
    return NextLeg(
        flight_id=flight,
        destination=destination,
        scheduled_departure_min=dep_abs - base,
        departure_delay_min=dep_delay,
    )


def typical_taxi_in(
    airport: str, path: str | os.PathLike[str] | None = None
) -> int | None:
    """Median TAXI_IN over the whole file for an airport, or None if too few
    flights to say."""
    con = ensure_cache(path)
    found = con.execute(
        "SELECT median_min, samples FROM taxi_in WHERE airport = ?", (airport,)
    ).fetchone()
    if found is None or found[1] < MIN_TAXI_SAMPLES:
        return None
    return int(found[0])
