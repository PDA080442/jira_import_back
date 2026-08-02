"""Read access to published help guides."""
from rest_framework import status

from core.exceptions import ApiError
from jira.models import JiraGuide


def list_guides():
    return JiraGuide.objects.filter(is_published=True).order_by("slug")


def get_guide(*, slug: str) -> JiraGuide:
    try:
        return JiraGuide.objects.get(slug=slug, is_published=True)
    except JiraGuide.DoesNotExist as exc:
        raise ApiError(
            detail="Guide not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
