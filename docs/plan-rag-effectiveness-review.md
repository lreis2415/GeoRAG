# Plan: RAG effectiveness review

## TODO
- [DONE:1] 1. Inventory the active model, chunking, vector-store, and retrieval settings.
- [DONE:2] 2. Trace document ingestion and query execution for quality-loss points or inactive settings.
- [DONE:3] 3. Produce prioritised, testable recommendations without changing production behaviour.

## Acceptance Criteria
- The review identifies the concrete current settings and the code paths that use them.
- Recommendations state expected impact, risk, and a way to validate the improvement.
- No application code or runtime configuration is changed.
