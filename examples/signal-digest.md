# Signal Digest — Field Test 36

An agent-curated intelligence digest: 232 candidates reviewed, 8 kept.
Facts separated from interpretation; uncorroborated signals stay on the
watchlist instead of being promoted.

## llms.txt supply-chain: agents installed unowned packages

**EXECUTIVE · score 91 · supply-chain**

Researchers scanned 6 214 live domains and found 120 `llms.txt` /
`llms-full.txt` files pointing at unregistered package names and domains.
They registered a handful and hosted phone-home packages; within an hour a
Fortune 500 company executed one. The beacon recorded the parent process
chain: coding agents — Claude, Codex, Hermes — were doing the installing.

> "Agents treat vendor docs as ground truth and don't question them — and
> neither do the humans supervising them." — one of the researchers

**Why it matters:** think SolarWinds-style supply chain, but the injection
point is a file literally designed to be read by agents.

**Action:** pin exact package names from a private registry; audit any
`llms.txt` you publish for unregistered references.

Sources: schneier.com · arstechnica.com (research write-up)

## Claude Code switches default: Sonnet 5, 1M window

**EXECUTIVE · score 88 · tooling**

The official changelog moves the default model to Claude Sonnet 5 with a
native 1M-token context window, a one-shot fallback per turn, and model
names instead of gateway IDs in configs. Promotional pricing figures are
cut off in the excerpt; the fallback model is not named.

**Why it matters:** default switches change cost profiles overnight for
every team that doesn't pin versions.

**Action:** pin the model explicitly in CI configs; re-benchmark agent
spend this week.

Source: code.claude.com changelog

## DeepSeek in talks for large Huawei chip order

**EXECUTIVE · score 84 · market**

Per Bloomberg, DeepSeek is discussing a large order for Huawei AI chips
for a new data-center in Inner Mongolia. Stage and size are not named in
the excerpts; talks, not a deal.

**Why it matters:** domestic-capacity scaling signal amid export controls.

Source: bloomberg.com (via Bloomberg reporting)

## vLLM: Responses API stream aborts mid-tool-call

**MATERIAL · score 72 · serving**

A single repro reports SSE Responses API streams aborting mid-stream on
tool-heavy loads with Qwen3.8 + qwen3_coder + speculative decoding
("DFlash drafter enabled") — nameless
`ResponseFunctionToolCallItem` arrives without a terminal event.

**Watch:** one author, no maintainer response, no server version in the
report. Keep DFlash off Responses-API loads until confirmed.

Source: github.com/vllm-project/vllm issue #55284

## Coder module registry compromised, Terraform modules swapped

**MATERIAL · score 70 · supply-chain**

The module registry of Coder was compromised; attacker-published
Terraform modules replaced community ones. Rotated credentials advised
for anyone who pulled modules in the exposure window.

Source: arstechnica.com

## Amazon Bedrock batch at 50% off, Agents GA pricing

**MATERIAL · score 61 · cloud**

AWS published a migration playbook alongside Bedrock changes: batch
inference at 50% discount and general-availability pricing for Agents.

Source: aws.amazon.com blogs

## GLM-5.3 stops returning 400s on Nous/OpenRouter

**MATERIAL · score 58 · serving**

After last week's incident, GLM-5.3 endpoints on Nous/OpenRouter no
longer return 400s under long-context bursts; a fix commit landed in the
gateway ("the decision to refuse a tool call lives entirely on the
client").

Source: github.com/NousResearch/hermes-agent

## The Memory Trust Gap (preprint)

**WATCHLIST · score 54 · research**

A preprint argues agents with persistent memory systematically
over-trust their own recall: injected facts survive across sessions even
after the source is discredited. Preliminary, n=4 benchmarks, no code
release. Watch, don't act.

Source: arxiv.org preprint

---

*Methodology: 13 lanes, 208 queries, semantic review of every candidate
against primary sources; vendor claims labelled; anything a single source
can't carry stays on the watchlist.*
