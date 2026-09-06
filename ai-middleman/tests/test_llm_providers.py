"""Provider migrations and actual service fallback paths, without live API calls."""

import json
import os

import httpx
import pytest

from app.services import llm_provider as providers
from app.services.agent import LLMAgent
from app.services.draft_generator import DraftGenerator
from app.services.intent_classifier import IntentClassifier, IntentClassificationError
from app.services.update_extractor import extract_update_target
from app.services.groq_media import (
    describe_image,
    transcribe_audio,
    MediaTranscriptionError,
)
from app.services.llm_json import extract_json


@pytest.fixture(autouse=True)
def clean_provider_env(monkeypatch):
    for name in list(os.environ):
        if name.startswith(("GROQ_", "FEATHERLESS_", "OPENROUTER_", "HUGGINGFACE_")):
            monkeypatch.delenv(name)
    for service in ("AGENT", "DRAFT", "INTENT"):
        monkeypatch.setenv(f"{service}_MAX_ATTEMPTS", "1")


def transport(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kw: client(transport=httpx.MockTransport(handler), **kw),
    )


def reply(content, finish="stop"):
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": content}, "finish_reason": finish}]},
    )


def test_no_credentials_means_no_http_config():
    assert providers.get_chat_configs() == []
    with pytest.raises(ValueError, match="No LLM"):
        providers.get_chat_config()


@pytest.mark.parametrize("key", ["", "  ", "your_groq_api_key_here", "changeme"])
def test_example_credentials_are_not_real_keys(monkeypatch, key):
    monkeypatch.setenv("GROQ_API_KEY", key)
    assert providers.get_chat_configs() == []


@pytest.mark.parametrize(
    "old,new",
    [
        ("llama-3.1-8b-instant", "openai/gpt-oss-20b"),
        ("llama-3.3-70b-versatile", "openai/gpt-oss-120b"),
        ("qwen/qwen3-32b", "openai/gpt-oss-120b"),
        ("", "openai/gpt-oss-20b"),
        ("custom-model", "custom-model"),
    ],
)
def test_old_env_values_migrate_but_custom_model_is_preserved(monkeypatch, old, new):
    monkeypatch.setenv("GROQ_MODEL", old)
    assert providers.groq_model() == new


def test_scout_migrates_to_a_vision_model(monkeypatch):
    monkeypatch.setenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct")
    assert providers.groq_model(vision=True) == "qwen/qwen3.6-27b"


def test_keys_never_cross_provider_boundaries(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-secret")
    configs = providers.get_chat_configs()
    assert len(configs) == 1
    assert configs[0]["api_url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert configs[0]["name"] == "openrouter"
    monkeypatch.setenv("FEATHERLESS_API_KEY", "feather-secret")
    monkeypatch.setenv("FEATHERLESS_MODEL", "NousResearch/Meta-Llama-3.1-8B-Instruct")
    configs = providers.get_chat_configs()
    assert [c["api_key"] for c in configs] == ["feather-secret", "router-secret"]
    assert configs[0]["model"] == "meta-llama/Llama-3.1-8B-Instruct"


def test_hf_only_configuration_and_ranking_exclusion(monkeypatch):
    monkeypatch.setenv("HUGGINGFACE_API_KEY", "hf-secret")
    assert providers.get_chat_config()["name"] == "huggingface"
    assert providers.get_chat_configs(include_huggingface=False) == []


def test_reasoning_budget_and_vendor_specific_options():
    config = {"name": "groq", "model": providers.GROQ_CHAT_MODEL}
    payload = providers.chat_payload(
        config, [], max_tokens=200, temperature=0.1, json_object=True
    )
    assert payload["max_completion_tokens"] >= 2048
    assert "max_tokens" not in payload
    assert payload["reasoning_effort"] == "low"
    assert payload["include_reasoning"] is False
    assert payload["response_format"] == {"type": "json_object"}
    config["name"] = "featherless"
    payload = providers.chat_payload(config, [], max_tokens=200, temperature=0.1)
    assert payload == {
        "model": config["model"],
        "messages": [],
        "max_tokens": 200,
        "temperature": 0.1,
    }


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"choices": []},
        {"choices": None},
        {"choices": [{"message": {"content": None}}]},
    ],
)
def test_malformed_200_envelope_is_rejected(body):
    with pytest.raises(ValueError):
        providers.completion_text(httpx.Response(200, json=body))


@pytest.mark.parametrize(
    "content,finish",
    [
        ("", "stop"),
        (" ", "stop"),
        ("half an answer", "length"),
        ("<think>private</think>answer", "stop"),
    ],
)
def test_empty_truncated_and_thinking_text_is_rejected(content, finish):
    with pytest.raises(ValueError):
        providers.completion_text(reply(content, finish))


@pytest.mark.parametrize("content", ["[]", "null", "true", "12"])
def test_json_service_requires_an_object(content):
    with pytest.raises(ValueError):
        extract_json(content)


CANDIDATE = {"id": 1, "full_name": "Test Lawyer", "title": "Lawyer"}


async def run_service(service):
    if service == "agent":
        return await LLMAgent().evaluate_matches("lawyer", [CANDIDATE])
    if service == "intent":
        return await IntentClassifier().classify("know a lawyer?")
    if service == "update":
        return await extract_update_target("Test Lawyer moved to Example")
    if service == "details":
        return await DraftGenerator().generate_details_draft(
            [{**CANDIDATE, "details_str": "test@example.invalid"}]
        )
    return await DraftGenerator().generate_draft("lawyer", [{"name": "Test Lawyer"}])


@pytest.mark.asyncio
@pytest.mark.parametrize("service", ["agent", "intent", "draft", "details", "update"])
@pytest.mark.parametrize(
    "failure", ["retired", "rate_limit", "empty", "truncated", "timeout"]
)
async def test_real_call_sites_fall_back(monkeypatch, service, failure):
    monkeypatch.setenv("GROQ_API_KEY", "groq-test")
    monkeypatch.setenv("FEATHERLESS_API_KEY", "feather-test")
    calls = []
    success = {
        "agent": '{"matches": [], "match_quality": "none"}',
        "intent": '{"is_request": true, "is_update": false, "language": "English"}',
        "update": '{"contact_name": "Test Lawyer", "attribute": "company", "new_value": "Example"}',
        "draft": "Test draft.",
        "details": "Test details.",
    }[service]

    def handler(request):
        calls.append(request)
        if request.url.host == "api.groq.com":
            payload = json.loads(request.content)
            assert payload["include_reasoning"] is False
            assert payload["max_completion_tokens"] >= 2048
            if failure == "retired":
                return httpx.Response(404)
            if failure == "rate_limit":
                return httpx.Response(429)
            if failure == "timeout":
                raise httpx.ReadTimeout("test timeout", request=request)
            return reply(
                None if failure == "empty" else "unfinished",
                "stop" if failure == "empty" else "length",
            )
        assert request.url.host == "api.featherless.ai"
        assert request.headers["authorization"] == "Bearer feather-test"
        return reply(success)

    transport(monkeypatch, handler)
    result = await run_service(service)
    assert len(calls) >= 2
    assert calls[-1].url.host == "api.featherless.ai"
    if service in {"draft", "details"}:
        assert result == success
    elif service == "intent":
        assert result["is_request"] is True
    elif service == "update":
        assert result["new_value"] == "Example"
    else:
        assert result["match_quality"] == "none"


@pytest.mark.asyncio
async def test_string_false_is_not_treated_as_true(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    transport(
        monkeypatch,
        lambda request: reply('{"is_request": "false", "is_update": false}'),
    )
    with pytest.raises(IntentClassificationError):
        await IntentClassifier().classify("hello")


@pytest.mark.parametrize("confidence", [float("nan"), float("inf"), 2, -1, True, "0.8"])
def test_invalid_ranking_scores_do_not_reach_approval(confidence):
    with pytest.raises(ValueError):
        LLMAgent._reconcile_matches(
            {"matches": [{"contact_id": 1, "confidence": confidence}]}, [CANDIDATE]
        )


@pytest.mark.asyncio
async def test_vision_payload_uses_qwen_without_thinking(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test")

    def handler(request):
        payload = json.loads(request.content)
        assert payload["model"] == "qwen/qwen3.6-27b"
        assert payload["reasoning_effort"] == "none"
        assert payload["messages"][0]["content"][1]["image_url"]["url"].startswith(
            "data:image/jpeg;base64,"
        )
        return reply("A synthetic test image.")

    transport(monkeypatch, handler)
    assert (
        await describe_image(b"fake image for transport test")
        == "A synthetic test image."
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["audio", "vision"])
@pytest.mark.parametrize("failure", ["empty", "timeout", "http"])
async def test_media_failure_has_a_visible_typed_error(monkeypatch, operation, failure):
    monkeypatch.setenv("GROQ_API_KEY", "test")

    def handler(request):
        if failure == "timeout":
            raise httpx.ReadTimeout("timeout", request=request)
        if failure == "http":
            return httpx.Response(400, text="sensitive upstream body")
        return httpx.Response(200, text="") if operation == "audio" else reply(None)

    transport(monkeypatch, handler)
    with pytest.raises(MediaTranscriptionError) as exc:
        await (
            transcribe_audio(b"test")
            if operation == "audio"
            else describe_image(b"test")
        )
    assert "sensitive upstream body" not in str(exc.value)
