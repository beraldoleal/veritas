"""Shared utilities for platform extractors."""


def remap_registry(image_ref: str, mirror_registry: str | None) -> str:
    """Replace the registry host in an image reference with mirror_registry.

    If mirror_registry is None, returns image_ref unchanged.
    Assumes the reference starts with a registry host, as is standard
    for all registries veritas uses.
    """
    if not mirror_registry:
        return image_ref
    _, rest = image_ref.split("/", 1)
    return f"{mirror_registry}/{rest}"
