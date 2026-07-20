import copy
import json
from pathlib import Path

import pytest

from kongfu_chess.infrastructure.configuration import ConfigError, ConfigProvider


CONFIG_PATH = Path(__file__).parents[2] / "config" / "server.json"


def test_default_server_configuration_loads_all_operational_contracts():
    config = ConfigProvider.load(CONFIG_PATH)

    assert config.network.host == "127.0.0.1"
    assert config.network.protocol_version == "1.0"
    assert config.timing.reconnect_grace_seconds == 20
    assert config.elo.k_factor == 32
    assert config.capacity.spectators_per_room == 10
    assert config.database.path.is_absolute()
    assert config.logging.max_bytes == 100 * 1024 * 1024


def test_configuration_rejects_missing_section():
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    del document["network"]

    with pytest.raises(ConfigError, match="network must be an object"):
        ConfigProvider.from_mapping(document)


@pytest.mark.parametrize("invalid_port", [0, 65536, "8765", True])
def test_configuration_rejects_invalid_port(invalid_port):
    document = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    document = copy.deepcopy(document)
    document["network"]["port"] = invalid_port

    with pytest.raises(ConfigError, match="port"):
        ConfigProvider.from_mapping(document)
