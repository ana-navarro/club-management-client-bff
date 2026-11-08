import os
import ssl
from collections.abc import Mapping
from functools import lru_cache

import httpx

REQUIRED_VARIABLES = ("USERS_SVC_URL", "TLS_CA", "TLS_CERT", "TLS_KEY")
TIMEOUT_SECONDS = 10.0


def create_http_client(env: Mapping[str, str]) -> httpx.Client:
    """Creates the client for internal calls: it verifies the server and presents a certificate."""
    missing = [name for name in REQUIRED_VARIABLES if not env.get(name)]
    if missing:
        raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")

    context = ssl.create_default_context(cafile=env["TLS_CA"])
    context.load_cert_chain(certfile=env["TLS_CERT"], keyfile=env["TLS_KEY"])
    return httpx.Client(base_url=env["USERS_SVC_URL"], verify=context, timeout=TIMEOUT_SECONDS)


@lru_cache(maxsize=1)
def get_http_client() -> httpx.Client:
    return create_http_client(os.environ)
