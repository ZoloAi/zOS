"""Deployment-aware logging helpers for zConfigPaths."""

from zOS import logging, Any, Dict, Optional
from zSys.Utils import is_production_from_zspark, is_testing_from_zspark

logger = logging.getLogger(__name__)


class zConfigPathsLogging:
    """Deployment-aware logging helpers used during preboot initialization."""

    _verbose: bool

    def _check_testing_from_zspark(self, zSpark_obj: Optional[Dict[str, Any]]) -> bool:
        """Early check if zSpark indicates Testing deployment (for suppressing banners)."""
        return is_testing_from_zspark(zSpark_obj)

    def _check_production_from_zspark(self, zSpark_obj: Optional[Dict[str, Any]]) -> bool:
        """Check if deployment mode is Production from zSpark.

        Called during __init__ before environment config exists.
        """
        return is_production_from_zspark(zSpark_obj)

    def _log_info(self, message: str) -> None:
        """Log info message (shown only in preboot verbose mode)."""
        if self._verbose:
            logger.info("[zConfigPaths] %s", message)

    def _log_warning(self, message: str) -> None:
        """Log warning message (shown only in preboot verbose mode)."""
        if self._verbose:
            logger.warning("[zConfigPaths] %s", message)

    def _log_error(self, message: str) -> None:
        """Log error message (always shown)."""
        logger.error("[zConfigPaths] ERROR: %s", message)
