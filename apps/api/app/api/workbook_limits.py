"""Where this system departs from the challenge workbook, stated for the organisers.

Words only: no figure from a run appears here. Each statement was checked against
the code named in `checked_against`; change a statement only with that code.
"""

from typing import Final

from app.negotiation.contracts import FrozenModel


class WorkbookDifference(FrozenModel):
    id: str
    limit: str  # the topic, in a few words
    what_we_do: str
    why: str
    checked_against: str  # where in apps/api/app/negotiation the statement was checked


class WorkbookLimits(FrozenModel):
    title: str
    items: tuple[WorkbookDifference, ...]


TITLE: Final = "Where we differ from the challenge workbook"

DIFFERENCES: Final[tuple[WorkbookDifference, ...]] = (
    WorkbookDifference(
        id="turns",
        limit="Negotiation turns",
        what_we_do=(
            "The organisers' brief says to reach consensus within 3 turns, and that "
            "with no agreement after 3 turns the fallback decides. We stop at 2."
        ),
        why=(
            "Two turns stays within the brief's limit and bounds the time and model "
            "calls per flight. The cap is fixed in code, and when the agents have not "
            "agreed by then, code picks the cheapest recovery plan that passes every "
            "rule."
        ),
        checked_against="protocol.py: MAX_TURNS and the turn_cap_no_agreement fallback",
    ),
    WorkbookDifference(
        id="runway_capacity",
        limit="Runway capacity",
        what_we_do=(
            "We count arrivals only. A closed runway does not lower the airport's "
            "hourly limit."
        ),
        why=(
            "The scenario holds no departures, so the count of movements is lighter "
            "than the workbook's and the check is the more lenient side of its "
            "limit. The limit is the workbook's total for the airport, and closing "
            "a runway in a scenario leaves that total as it was."
        ),
        checked_against=(
            "rules/atc.py: check_runway_throughput; "
            "scenario.py: airport_ops_per_hour and closed_runways"
        ),
    ),
    WorkbookDifference(
        id="fuel_on_board",
        limit="Fuel on board",
        what_we_do=(
            "Fuel on board is synthetic and varies by flight. It is usually above "
            "the workbook's 45-minute default, so the fuel rule binds less often "
            "than it would at the default."
        ),
        why=(
            "Each flight carries its trip fuel, the 45 minutes of holding fuel plus "
            "a seeded amount that is usually extra, and any alternate fuel. A small "
            "share of airborne flights start below the final reserve, so the rule "
            "still has cases to catch."
        ),
        checked_against=(
            "scenario.py: GeneratorParams.surplus_tiers, surplus_pre_departure_min "
            "and the fuel block of build_scenario"
        ),
    ),
    WorkbookDifference(
        id="alternate_fuel",
        limit="Alternate-fuel test",
        what_we_do=(
            "We keep an extra test: if the forecast from an hour before to an hour "
            "after arrival is poor, or is missing, the flight must also carry fuel "
            "for an alternate airport."
        ),
        why=(
            "It is our own policy, shaped on a dispatch rule (14 CFR 121.619(a)). It "
            "is not in the workbook and it is not the regulation."
        ),
        checked_against=(
            "rules/pilot.py: alternate_required; "
            "rule_values.py: ALTERNATE_* values, status policy"
        ),
    ),
    WorkbookDifference(
        id="synthetic_fields",
        limit="Crew report time and gate sizes",
        what_we_do="Crew report time and gate sizes are synthetic and ours.",
        why=(
            "The workbook gives gate counts, not gate sizes, and no crew report "
            "times. Decision time is not in this group: it is worked out from the "
            "schedule by our own rule."
        ),
        checked_against=(
            "scenario.py: FIELD_NOTES, decision_time_min (derived), "
            "crew_report_min and gates"
        ),
    ),
    WorkbookDifference(
        id="hold_burn",
        limit="Holding fuel burn",
        what_we_do=(
            "The wide-body holding burn of 6,500 kg an hour is rounded up to 109 kg "
            "a minute."
        ),
        why=(
            "We work in whole kilograms a minute, and rounding up asks for slightly "
            "more fuel, which is the safe side."
        ),
        checked_against="rule_values.py: hold_burn_kg_per_min",
    ),
    WorkbookDifference(
        id="departure_wake",
        limit="Departure wake times",
        what_we_do="We do not use the workbook's wake times for departures.",
        why="We only sequence arrivals.",
        checked_against="rule_values.py: the note beside the wake table",
    ),
    WorkbookDifference(
        id="flights_file",
        limit="Flights file",
        what_we_do=(
            "We read the full flights file, not only the eligible rows. Our 358,774 "
            "eligible rows match the organisers' filtered file exactly, and both "
            "leave out October."
        ),
        why=(
            "The full file lets us follow an aircraft to its next flight, which "
            "needs rows the filtered file drops."
        ),
        checked_against="dot.py: is_eligible and the schedule table",
    ),
)


def read_limits() -> WorkbookLimits:
    return WorkbookLimits(title=TITLE, items=DIFFERENCES)
