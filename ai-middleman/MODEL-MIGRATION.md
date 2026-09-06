# Model migration and reliability review — 6 September 2026

## Replacements

| Use | Old configuration | New configuration |
|---|---|---|
| Groq text | `llama-3.1-8b-instant` | `openai/gpt-oss-20b` |
| Groq images | `meta-llama/llama-4-scout-17b-16e-instruct` | `qwen/qwen3.6-27b` |
| Featherless fallback | `NousResearch/Meta-Llama-3.1-8B-Instruct` | `meta-llama/Llama-3.1-8B-Instruct` |
| OpenRouter | Incorrectly reused its key on Featherless | Independent endpoint and key; `meta-llama/llama-3.1-8b-instruct` |
| Hugging Face | Llama 3.1 8B through `:nscale` | Retained; still excluded from ranking pending evaluation |
| Audio | `whisper-large-v3-turbo` | Retained |

Groq's [deprecation notice](https://console.groq.com/docs/deprecations) lists
the text shutdown on 16 August 2026 and Scout shutdown on 17 July 2026 for
free/developer tiers; committed-spend enterprise accounts are an exception.
The chosen text model appears in the [supported catalogue](https://console.groq.com/docs/models).
For images, use a genuine [vision-capable replacement](https://console.groq.com/docs/vision),
not the text-only GPT-OSS replacement listed alongside Scout in the retirement table.

The fallback IDs are documented by
[Featherless](https://featherless.ai/models/meta-llama/Llama-3.1-8B-Instruct),
[OpenRouter](https://openrouter.ai/meta-llama/llama-3.1-8b-instruct) and
[Hugging Face Nscale](https://huggingface.co/docs/inference-providers/en/providers/nscale).
Catalogue documentation does not prove that any particular key has access,
quota or credits. Qwen is a preview model; run the diagnostic before a demo.

## Implementation changes

- Known retired Groq environment values migrate with a logged warning; custom
  model overrides remain intact. The old Featherless alias also migrates.
- Blank model/URL entries use defaults; example keys are ignored. No configured
  keys means no HTTP attempt with `Bearer None`. HF-only selection works.
- OpenRouter credentials are no longer borrowed by Featherless. Each vendor uses
  its own environment variables. Only explicitly configured vendors are tried.
- Every text call site uses the shared model-aware payload builder. GPT-OSS uses
  low reasoning effort, hides reasoning and reserves at least 2,048 completion
  tokens for reasoning plus final text. Hiding reasoning does not disable it.
  Qwen vision uses no reasoning. Settings follow
  [Groq's reasoning API](https://console.groq.com/docs/reasoning); they are not
  sent to unrelated providers.
- Empty, malformed, reasoning-only and truncated completions enter retry/fallback
  paths rather than crashing or returning a blank draft. Raw reasoning is never
  substituted for final text. Groq structured calls request JSON-object mode.
- JSON top-level values must be objects; intent flags must be actual booleans;
  ranking confidences must be finite numbers in [0, 1]. Candidate identity still
  comes from the database shortlist, not invented model display fields.
- Media timeouts and unusable replies raise the existing user-visible media
  error type without echoing sensitive provider response bodies.
- Invalid/missing WhatsApp signatures now fail closed (403); an absent/example
  signing secret produces 503. The former debug bypass could accept forged
  owner messages. No new mechanism automatically approves drafts.
- CI runs all of `tests/`, not only the original matching test file.

## Verification performed

Installed the repository's pinned dependencies into an isolated environment.
**88 tests passed**, up from the original 16. New tests exercise the actual
intent, ranking, drafting, details and update call sites through mocked HTTP
retirement/rate-limit/timeout/empty/truncated responses, plus credential isolation,
payload contracts, media failures and webhook authentication. Critical Python
lint passes. Two dependency deprecation warnings remain in Starlette's test client.

No provider credentials or `.env` exist in this checkout: live inference was
**not** tested. The diagnostic correctly reports missing credentials. No contacts,
WhatsApp messages or customer data were sent. No database/migration run or frontend
browser verification was performed; this change targets backend reliability.
Existing eval scores are historical and must be rerun on the replacements.

## Rollout

1. Pull this change. In `ai-middleman/.env`, configure a real `GROQ_API_KEY` and
   `WHATSAPP_APP_SECRET`; optionally configure fallback keys. Never commit secrets.
   Use `.env.example` for current IDs. Restart the API to refresh service configs.
2. From `ai-middleman/`, run `python scripts/check_llm.py` for catalogue checks.
   Run `python scripts/check_llm.py --probe` to make small synthetic text calls
   (may consume credits). Neither command accesses contacts or sends WhatsApp.
   Vision/audio inference are not tested by the text probe.
3. Run `python -m pytest tests/ -q`, then the existing labeled eval runner against
   a working database/API. Separately test a consented sample image and voice note.
4. Rehearse approval on the real phone and measure latency, relevance and cost.
   The larger token budget and replacement providers are not assumed free.

## Still important before public production use

- Dashboard contact CRUD, pipeline events and friend-simulator routes have no
  application authentication. Keep the demo behind a trusted/private access layer;
  CORS is not authentication. Add an authenticated owner session before exposing
  these endpoints publicly. Webhook HMAC fixes only the webhook boundary.
- The ranking code retains weak candidates at 0.3 while the friend route selects
  strong candidates at 0.7; older prose says 0.5. Thresholds were not silently
  retuned during a model migration. Reconcile the documented policy with measured
  relevance before claiming new accuracy.
- Re-evaluate multilingual quality and provider-specific JSON reliability; the
  previous Llama measurements do not transfer automatically to GPT-OSS/Qwen.

No retraining, public deployment, purchased credits or contact-data changes were
performed by this review.
