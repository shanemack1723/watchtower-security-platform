import os
import secrets
from pathlib import Path

from dotenv import load_dotenv
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENVIRONMENT_FILE = PROJECT_ROOT / ".env"

load_dotenv(
    ENVIRONMENT_FILE,
    override=True,
)


agent_api_key_header = APIKeyHeader(
    name="X-Watchtower-API-Key",
    auto_error=False,
)


def require_agent_api_key(
    provided_api_key: str | None = Security(agent_api_key_header),
) -> str:
    expected_api_key = os.getenv("WATCHTOWER_AGENT_API_KEY")

    if not expected_api_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The agent API key is not configured.",
        )

    if (
        provided_api_key is None
        or not secrets.compare_digest(
            provided_api_key,
            expected_api_key,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid Watchtower agent API key is required.",
        )

    return provided_api_key