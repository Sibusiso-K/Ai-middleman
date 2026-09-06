"""Check configured model catalogues; --probe adds synthetic text completions.

No contact database or WhatsApp calls. API keys and provider response bodies
are never printed. --probe can consume provider credits; it is opt-in.
"""

import argparse
import asyncio
from pathlib import Path
import sys

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.services.llm_provider import (
    get_chat_configs,
    chat_payload,
    completion_text,
    groq_model,
    setting,
)
from app.services.llm_json import extract_json


async def check_config(client, config: dict, *, probe: bool = False) -> list[str]:
    headers = {"Authorization": f"Bearer {config['api_key']}"}
    url = config["api_url"].removesuffix("/chat/completions") + "/models"
    issues = []
    try:
        response = await client.get(url, headers=headers, timeout=20)
        if response.status_code != 200:
            return [
                f"model catalogue HTTP {response.status_code}; check key/permissions/endpoint"
            ]
        ids = {item["id"] for item in response.json()["data"]}
        model = (
            config["model"].split(":", 1)[0]
            if config["name"] == "huggingface"
            else config["model"]
        )
        if model not in ids:
            issues.append(f"configured model absent from catalogue: {model}")
        if config["name"] == "groq":
            for media_model in (
                groq_model(vision=True),
                setting("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo"),
            ):
                if media_model not in ids:
                    issues.append(f"media model absent from catalogue: {media_model}")
        if probe and not issues:
            response = await client.post(
                config["api_url"],
                headers=headers,
                json=chat_payload(
                    config,
                    [
                        {
                            "role": "user",
                            "content": 'Return only this JSON object: {"ok": true}',
                        }
                    ],
                    max_tokens=128,
                    temperature=0,
                    json_object=True,
                ),
                timeout=30,
            )
            if response.status_code != 200:
                issues.append(f"synthetic completion HTTP {response.status_code}")
            elif extract_json(completion_text(response)).get("ok") is not True:
                issues.append("synthetic completion failed the JSON contract")
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        issues.append(
            f"check failed ({type(exc).__name__}); check connectivity/response contract"
        )
    return issues


async def run(*, probe: bool = False) -> int:
    configs = get_chat_configs()
    if not configs:
        print(
            "No usable provider keys configured. Set keys in ai-middleman/.env; do not commit them."
        )
        return 1
    failed = False
    async with httpx.AsyncClient() as client:
        for config in configs:
            issues = await check_config(client, config, probe=probe)
            failed |= bool(issues)
            print(
                f"{config['name']} / {config['model']}: "
                + (
                    "; ".join(issues)
                    if issues
                    else "catalogue OK"
                    + (
                        ", synthetic text probe OK"
                        if probe
                        else " (inference not tested)"
                    )
                )
            )
    print("Catalogue presence is not a quota, quality, or vision-inference guarantee.")
    return int(failed)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Send one small synthetic text completion per configured provider (may consume credits)",
    )
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(probe=args.probe)))
