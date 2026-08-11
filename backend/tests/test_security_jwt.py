from datetime import timedelta

import jwt

from app.core import security
from app.core.config import settings


def test_access_token_round_trips_with_pyjwt():
    token = security.create_access_token(
        "runtime-modernization",
        expires_delta=timedelta(minutes=5),
    )

    payload = jwt.decode(
        token,
        settings.secret_key,
        algorithms=[security.ALGORITHM],
    )

    assert payload["sub"] == "runtime-modernization"
    assert "exp" in payload
