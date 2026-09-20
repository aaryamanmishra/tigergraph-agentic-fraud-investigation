"""
Configuration Management for TigerGraph Agentic Fraud Investigation.
Supports environment variables and .env file loading without committing secrets.
"""

import os
import json
import logging
import urllib.request
import urllib.error
from typing import Optional, Dict

logger = logging.getLogger(__name__)


def _load_dotenv():
    """Lightweight zero-dependency .env loader."""
    candidates = [
        os.path.join(os.getcwd(), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.expanduser("~/.env")
    ]
    for env_path in candidates:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k not in os.environ:
                            os.environ[k] = v
            except Exception as e:
                logger.warning(f"Could not read .env file at {env_path}: {e}")
            break


_load_dotenv()


class Config:
    # Environment
    ENV: str = os.getenv("APP_ENV", "development")
    DATA_DIR: str = os.getenv("DATA_DIR", os.path.abspath("."))
    CASES_DIR: str = os.getenv("CASES_DIR", os.path.abspath("cases"))

    # TigerGraph Connection Settings
    TG_HOST: str = os.getenv("TG_HOST", "localhost")
    TG_REST_PORT: int = int(os.getenv("TG_REST_PORT", "14240" if "tgcloud" in os.getenv("TG_HOST", "") else "9000"))
    TG_GRAPH_NAME: str = os.getenv("TG_GRAPHNAME", os.getenv("TG_GRAPH_NAME", "FraudNet"))
    TG_GRAPHNAME: str = TG_GRAPH_NAME
    TG_PASSWORD: str = os.getenv("TG_PASSWORD", "")
    TG_SECRET: str = os.getenv("TG_SECRET", "")
    TG_TOKEN: str = os.getenv("TG_TOKEN", "")

    # Graph Execution Backend
    # Options: "auto" (tries TigerGraph, falls back to in_memory if unreachable),
    #          "tigergraph" (strictly requires TigerGraph, fails if offline),
    #          "in_memory" (uses local high-performance graph index)
    TG_BACKEND: str = os.getenv("TG_BACKEND", "auto")

    # TigerGraph MCP Server Settings
    MCP_SERVER_PORT: int = int(os.getenv("MCP_SERVER_PORT", "8080"))
    MCP_ENABLED: bool = os.getenv("MCP_ENABLED", "true").lower() == "true"

    _cached_token: Optional[str] = None

    @classmethod
    def get_rest_base_url(cls) -> str:
        protocol = "https" if ("tgcloud" in cls.TG_HOST or cls.TG_HOST.startswith("https://")) else "http"
        host = cls.TG_HOST.replace("http://", "").replace("https://", "").rstrip("/")
        # If port is standard 443 on cloud or host already includes port
        if ":" in host:
            return f"{protocol}://{host}"
        if "tgcloud" in cls.TG_HOST and cls.TG_REST_PORT in (443, 14240):
            return f"https://{host}"
        return f"{protocol}://{host}:{cls.TG_REST_PORT}"

    @classmethod
    def is_tigergraph_configured(cls) -> bool:
        """Returns True if meaningful TigerGraph host credentials or secrets are provided."""
        return bool(
            (cls.TG_HOST and cls.TG_HOST != "localhost")
            or cls.TG_SECRET
            or cls.TG_TOKEN
            or cls.TG_PASSWORD
        )

    @classmethod
    def get_auth_token(cls) -> Optional[str]:
        """
        Retrieves or generates a bearer token using TG_TOKEN or TG_SECRET.
        Never prints or exposes secret values.
        """
        if cls.TG_TOKEN:
            return cls.TG_TOKEN
        if cls._cached_token:
            return cls._cached_token
        if not cls.TG_SECRET:
            return None

        # Request token from TigerGraph using the secret
        base_url = cls.get_rest_base_url()
        endpoints = [
            f"{base_url}/gsql/v1/tokens",
            f"{base_url}/restpp/requesttoken",
            f"{base_url}/requesttoken",
            f"{base_url}:14240/gsql/v1/tokens",
            f"{base_url}:14240/restpp/requesttoken"
        ]

        payload = json.dumps({"secret": cls.TG_SECRET, "lifetime": 2592000}).encode("utf-8")
        for ep in endpoints:
            try:
                req = urllib.request.Request(
                    ep,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "TigerGraphAdapter/1.0"},
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=5.0) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if not data.get("error"):
                        # TG 4.x puts token at root, TG 3.x puts it in results.token
                        tok = data.get("token") or (data.get("results") or {}).get("token")
                        if tok:
                            cls._cached_token = tok
                            logger.info("Successfully acquired TigerGraph token via database secret.")
                            return cls._cached_token
            except Exception:
                continue

        # Also attempt GET requesttoken with query param if POST is disallowed
        try:
            get_url = f"{base_url}/requesttoken?secret={cls.TG_SECRET}"
            req = urllib.request.Request(get_url, headers={"User-Agent": "TigerGraphAdapter/1.0"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if not data.get("error") and "results" in data and "token" in data["results"]:
                    cls._cached_token = data["results"]["token"]
                    return cls._cached_token
        except Exception:
            pass

        return None

    @classmethod
    def get_status_dict(cls) -> Dict[str, Any]:
        """Returns safe configuration summary without exposing sensitive credentials."""
        return {
            "backend": cls.TG_BACKEND,
            "host": cls.TG_HOST,
            "rest_base_url": cls.get_rest_base_url(),
            "graph_name": cls.TG_GRAPH_NAME,
            "has_secret": bool(cls.TG_SECRET),
            "has_token": bool(cls.TG_TOKEN or cls._cached_token),
            "is_configured": cls.is_tigergraph_configured()
        }


config = Config()
