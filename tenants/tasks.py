"""Celery tasks for workspace invite emails."""
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from core.logging import get_logger

logger = get_logger("tenants.tasks")


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def send_workspace_invite_email(self, invite_id: str, raw_token: str) -> None:
    """Send invite link; raw_token only in task args, not in DB or logs."""
    from tenants.models import WorkspaceInvite

    invite = WorkspaceInvite.objects.select_related("workspace").get(id=invite_id)
    accept_url = f"{settings.FRONTEND_URL.rstrip('/')}/accept-invite?token={raw_token}"
    subject = f"Invitation to join {invite.workspace.name}"
    message = (
        f"Hello,\n\n"
        f"You have been invited to join workspace \"{invite.workspace.name}\" "
        f"with role \"{invite.role}\".\n\n"
        f"Accept the invitation:\n{accept_url}\n\n"
        f"If you did not expect this, ignore this email."
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[invite.email],
        fail_silently=False,
    )
    logger.info(
        "invite_email_sent",
        workspace_id=str(invite.workspace_id),
        invite_id=invite_id,
    )
