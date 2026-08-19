"""Public package surface for MammothOS."""

from mammoth_os.atlas_session import ATLASSession
from mammoth_os.sdk import AtlasFAB, AtlasFABConfig

__all__ = ["ATLASSession", "AtlasFAB", "AtlasFABConfig", "__version__"]

__version__ = "0.5.0"
