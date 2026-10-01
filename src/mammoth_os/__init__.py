"""Public package surface for MammothOS."""

from mammoth_os.atlas_session import ATLASSession, LessonGateError
from mammoth_os.sdk import (
    AtlasFAB,
    AtlasFABConfig,
    AtlasFABError,
    AtlasGenerationReport,
    AtlasLessonSnapshot,
    AtlasProgressSnapshot,
    AtlasRuntimeSnapshot,
    AtlasSubmissionReport,
    AtlasUsageSnapshot,
    MammothMind,
    MammothMindConfig,
    MammothMindError,
)
from mammoth_os.paths import MammothPaths, PathsError

__all__ = [
    "MammothMind",
    "MammothMindConfig",
    "MammothMindError",
    "MammothPaths",
    "PathsError",
    "ATLASSession",
    "LessonGateError",
    "AtlasFAB",
    "AtlasFABConfig",
    "AtlasFABError",
    "AtlasGenerationReport",
    "AtlasLessonSnapshot",
    "AtlasProgressSnapshot",
    "AtlasRuntimeSnapshot",
    "AtlasSubmissionReport",
    "AtlasUsageSnapshot",
    "__version__",
]

__version__ = "0.6.0"
