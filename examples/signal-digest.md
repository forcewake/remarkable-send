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

Per Bloomberg, DeepSeek is discussing a large order for Huawei AI chips to
equip a new data-center in Inner Mongolia. The stage of the talks and the
order size are not named in the excerpts — this is negotiations reporting,
not a signed deal, and single-source market stories stay capped below the
top score band for exactly that reason.

**Why it matters:** if the order lands, it is a domestic-capacity scaling
signal under export controls — training compute moving to sanctioned
silicon at scale changes capacity planning for everyone downstream of
Chinese model releases.

**Watch:** procurement volume, data-center power permits in Inner
Mongolia, and any Huawei statement. Talks collapse more often than they
convert.

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

The module registry of Coder was compromised: attacker-published
Terraform modules displaced community ones, meaning `terraform init`
against the registry could pull attacker code into build pipelines with
whatever credentials the plan runner holds. The exposure window is
published; anyone who pulled modules in it should treat registry content
as untrusted until pinned.

**Why it matters:** this is the second registry-style incident in one
digest — the llms.txt research above is the same shape from the agent
side. The pattern for the quarter is *trusted distribution points*, not
zero-days: registries, docs files, package mirrors.

**Action:** pin module versions by digest; rotate credentials available to
plan runners; audit what executed during the window.

Source: arstechnica.com

## Amazon Bedrock batch at 50% off, Agents GA pricing

**MATERIAL · score 61 · cloud**

AWS published a migration playbook alongside two Bedrock changes: batch
inference at a fifty percent discount and general-availability pricing for
Agents. The playbook itself is the more useful artifact — it walks through
request signing, model mapping and the guardrails config that most teams
skip on the first pass.

**Why it matters:** batch pricing is the difference between nightly eval
suites that run and nightly eval suites that get disabled when the bill
arrives. If you are running evaluation or enrichment workloads
request-by-request, this is the migration to make this quarter.

**Action:** move anything latency-tolerant to batch; re-check guardrail
policies before switching, GA pricing changed per-token assumptions.

Source: aws.amazon.com blogs

## GLM-5.3 stops returning 400s on Nous/OpenRouter

**MATERIAL · score 58 · serving**

After last week's incident, GLM-5.3 endpoints on Nous/OpenRouter no longer
return 400s under long-context bursts. The fix commit is small and telling:
the decision to refuse a tool call now lives entirely on the client, where
it belonged — the gateway had been rejecting requests it could not
semantically judge.

**Why it matters:** if you route agent traffic through OpenRouter with
fallbacks, silent gateway-side refusals masquerade as model failures and
poison your retry logic. Worth knowing the failure class is gone before
you remove workarounds.

**Action:** drop any 400-retry special-casing for this route; keep
client-side refusal handling.

Source: github.com/NousResearch/hermes-agent

## The Memory Trust Gap (preprint)

**WATCHLIST · score 54 · research**

A preprint argues that agents with persistent memory systematically
over-trust their own recall: facts injected into memory during one session
survive into later sessions even after the source is discredited, and
explicit corrections decay faster than the original contamination. The
mechanism the authors propose — provenance-weighted recall — is sensible;
the evidence is four benchmarks and no code release.

**Why it stays on the watchlist:** n=4 with no reproduction is a prompt
for your own testing, not a basis for architecture decisions. If you run
long-lived agent memory, replicate the persistence test on your own stack
this month; that is the cheap version of acting on it.

Source: arxiv.org preprint

---

*Methodology: 13 lanes, 208 queries, semantic review of every candidate
against primary sources; vendor claims labelled; anything a single source
can't carry stays on the watchlist.*
