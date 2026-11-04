"""Mammoth Paths: the MammothOS workspace SDK.

Embed Mammoth Mind agent runs, repository sources, notes, the build log, and the
owner terminal in your own software. The tutor SDK (``MammothMind`` /
``AtlasFAB``) is separate and unchanged.
"""

from mammoth_os.paths.client import (
    PATHS_CONTRACT_VERSION,
    RUN_CONTRACT_VERSION,
    MammothPaths,
    PathsError,
    RunEvent,
    RunResult,
    iter_sse,
)
from mammoth_os.paths.branch_export import decode_branch_export as decode_owner_branch_export

__all__ = [
    "PATHS_CONTRACT_VERSION",
    "RUN_CONTRACT_VERSION",
    "MammothPaths",
    "PathsError",
    "RunEvent",
    "RunResult",
    "iter_sse",
    "decode_owner_branch_export",
]
