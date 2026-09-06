import httpx
import pytest

from scripts.check_llm import check_config


@pytest.mark.asyncio
async def test_missing_model_is_failure_not_false_green():
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={"data": []})
        )
    ) as client:
        issues = await check_config(
            client,
            {
                "name": "featherless",
                "api_key": "test",
                "api_url": "https://example.invalid/v1/chat/completions",
                "model": "missing",
            },
        )
    assert issues == ["configured model absent from catalogue: missing"]


@pytest.mark.asyncio
async def test_diagnostic_probes_only_synthetic_text():
    calls = []

    def handler(request):
        calls.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"data": [{"id": "test-model"}]})
        assert b"Return only this JSON object" in request.content
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"ok": true}'}, "finish_reason": "stop"}
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        issues = await check_config(
            client,
            {
                "name": "featherless",
                "api_key": "test",
                "api_url": "https://example.invalid/v1/chat/completions",
                "model": "test-model",
            },
            probe=True,
        )
    assert issues == []
    assert [r.method for r in calls] == ["GET", "POST"]
