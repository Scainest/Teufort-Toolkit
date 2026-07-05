"""Path helpers shared by the export modules."""

from __future__ import annotations

import os


def resolve_target_dir(export_dir: str, relative_dir: str) -> str:
    """Join `export_dir` + `relative_dir`, but collapse any overlap so the
    subpath is never duplicated.

    If the user browses straight into the deep folder (or any leading part
    of it), e.g. selecting
        .../custom/MyMod/scripts/items/custom_texture_blend_layers
    we must NOT append the whole chain again and produce
        .../custom_texture_blend_layers/scripts/items/custom_texture_blend_layers

    The overlap is matched on the tail of `export_dir` against the head of
    `relative_dir`, case-insensitively (Windows paths are case-insensitive).
    """
    rel_parts = [p for p in relative_dir.replace("/", os.sep).split(os.sep) if p]
    norm = os.path.normpath(export_dir)
    existing = [p for p in norm.split(os.sep) if p]

    for k in range(len(rel_parts), 0, -1):
        if len(existing) >= k and (
            [p.lower() for p in existing[-k:]]
            == [p.lower() for p in rel_parts[:k]]
        ):
            return os.path.join(norm, *rel_parts[k:])
    return os.path.join(norm, *rel_parts)
