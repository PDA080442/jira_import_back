"""Profile read/update for /api/me/ (locale, timezone, notifications)."""
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from accounts.models import Profile, User
from audit.services.log_action import log_action
from core.exceptions import ApiError
from core.logging import get_logger

logger = get_logger("accounts.profile")


def get_profile(user: User) -> Profile:
    return Profile.objects.select_related("user").get(user=user)


def validate_timezone(timezone_name: str) -> None:
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ApiError(
            detail="Invalid timezone.",
            code="VALIDATION_ERROR",
            status_code=400,
            field_errors={"timezone": ["Invalid timezone."]},
        ) from exc


def update_profile(user: User, *, data: dict) -> Profile:
    profile = get_profile(user)
    changed: dict = {}

    if "locale" in data:
        profile.locale = data["locale"]
        changed["locale"] = data["locale"]

    if "timezone" in data:
        validate_timezone(data["timezone"])
        profile.timezone = data["timezone"]
        changed["timezone"] = data["timezone"]

    if "notification_preferences" in data:
        profile.notification_preferences = data["notification_preferences"]
        changed["notification_preferences"] = data["notification_preferences"]

    if changed:
        profile.save()
        log_action(
            action="profile.update",
            entity_type="profile",
            entity_id=str(profile.id),
            actor=user,
            payload=changed,
        )
        logger.info("profile_updated", user_id=str(user.id), fields=list(changed.keys()))

    return profile
