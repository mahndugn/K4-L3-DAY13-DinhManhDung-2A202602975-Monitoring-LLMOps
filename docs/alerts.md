# Alert runbooks

These symptom based alerts notify `#llmops-alerts`. The owning on-call role
acknowledges the alert, records the incident window, and links the affected
correlation IDs and trace IDs in the incident note. Conditions are evaluated
over rolling windows and must remain true for the configured duration.

## <a id="alert-1"></a>1. Elevated request error rate

- **Severity / owner:** Critical / `api-on-call`
- **Condition:** Request error rate is above 2% for 5 minutes.
- **User impact:** Some chat requests fail or return an error instead of an answer.
- **First checks:**
  1. Confirm the alert window and compare `request_failed` with `request_received`.
  2. Group failures by `error_type` and `tool_name`; check whether retrieval failures dominate.
  3. Select an affected `correlation_id` and inspect its trace for the failed observation.
- **Mitigation:** If failures are retrieval related, disable the affected retrieval path or
  restore its last healthy configuration. If failures are broader, roll back the most
  recent application change and verify `/health` before clearing the alert.
- **Recovery check:** Error rate remains at or below 2% for 10 minutes and a fresh
  sample request succeeds.

## <a id="alert-2"></a>2. High request latency

- **Severity / owner:** Warning / `llmops-on-call`
- **Condition:** Request latency P95 is above 3000 ms for 10 minutes.
- **User impact:** A meaningful share of users wait longer than the 3-second SLO limit.
- **First checks:**
  1. Compare request P95, TTFT P95, and traffic over the same time range.
  2. Find slow `response_sent` records and collect their `correlation_id` values.
  3. Open matching traces and compare retrieval and generation observation durations.
- **Mitigation:** Reduce avoidable prompt/context size, lower request concurrency if the
  service is saturated, or disable a confirmed slow optional retrieval path. Roll back
  the latest change if the regression began with that release.
- **Recovery check:** Request P95 returns below 3000 ms for 10 minutes while quality
  and retrieval success remain within their guardrails.

## <a id="alert-3"></a>3. Low retrieval success

- **Severity / owner:** Warning / `retrieval-on-call`
- **Condition:** Retrieval success rate is below 90% for 5 minutes.
- **User impact:** Answers may lack relevant source material or fall back to generic responses.
- **First checks:**
  1. Compare successful and failed retrieval `tool_success` values in the alert window.
  2. Group failed records by `error_type` and check for repeated timeout patterns.
  3. Follow one failed request from its structured log `correlation_id` to the retrieval
     observation in Langfuse.
- **Mitigation:** Restore the last healthy retriever configuration or switch to the
  documented fallback while the retrieval dependency is unhealthy. Keep the fallback
  visible in logs and avoid reporting fallback answers as successful retrievals.
- **Recovery check:** Retrieval success is at least 90% for 10 minutes and sampled
  traces show the retrieval observation completing normally.
