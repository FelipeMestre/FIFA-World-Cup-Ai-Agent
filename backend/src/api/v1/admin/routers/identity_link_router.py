"""Admin-only review endpoints for `player_identity_link` matches below the
auto-accept confidence threshold.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.v1.admin.dtos.identity_link_dtos import (
    IdentityLinkResponse,
    IdentityLinkReviewResponse,
    PaginatedIdentityLinkReviewResponse,
    ReassignLinkRequest,
    RematchIdentityLinksRequest,
    RematchTriggerResponse,
)
from src.api.v1.auth.services.dependencies import require_admin
from src.domain.ingestion.exceptions.ingestion_exceptions import (
    IdentityLinkAlreadyReviewedError,
    IdentityLinkNotFoundError,
    RealPlayerAlreadyLinkedError,
    RealPlayerNotFoundError,
)
from src.domain.ingestion.model.ingestion_job import (
    IngestionJob,
    IngestionJobStatus,
    IngestionJobType,
)
from src.domain.ingestion.model.player_identity_link import LinkReviewStatus
from src.domain.ingestion.services.identity_link_review_service import (
    PlayerIdentityLinkReviewService,
)
from src.infra.postgres.interfaces.ingestion_job_repository_interface import (
    IngestionJobRepositoryInterface,
)
from src.infra.postgres.interfaces.player_identity_link_repository_interface import (
    PlayerIdentityLinkRepositoryInterface,
)
from src.infra.postgres.repositories.ingestion_job_repository import get_ingestion_job_repository
from src.infra.postgres.repositories.player_identity_link_repository import (
    get_player_identity_link_repository,
)
from src.infra.task_queue.pool import enqueue_identity_link_rematch

router = APIRouter(prefix="/admin/identity-links", tags=["admin-identity-links"])

AdminDep = Annotated[dict, Depends(require_admin)]
IngestionJobRepositoryDep = Annotated[
    IngestionJobRepositoryInterface, Depends(get_ingestion_job_repository)
]


def get_identity_link_review_service(
    repository: Annotated[
        PlayerIdentityLinkRepositoryInterface, Depends(get_player_identity_link_repository)
    ],
) -> PlayerIdentityLinkReviewService:
    return PlayerIdentityLinkReviewService(repository)


ReviewServiceDep = Annotated[
    PlayerIdentityLinkReviewService, Depends(get_identity_link_review_service)
]


@router.get(
    "",
    response_model=PaginatedIdentityLinkReviewResponse,
    summary="List identity-link matches with full comparison data, filterable by status",
)
async def list_links(
    service: ReviewServiceDep,
    admin: AdminDep,
    review_status: Annotated[
        LinkReviewStatus | None, Query(alias="status")
    ] = LinkReviewStatus.PENDING,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> PaginatedIdentityLinkReviewResponse:
    reviews = await service.list_by_status(review_status, limit=limit, offset=offset)
    total = await service.count_by_status(review_status)
    return PaginatedIdentityLinkReviewResponse(
        items=[IdentityLinkReviewResponse.from_domain(review) for review in reviews],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/rematch",
    response_model=RematchTriggerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Wipe and regenerate every player_identity_link from scratch",
    description="Admin-only. Deletes every player_identity_link row (including "
    "admin-reviewed ones) and queues a from-scratch rematch against the "
    "already-persisted player/real_player tables -- no Transfermarkt HTTP calls, "
    "no CSV re-parsing. Destructive: requires confirm=true.",
    responses={status.HTTP_400_BAD_REQUEST: {"description": "confirm was not explicitly true"}},
)
async def rematch_identity_links(
    admin: AdminDep,
    job_repository: IngestionJobRepositoryDep,
    request: RematchIdentityLinksRequest | None = None,
) -> RematchTriggerResponse:
    request = request or RematchIdentityLinksRequest()
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="confirm must be explicitly true -- this deletes every "
            "player_identity_link row, including admin-reviewed ones",
        )

    job = IngestionJob(
        id=None,
        job_type=IngestionJobType.IDENTITY_LINK_REMATCH,
        status=IngestionJobStatus.QUEUED,
        source_label="admin-triggered-rematch",
        requested_by_user_id=int(admin["sub"]),
    )
    created_job = await job_repository.create(job)
    await enqueue_identity_link_rematch(created_job.id)
    return RematchTriggerResponse(job_id=created_job.id, status=created_job.status.value)


@router.post(
    "/{link_id}/approve",
    response_model=IdentityLinkResponse,
    summary="Approve a pending identity-link match",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Link not found"},
        status.HTTP_409_CONFLICT: {"description": "Link is not currently pending"},
    },
)
async def approve_link(
    link_id: int, service: ReviewServiceDep, admin: AdminDep
) -> IdentityLinkResponse:
    link = await _review(service.approve, link_id, admin)
    return IdentityLinkResponse.from_domain(link)


@router.post(
    "/{link_id}/reject",
    response_model=IdentityLinkResponse,
    summary="Reject a pending identity-link match",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Link not found"},
        status.HTTP_409_CONFLICT: {"description": "Link is not currently pending"},
    },
)
async def reject_link(
    link_id: int, service: ReviewServiceDep, admin: AdminDep
) -> IdentityLinkResponse:
    link = await _review(service.reject, link_id, admin)
    return IdentityLinkResponse.from_domain(link)


@router.post(
    "/{link_id}/reassign",
    response_model=IdentityLinkResponse,
    summary="Correct a doubtful identity-link match to a different real_player",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "Link or real_player not found"},
        status.HTTP_409_CONFLICT: {
            "description": "real_player is already linked to a different player"
        },
    },
)
async def reassign_link(
    link_id: int, body: ReassignLinkRequest, service: ReviewServiceDep, admin: AdminDep
) -> IdentityLinkResponse:
    try:
        link = await service.reassign(link_id, body.real_player_id, admin_user_id=int(admin["sub"]))
    except (IdentityLinkNotFoundError, RealPlayerNotFoundError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except RealPlayerAlreadyLinkedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return IdentityLinkResponse.from_domain(link)


async def _review(action, link_id: int, admin: dict):
    try:
        return await action(link_id, admin_user_id=int(admin["sub"]))
    except IdentityLinkNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except IdentityLinkAlreadyReviewedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
