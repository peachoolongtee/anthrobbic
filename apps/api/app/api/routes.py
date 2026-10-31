"""Dashboard routes. Handlers stay thin; `RunService` does the work."""

from typing import Annotated

from fastapi import APIRouter, Body, Depends, Query, Request

from app.api.evaluation import read_evaluation
from app.api.runs import RunRequest, RunService, StateChange, VerifyRequest
from app.api.wire import (
    Evaluation,
    RunLog,
    RunView,
    ScenarioSummary,
    SignoffResult,
    StateChanged,
    VerifyLogResult,
)
from app.negotiation.dot import Cause
from app.negotiation.signoff import SignOffRequest

router = APIRouter()


def get_service(request: Request) -> RunService:
    service: RunService = request.app.state.runs
    return service


Service = Annotated[RunService, Depends(get_service)]


@router.get("/scenarios")
def list_scenarios(
    service: Service,
    cause: Cause | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[ScenarioSummary]:
    return service.catalogue.summaries(cause, limit)


@router.post("/runs")
def create_run(service: Service, body: RunRequest) -> RunView:
    return service.create_run(body)


@router.post("/runs/{run_id}/state")
def change_state(service: Service, run_id: str, body: StateChange) -> StateChanged:
    return service.change_state(run_id, body)


@router.post("/runs/{run_id}/signoff")
def sign_off(service: Service, run_id: str, body: SignOffRequest) -> SignoffResult:
    return service.sign_off(run_id, body)


@router.get("/runs/{run_id}/log")
def get_log(service: Service, run_id: str) -> RunLog:
    return service.log(run_id)


@router.post("/runs/{run_id}/log/verify")
def verify_log(
    service: Service,
    run_id: str,
    body: Annotated[VerifyRequest | None, Body()] = None,
) -> VerifyLogResult:
    return service.verify_log(run_id, body or VerifyRequest())


@router.get("/evaluation")
def get_evaluation(service: Service) -> Evaluation:
    return read_evaluation(service.results_dir)
