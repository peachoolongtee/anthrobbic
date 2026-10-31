"""Sign-off: the duty manager's approval, checked against the state now.

Approval is only given if the package, the operational state and the card are
all exactly what the manager saw, every hard rule still passes, and the
request has not been used before. Approval means the requests were issued. It
does not mean ATC granted them, and nothing is executed here. The outcome is
written to the evidence log, and approval is returned only once that write has
succeeded.
"""

import hashlib
import json
import threading
from collections.abc import Mapping, MutableSet
from enum import StrEnum
from typing import Any, Self

from pydantic import model_validator

from app.negotiation.card import (
    Card,
    PackageTerm,
    authority_terms,
    card_hash_of,
    changed_card_fields,
    decision_card,
    package_name,
)
from app.negotiation.contracts import FrozenModel, Package, Scenario, Violation
from app.negotiation.log import EvidenceLog
from app.negotiation.rules import check_package
from app.negotiation.utility import DEFAULT_WEIGHTS, CostWeights, compute_cost

UNATTRIBUTED = "unattributed"

_LOCK = threading.Lock()


def _digest(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(text.encode()).hexdigest()


def field_versions(scenario: Scenario) -> Mapping[str, str]:
    """A hash per scenario field, value and provenance together."""
    return {
        name: _digest(getattr(scenario, name).model_dump(mode="json"))
        for name in type(scenario).model_fields
    }


def versions_root(versions: Mapping[str, str]) -> str:
    return _digest(dict(versions))


def state_version(scenario: Scenario) -> str:
    """Hash of everything in the scenario: every operational field (runways,
    taxiways, gates, occupancies, other arrivals, forecast, fuel, planning
    window, ground shift, connections, next leg) and its provenance label.

    Any change while the manager reads gives a different value. List order is
    part of the hash, so a reorder counts as a change; refusing too often is
    the safe error.
    """
    return versions_root(field_versions(scenario))


def changed_state_fields(
    seen: Mapping[str, str] | None, current: Mapping[str, str], seen_root: str
) -> tuple[str, ...]:
    """Which fields changed. A per-field record that does not add up to the
    version the manager saw cannot be trusted, so it attributes nothing."""
    if seen is None or versions_root(seen) != seen_root:
        return (UNATTRIBUTED,)
    names = [n for n in (*current, *seen) if seen.get(n) != current.get(n)]
    return tuple(dict.fromkeys(names))


class SignOffStatus(StrEnum):
    APPROVED = "APPROVED"
    REFUSED_STATE_CHANGED = "REFUSED_STATE_CHANGED"
    REFUSED_PACKAGE_CHANGED = "REFUSED_PACKAGE_CHANGED"
    REFUSED_CARD_CHANGED = "REFUSED_CARD_CHANGED"
    REFUSED_RULES_FAILED = "REFUSED_RULES_FAILED"
    REFUSED_ALREADY_USED = "REFUSED_ALREADY_USED"


class SignOffRequest(FrozenModel):
    """What the duty manager saw and decided.

    `field_versions_seen` and `card_field_hashes_seen` are optional. They let a
    refusal name the fields that changed; without them it says it cannot.
    """

    terms_hash: str
    state_version_seen: str
    card_hash_seen: str
    decided_by: str
    airline_decisions_approved: bool
    requests_to_send: bool
    field_versions_seen: Mapping[str, str] | None = None
    card_field_hashes_seen: Mapping[str, str] | None = None

    @model_validator(mode="after")
    def _a_real_sign_off(self) -> Self:
        if not self.decided_by.strip():
            raise ValueError("decided_by must name the person")
        if not (self.airline_decisions_approved or self.requests_to_send):
            raise ValueError("a sign-off must approve a decision or send a request")
        return self

    @property
    def token(self) -> str:
        """One approval per package, state and card as seen."""
        return _digest([self.terms_hash, self.state_version_seen, self.card_hash_seen])


class SignOffOutcome(FrozenModel):
    status: SignOffStatus
    package_name: str
    violations: tuple[Violation, ...]
    changed_fields: tuple[str, ...]
    changed_card_fields: tuple[str, ...]
    airline_decisions: tuple[PackageTerm, ...]
    requests: tuple[PackageTerm, ...]
    card_hash: str
    # The head after the sign-off entry: the value to anchor and to show.
    log_head: str


def _violation_record(v: Violation) -> dict[str, Any]:
    return {
        "rule_id": v.rule_id,
        "observed": v.observed,
        "limit": v.limit,
        "unit": v.unit,
        "cause": v.cause.value,
    }


def sign_off(
    request: SignOffRequest,
    package: Package,
    current_scenario: Scenario,
    log: EvidenceLog,
    used_tokens: MutableSet[str],
    *,
    weights: CostWeights = DEFAULT_WEIGHTS,
) -> SignOffOutcome:
    """Decide a sign-off against the current state and record it.

    Checked in this order, and the first failure is the status: token unused,
    package unchanged, state unchanged, every rule passes, card unchanged.
    Violations are always reported. Only an approval uses up the token.

    `weights` must be those the card was built with. The rebuilt card also
    leaves out reasons, since explanations never block a sign-off.
    """
    with _LOCK:
        versions = field_versions(current_scenario)
        current_state = versions_root(versions)
        violations = check_package(current_scenario, package)
        card: Card = decision_card(
            current_scenario,
            package,
            compute_cost(current_scenario, package, weights),
            violations,
            state_version=current_state,
        )

        changed: tuple[str, ...] = ()
        changed_card: tuple[str, ...] = ()
        if request.token in used_tokens:
            status = SignOffStatus.REFUSED_ALREADY_USED
        elif request.terms_hash != package.terms_hash:
            status = SignOffStatus.REFUSED_PACKAGE_CHANGED
        elif request.state_version_seen != current_state:
            status = SignOffStatus.REFUSED_STATE_CHANGED
            changed = changed_state_fields(
                request.field_versions_seen, versions, request.state_version_seen
            )
        elif violations:
            status = SignOffStatus.REFUSED_RULES_FAILED
        elif request.card_hash_seen != card.card_hash:
            status = SignOffStatus.REFUSED_CARD_CHANGED
            seen = request.card_field_hashes_seen
            if seen is not None and card_hash_of(seen) != request.card_hash_seen:
                seen = None  # does not add up to the hash the manager saw
            changed_card = changed_card_fields(seen, card.field_hashes) or (
                UNATTRIBUTED,
            )
        else:
            status = SignOffStatus.APPROVED

        approved = status is SignOffStatus.APPROVED
        airline, requests = authority_terms(package)
        airline = airline if approved and request.airline_decisions_approved else ()
        requests = requests if approved and request.requests_to_send else ()

        entry = log.append(
            "signoff",
            {
                "status": status.value,
                "package_name": package_name(package),
                "terms_hash": package.terms_hash,
                "terms_hash_seen": request.terms_hash,
                "state_version_seen": request.state_version_seen,
                "state_version_current": current_state,
                "card_hash_seen": request.card_hash_seen,
                "card_hash": card.card_hash,
                "decided_by": request.decided_by,
                "violations": [_violation_record(v) for v in violations],
                "changed_fields": list(changed),
                "changed_card_fields": list(changed_card),
                "airline_decisions": [t.model_dump() for t in airline],
                "requests": [t.model_dump() for t in requests],
                "log_head_before": log.head,
                "requests_issued_not_granted": approved and bool(requests),
                "executed": False,
            },
        )
        if approved:
            used_tokens.add(request.token)
        return SignOffOutcome(
            status=status,
            package_name=package_name(package),
            violations=violations,
            changed_fields=changed,
            changed_card_fields=changed_card,
            airline_decisions=airline,
            requests=requests,
            card_hash=card.card_hash,
            log_head=entry.entry_hash,
        )


_STATUS_LINES: Mapping[SignOffStatus, str] = {
    SignOffStatus.APPROVED: (
        "APPROVED. Requests were issued, not granted. Nothing has been executed."
    ),
    SignOffStatus.REFUSED_STATE_CHANGED: "REFUSED: the state changed after you looked.",
    SignOffStatus.REFUSED_PACKAGE_CHANGED: "REFUSED: the package is not the one shown.",
    SignOffStatus.REFUSED_CARD_CHANGED: "REFUSED: the card is not the one shown.",
    SignOffStatus.REFUSED_RULES_FAILED: "REFUSED: a hard rule fails now.",
    SignOffStatus.REFUSED_ALREADY_USED: "REFUSED: this sign-off was already used.",
}


def _terms(terms: tuple[PackageTerm, ...]) -> str:
    return "; ".join(f"{t.label}: {t.value}" for t in terms) or "none"


def render_record(outcome: SignOffOutcome) -> str:
    """The printable sign-off record. Fixed text and hashes only."""
    return "\n".join(
        [
            "SIGN-OFF RECORD",
            f"Package: {outcome.package_name}",
            f"Outcome: {_STATUS_LINES[outcome.status]}",
            f"Airline decisions: {_terms(outcome.airline_decisions)}",
            f"Requests to send: {_terms(outcome.requests)}",
            f"Rules failing: {len(outcome.violations)}",
            f"State fields changed: {', '.join(outcome.changed_fields) or 'none'}",
            f"Card fields changed: {', '.join(outcome.changed_card_fields) or 'none'}",
            f"Card hash: {outcome.card_hash}",
            f"Log head (anchor): {outcome.log_head}",
        ]
    )
