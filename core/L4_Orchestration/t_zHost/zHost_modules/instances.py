"""Instance lifecycle — wake / sleep / inspect a single app instance.

The backend (local process in dev, k8s in prod) is chosen by env behind
``get_driver``, so the wake/sleep flow is identical everywhere. This is the
control-plane counterpart the SDK's ``instance`` facade delegates to.
"""

from typing import Any


class InstancesMixin:
    """wake / sleep / status over the active compute driver."""

    zos: Any

    def _driver(self):
        from zos_plugin.drivers import get_driver  # pylint: disable=import-outside-toplevel

        return get_driver(self.zos)

    def wake(self, app: Any, timeout: float = 25.0):
        """Ensure ``app`` is running and reachable; return its :class:`Instance`."""
        from zos_plugin import AppSpec  # pylint: disable=import-outside-toplevel

        return self._driver().wake(AppSpec.coerce(app), timeout=timeout)

    def sleep(self, app: Any) -> bool:
        """Tear down the app's instance. Accepts an app_id or an app spec."""
        from zos_plugin import AppSpec  # pylint: disable=import-outside-toplevel

        app_id = app if isinstance(app, str) else AppSpec.coerce(app).app_id
        return self._driver().sleep(app_id)

    def status(self, app: Any):
        """Current :class:`Instance` (asleep / waking / running) — never raises."""
        from zos_plugin import AppSpec  # pylint: disable=import-outside-toplevel

        app_id = app if isinstance(app, str) else AppSpec.coerce(app).app_id
        return self._driver().status(app_id)
