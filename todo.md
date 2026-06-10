# TODO

## Deferred from conversational-retrieval plan

- [ ] **SSE streaming for answers + reasoning steps.**
  The plan returns a single JSON answer (`AgentResponse`). With FastAPI this is
  easy to upgrade later via `StreamingResponse` / EventSource — stream the Final
  Answer token-by-token, and optionally each ReAct Thought/Action/Observation
  step. Mirror the `:8081` PDF endpoint SSE format
  (`event: sources`, see `docs/PDF_ENDPOINT_SSE_FORMAT.md` once ported).
  Decide how streaming interacts with per-turn conversation persistence
  (persist after the stream completes).

See `PLAN_CONVERSATIONAL_RETRIEVAL.md` for the full plan.
