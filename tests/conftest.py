"""Shared fixtures. The Home Assistant fixtures exist only when the harness is installed."""
import pytest

try:
    import pytest_homeassistant_custom_component  # noqa: F401
except ImportError:
    pass
else:
    @pytest.fixture(autouse=True)
    def _enable_custom_integrations(request):
        """Let Home Assistant load this repo's integration in tests that use `hass`."""
        if "hass" in request.fixturenames:
            request.getfixturevalue("enable_custom_integrations")
