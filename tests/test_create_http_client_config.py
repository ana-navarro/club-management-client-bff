import ssl
from pathlib import Path

import pytest

from src.config.create_http_client_config import create_http_client


def test_names_every_missing_variable() -> None:
    with pytest.raises(RuntimeError, match="USERS_SVC_URL, TLS_KEY"):
        create_http_client({"TLS_CA": "c", "TLS_CERT": "r"})


def test_refuses_an_unreadable_authority(tmp_path: Path) -> None:
    env = {
        "USERS_SVC_URL": "https://users-svc",
        "TLS_CA": str(tmp_path / "missing.crt"),
        "TLS_CERT": str(tmp_path / "missing.crt"),
        "TLS_KEY": str(tmp_path / "missing.key"),
    }
    with pytest.raises((OSError, ssl.SSLError)):
        create_http_client(env)
