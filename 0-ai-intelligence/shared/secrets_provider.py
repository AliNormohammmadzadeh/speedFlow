"""Pluggable secrets provider (task 4.9).

Resolves secrets via SECRETS_PROVIDER:
  - env   (default): os.environ
  - vault : HashiCorp Vault KV v2 (hvac) at VAULT_ADDR/VAULT_TOKEN, SECRETS_VAULT_PATH
  - aws   : AWS Secrets Manager (boto3), one JSON secret at SECRETS_AWS_ID

All providers fall back to environment variables if the backend is unavailable,
so no plaintext secrets need to live in prod config while dev keeps working.
"""

import json
import logging
import os
from functools import lru_cache

logger = logging.getLogger(__name__)

PROVIDER = os.environ.get("SECRETS_PROVIDER", "env").lower()


@lru_cache(maxsize=1)
def _vault_secrets() -> dict:
    try:
        import hvac

        client = hvac.Client(url=os.environ["VAULT_ADDR"], token=os.environ["VAULT_TOKEN"])
        path = os.environ.get("SECRETS_VAULT_PATH", "speedflow")
        resp = client.secrets.kv.v2.read_secret_version(path=path)
        return resp["data"]["data"]
    except Exception as exc:
        logger.warning("Vault unavailable (%s); falling back to env", exc)
        return {}


@lru_cache(maxsize=1)
def _aws_secrets() -> dict:
    try:
        import boto3

        client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "eu-west-1"))
        secret_id = os.environ["SECRETS_AWS_ID"]
        resp = client.get_secret_value(SecretId=secret_id)
        return json.loads(resp["SecretString"])
    except Exception as exc:
        logger.warning("AWS Secrets Manager unavailable (%s); falling back to env", exc)
        return {}


def get_secret(name: str, default: str | None = None) -> str | None:
    """Resolve a secret by name via the configured provider, env as fallback."""
    if PROVIDER == "vault":
        val = _vault_secrets().get(name)
        if val is not None:
            return val
    elif PROVIDER == "aws":
        val = _aws_secrets().get(name)
        if val is not None:
            return val
    return os.environ.get(name, default)


def provider() -> str:
    return PROVIDER
