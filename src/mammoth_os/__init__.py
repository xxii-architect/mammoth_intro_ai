"""Public package surface for MammothOS."""

from mammoth_os.atlas_session import ATLASSession
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
)

__all__ = [
    "ATLASSession",
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

__version__ = "0.5.0"
