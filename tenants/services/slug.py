"""Slug helpers for workspace URLs."""
from django.utils.text import slugify

from tenants.models import Workspace


def build_unique_slug(name: str) -> str:
    base = slugify(name) or "workspace"
    slug = base
    suffix = 1
    while Workspace.objects.filter(slug=slug).exists():
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug
