# Weekly Report — Platform Team

Status for week 36, compiled Friday 17:00. Audience: engineering leadership.

## Highlights

Shipped the context-compression rewrite; agent sessions now survive 200k+
token histories without drift. Rolling out to 10% of traffic on Monday.

## Metrics

| Metric | This week | Last week | Delta |
|---|---|---|---|
| Sessions/day | 41 203 | 38 117 | +8.1% |
| Median latency | 2.4 s | 2.9 s | −17% |
| p99 latency | 11.8 s | 9.2 s | +28% ⚠ |
| Cost/session | $0.041 | $0.047 | −12.8% |

The p99 regression traces to the new evaluator shard — see Incidents.

## Incidents

**INC-2231** (Tue, 40 min): evaluator shard OOM under batch load; the
compressor emits denser checkpoints than the shard's memory budget assumed.

```python
# hotfix shipped Thursday
BATCH_SOFT_LIMIT = int(os.environ.get("EVAL_BATCH_SOFT_LIMIT", 256))
if len(pending) > BATCH_SOFT_LIMIT:
    flush(pending[:BATCH_SOFT_LIMIT])
    pending = pending[BATCH_SOFT_LIMIT:]
```

**INC-2233** (Wed, 6 min): DNS blip, failover worked, no action.

## Next week

1. Evaluator shard memory budget: +2 GB and a load test with dense checkpoints
2. Compression rewrite to 50% of traffic
3. Draft the p99 alert runbook (owner: N.)
