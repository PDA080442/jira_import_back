"""Celery tasks for auth emails (verify link, password reset link)."""
from celery import shared_task
from django.conf import settings
from django.core.mail import send_mail

from core.logging import get_logger

logger = get_logger("accounts.tasks")


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def send_verification_email(self, token_id: str, raw_token: str) -> None:
    """Send verify link; raw_token exists only in task args, not in DB or logs."""
    from accounts.models import EmailVerificationToken

    token = EmailVerificationToken.objects.select_related("user").get(id=token_id)
    verify_url = f"{settings.FRONTEND_URL.rstrip('/')}/verify-email?token={raw_token}"
    subject = "Confirm your email"
    message = (
        f"Hello,\n\n"
        f"Please confirm your email by opening this link:\n{verify_url}\n\n"
        f"If you did not register, ignore this email."
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[token.user.email],
        fail_silently=False,
    )
    logger.info("verification_email_sent", user_id=str(token.user_id), token_id=token_id)


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 5},
)
def send_password_reset_email(self, token_id: str, raw_token: str) -> None:
    from accounts.models import PasswordResetToken

    token = PasswordResetToken.objects.select_related("user").get(id=token_id)
    reset_url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password?token={raw_token}"
    subject = "Reset your password"
    message = (
        f"Hello,\n\n"
        f"Reset your password by opening this link:\n{reset_url}\n\n"
        f"If you did not request a reset, ignore this email."
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[token.user.email],
        fail_silently=False,
    )
    logger.info("password_reset_email_sent", user_id=str(token.user_id), token_id=token_id)
