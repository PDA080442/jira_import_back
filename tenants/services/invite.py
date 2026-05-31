"""Workspace invite create and accept flows."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from accounts.models import User
from accounts.services.tokens import generate_raw_token, hash_token, is_token_expired
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger
from rest_framework import status
from tenants.models import INVITE_ROLES, Workspace, WorkspaceInvite, WorkspaceMembership, WorkspaceRole
from tenants.services.membership import get_membership, user_has_admin_role

logger = get_logger("tenants.invite")


def invite_expires_at():
    hours = getattr(settings, "WORKSPACE_INVITE_TTL_HOURS", 168)
    return timezone.now() + timedelta(hours=hours)


def invalidate_pending_invites(*, workspace: Workspace, email: str) -> None:
    WorkspaceInvite.objects.filter(
        workspace=workspace,
        email=email,
        used_at__isnull=True,
    ).update(used_at=timezone.now())


@transaction.atomic
def create_invite(*, workspace: Workspace, user: User, email: str, role: str) -> WorkspaceInvite:
    from tenants.tasks import send_workspace_invite_email

    if not user_has_admin_role(user=user, workspace=workspace):
        raise ApiError(
            detail="You do not have permission to invite members.",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    if role == WorkspaceRole.OWNER or role not in INVITE_ROLES:
        raise ApiError(
            detail="Invalid invite role.",
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            field_errors={"role": ["Cannot invite with this role."]},
        )

    email = User.objects.normalize_email(email)

    if WorkspaceMembership.objects.filter(workspace=workspace, user__email=email).exists():
        raise ApiError(
            detail="User is already a member.",
            code="VALIDATION_ERROR",
            status_code=status.HTTP_400_BAD_REQUEST,
            field_errors={"email": ["User is already a member of this workspace."]},
        )

    invalidate_pending_invites(workspace=workspace, email=email)
    raw_token = generate_raw_token()
    invite = WorkspaceInvite.objects.create(
        workspace=workspace,
        email=email,
        role=role,
        token_hash=hash_token(raw_token),
        invited_by=user,
        expires_at=invite_expires_at(),
    )
    send_workspace_invite_email.delay(str(invite.id), raw_token)

    log_action(
        action="invite.create",
        entity_type="workspace_invite",
        entity_id=str(invite.id),
        actor=user,
        payload={"email": email, "role": role},
    )
    logger.info("invite_created", workspace_id=str(workspace.id), invite_id=str(invite.id))
    return invite


@transaction.atomic
def accept_invite(*, user: User, raw_token: str) -> WorkspaceMembership:
    token_hash = hash_token(raw_token)
    try:
        invite = WorkspaceInvite.objects.select_related("workspace").get(token_hash=token_hash)
    except WorkspaceInvite.DoesNotExist as exc:
        raise ApiError(
            detail="Invalid invite token.",
            code="TOKEN_INVALID",
            status_code=status.HTTP_400_BAD_REQUEST,
        ) from exc

    if invite.used_at is not None:
        raise ApiError(
            detail="Invalid invite token.",
            code="TOKEN_INVALID",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if is_token_expired(invite.expires_at):
        raise ApiError(
            detail="Invite token has expired.",
            code="TOKEN_EXPIRED",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    if User.objects.normalize_email(user.email) != User.objects.normalize_email(invite.email):
        raise ApiError(
            detail="Invite email does not match your account.",
            code="FORBIDDEN",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    existing = get_membership(user=user, workspace=invite.workspace)
    if existing is not None:
        invite.used_at = timezone.now()
        invite.save(update_fields=["used_at"])
        return existing

    membership = WorkspaceMembership.objects.create(
        workspace=invite.workspace,
        user=user,
        role=invite.role,
    )
    invite.used_at = timezone.now()
    invite.save(update_fields=["used_at"])

    log_action(
        action="invite.accept",
        entity_type="workspace_membership",
        entity_id=str(membership.id),
        actor=user,
        payload={"workspace_id": str(invite.workspace_id), "role": invite.role},
    )
    logger.info("invite_accepted", workspace_id=str(invite.workspace_id), user_id=str(user.id))
    return membership
