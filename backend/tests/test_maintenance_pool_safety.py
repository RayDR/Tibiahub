"""Regression coverage for maintenance middleware connection handling."""

from types import SimpleNamespace

import pytest
from starlette.responses import Response

import main as backend_main


class FakeQuery:
    def filter(self, *_args, **_kwargs):
        return self

    def order_by(self, *_args, **_kwargs):
        return self

    def first(self):
        return None


class FakeSession:
    def __init__(self):
        self.closed = False

    def query(self, *_args, **_kwargs):
        return FakeQuery()

    def rollback(self):
        pass

    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_maintenance_session_closes_before_endpoint(
    monkeypatch,
):
    session = FakeSession()

    monkeypatch.setattr(
        backend_main,
        "SessionLocal",
        lambda: session,
    )

    request = SimpleNamespace(
        url=SimpleNamespace(
            path="/api/v1/catalog/discovery",
        ),
        headers={},
    )

    async def call_next(_request):
        assert session.closed is True
        return Response(status_code=200)

    response = await backend_main.maintenance_enforcement(
        request,
        call_next,
    )

    assert response.status_code == 200
    assert session.closed is True
