import asyncio
import pytest
from fraud.middleware import BodyLimitMiddleware


def test_chunked_oversize_is_rejected_before_application():
    async def run():
        called = False
        sent = []

        async def app(scope, receive, send):
            nonlocal called
            called = True

        chunks = iter(
            [
                {"type": "http.request", "body": b"x" * 40_000, "more_body": True},
                {"type": "http.request", "body": b"x" * 40_000, "more_body": False},
            ]
        )

        async def receive():
            return next(chunks)

        async def send(value):
            sent.append(value)

        await BodyLimitMiddleware(app)(
            {"type": "http", "headers": [(b"content-length", b"1")]}, receive, send
        )
        assert not called and sent[0]["status"] == 413

    asyncio.run(run())


def test_valid_body_is_replayed_once_without_corruption():
    async def run():
        seen = []

        async def app(scope, receive, send):
            seen.append(await receive())

        chunks = iter(
            [
                {"type": "http.request", "body": b'{"a":', "more_body": True},
                {"type": "http.request", "body": b"1}", "more_body": False},
            ]
        )

        async def receive():
            return next(chunks)

        async def send(value):
            raise AssertionError("Middleware must not send a response")

        await BodyLimitMiddleware(app)({"type": "http"}, receive, send)
        assert seen == [{"type": "http.request", "body": b'{"a":1}', "more_body": False}]

    asyncio.run(run())


def test_production_rejects_demo_key_before_creating_state(monkeypatch, tmp_path):
    import fraud.api as api

    monkeypatch.setenv("FRAUD_ENV", "production")
    monkeypatch.setattr(api, "API_KEY", "local-demo-change-me")
    with pytest.raises(ValueError, match="Production requires"):
        api.create_app(tmp_path / "must-not-exist", tmp_path / "models")
    assert not (tmp_path / "must-not-exist").exists()
