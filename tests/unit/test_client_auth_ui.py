import pytest

from kongfu_chess.client import AuthUiConfig, AuthUiMode


def test_production_auth_ui_defaults_to_portable_opencv_and_disables_cli():
    config = AuthUiConfig()

    assert config.mode is AuthUiMode.OPENCV
    assert config.cli_debug_enabled is False


def test_cli_auth_requires_explicit_debug_enablement():
    with pytest.raises(ValueError, match="explicit debug"):
        AuthUiConfig(mode=AuthUiMode.CLI_DEBUG)

    enabled = AuthUiConfig(
        mode=AuthUiMode.CLI_DEBUG,
        cli_debug_enabled=True,
    )
    assert enabled.mode is AuthUiMode.CLI_DEBUG
