# AI Reliability & Evaluation Platform

## Project Specification (v1.0)

**Project type:** Portfolio-grade AI infrastructure / backend
engineering platform\
**Primary goal:** Evaluate multiple LLMs on the same workload, compare
quality and operational performance, detect regressions, and recommend a
model for each task.\
**Target users:** AI engineers, backend engineers, ML engineers, and
teams choosing or upgrading LLMs.\
**Suggested build window:** 7 days for a credible MVP, using AI coding
tools as an accelerator---not as a substitute for tests and review.

------------------------------------------------------------------------

## 1. Executive Summary

The AI Reliability & Evaluation Platform is a web application and
backend service for repeatable evaluation of large language models
(LLMs). A user creates a dataset of test cases, selects models,
configures an evaluation run, and starts a benchmark. The platform sends
the same test cases to each selected model through LiteLLM, records
outputs and operational metrics, scores outputs using deterministic
checks and optional model-based judging, and presents comparative
reports.

The platform should help answer:

-   Which model performs best for a specific task and dataset?
-   Which model is faster, more reliable, and cheaper?
-   Did a prompt, model, provider, or configuration change cause a
    quality regression?
-   Is a new model version safe to promote for a workload?
-   What evidence supports the recommendation?

The MVP should favor reproducibility, safe execution, and explainable
reports over an overly broad feature set.

## 2. Problem Statement

Teams often choose LLMs using a few manual prompts, vendor benchmarks,
or subjective impressions. These approaches are difficult to reproduce
and do not reliably capture the trade-offs between answer quality,
latency, cost, and provider errors. A model that performs well on one
task may fail on another; an apparently better model may also be much
slower or more expensive.

When prompts, models, or provider settings change, teams may not notice
regressions until users encounter them. Evaluation data and results are
frequently scattered across notebooks, spreadsheets, logs, and ad hoc
scripts.

### Problem to solve

Build a centralized, repeatable system that evaluates candidate models
on a versioned dataset, measures both quality and operational behavior,
compares runs against a baseline, and produces an evidence-based
recommendation.

### Non-goals for the first week

-   Training or fine-tuning foundation models.
-   Guaranteeing that automated judges provide objective truth.
-   Supporting every LLM provider and every evaluation methodology.
-   Building a full enterprise multi-tenant billing platform.
-   Automatically deploying models to production without human approval.
-   Storing unrestricted sensitive production prompts or secrets.

## 3. Proposed Solution

Build a React dashboard backed by a FastAPI service. PostgreSQL stores
users, datasets, dataset versions, evaluation runs, results, metric
summaries, and regression findings. Redis supports job coordination and
rate limiting; a worker executes evaluation jobs asynchronously. LiteLLM
provides a common interface to configured model providers.

### Core user journey

1.  Create a dataset and add test cases.
2.  Validate and version the dataset.
3.  Select two or more configured models and an evaluation profile.
4.  Launch an evaluation run.
5.  The API validates permissions, quotas, and configuration, then
    queues a job.
6.  A worker runs test cases against each selected model with bounded
    concurrency, timeouts, retries, and per-run budgets.
7.  Results and metrics are persisted as each case finishes.
8.  The scoring service computes task-specific quality scores and
    aggregates operational metrics.
9.  The regression detector compares the run with a selected baseline.
10. The dashboard presents model comparisons, failures, cost/latency
    trade-offs, and a recommendation with supporting evidence.

### Key product principles

-   **Reproducibility:** dataset version, prompt version, model
    identifier, model parameters, evaluator version, and timestamp are
    recorded.
-   **Comparable tests:** the same dataset cases and evaluation settings
    are used for each model in a comparison.
-   **Fail visibly:** provider errors and missing results are reported
    rather than silently discarded.
-   **Bounded execution:** concurrency, retries, token usage, duration,
    and spend are limited.
-   **Explainable recommendations:** no "best model" result without the
    metric weights, constraints, and supporting scores.
-   **Secure by default:** API keys remain server-side, sensitive values
    are redacted, and public demos use quotas and safe sample data.

## 4. Goals and Success Criteria

### MVP goals

-   Run a versioned dataset against at least two configured models
    through LiteLLM.
-   Store every case-level result, including failures.
-   Measure latency, token usage when available, estimated cost when
    calculable, quality score, and failure rate.
-   Compare a new run to a baseline.
-   Detect configured quality or reliability regressions.
-   Recommend a model according to a user-selected scoring policy.
-   Provide a usable dashboard and a reproducible demo dataset.
-   Run locally using Docker Compose and be deployable to AWS later.

### Acceptance criteria

1.  A user can create, view, and version a dataset.
2.  A user can start a run without keeping an HTTP request open until
    completion.
3.  The UI shows queued/running/completed/failed states.
4.  Every test case/model pair has a terminal status: success, provider
    error, timeout, or skipped.
5.  The system records elapsed time and available token/cost metadata.
6.  Deterministic evaluators work without a judge model.
7.  A baseline comparison produces a regression report.
8.  A failed provider call does not crash the entire run.
9.  Secrets are not returned to the browser or written into logs.
10. Tests cover the core run lifecycle, scoring, regression logic, and
    API validation.

## 5. Scope and Feature Requirements

### P0 --- required for MVP

-   Dataset CRUD and JSON/CSV import.
-   Dataset versioning using immutable snapshots.
-   Test-case schema and validation.
-   Model registry/configuration using server-side environment
    variables.
-   Asynchronous evaluation jobs.
-   LiteLLM-based provider calls.
-   Per-case output, status, duration, usage, and error recording.
-   Deterministic evaluators: exact match, contains, regex, JSON schema
    validity, and reference-answer similarity only if a suitable
    local/remote embedding option is configured.
-   Run summary: quality, latency, token usage, estimated cost, failure
    rate.
-   Baseline comparison and configurable regression thresholds.
-   Model ranking under a transparent weighted scoring policy.
-   Dashboard for datasets, runs, model comparison, and case-level
    inspection.
-   Rate limits, execution limits, safe logging, and demo mode.

### P1 --- after MVP

-   LLM-as-a-judge evaluation with a separately configured judge model.
-   Pairwise blind comparisons.
-   Confidence intervals or bootstrap estimates for quality metrics.
-   Scheduled evaluations and GitHub Actions integration.
-   Prompt template versioning.
-   OpenTelemetry tracing and metrics export.
-   Login and team workspaces.
-   CSV/PDF report export.
-   AWS deployment with managed PostgreSQL and secret storage.

### P2 --- future enhancements

-   Human review queues and adjudication.
-   Statistical significance tests for selected metrics.
-   Drift monitoring from user feedback.
-   Canary evaluation before model promotion.
-   Webhook notifications.
-   Multi-region execution and advanced tenant isolation.
-   Evaluation plugins and custom scorer SDK.

## 6. Functional Requirements

  -----------------------------------------------------------------------
  ID                      Requirement             Priority
  ----------------------- ----------------------- -----------------------
  FR-01                   Create, edit, validate, P0
                          import, and view        
                          datasets                

  FR-02                   Preserve immutable      P0
                          dataset versions used   
                          by runs                 

  FR-03                   Configure model aliases P0
                          and allowed provider    
                          models                  

  FR-04                   Start, cancel where     P0
                          safe, and inspect       
                          asynchronous runs       

  FR-05                   Execute test cases      P0
                          across selected models  
                          via LiteLLM             

  FR-06                   Capture output, status, P0
                          latency, usage, cost    
                          estimate, and errors    

  FR-07                   Compute deterministic   P0
                          quality metrics         

  FR-08                   Aggregate results by    P0
                          model and dataset       

  FR-09                   Compare a run to a      P0
                          baseline and flag       
                          regressions             

  FR-10                   Rank models under       P0
                          configurable            
                          constraints and weights 

  FR-11                   Display case-level      P0
                          outputs and failure     
                          details                 

  FR-12                   Enforce quotas,         P0
                          concurrency caps,       
                          timeouts, and retries   

  FR-13                   Redact secrets and      P0
                          avoid exposing provider 
                          credentials             

  FR-14                   Export a                P1
                          machine-readable run    
                          report                  

  FR-15                   Schedule recurring      P1
                          evaluations             
  -----------------------------------------------------------------------

## 7. Non-Functional Requirements

-   **Reliability:** a single case failure must not terminate the whole
    run.
-   **Performance:** API endpoints should return quickly; long-running
    work belongs in workers.
-   **Scalability:** workers can be scaled horizontally; avoid assuming
    in-memory state is shared.
-   **Consistency:** run metadata and results must have explicit states
    and durable storage.
-   **Security:** validate input, restrict model names, keep secrets
    server-side, and rate-limit public endpoints.
-   **Observability:** structured logs with request/run/case IDs; health
    and readiness endpoints.
-   **Maintainability:** typed schemas, service boundaries, migrations,
    tests, linting, and clear error codes.
-   **Cost control:** configurable maximum cases, models, tokens,
    retries, concurrency, and spend.
-   **Reproducibility:** persist evaluator configuration and versioned
    dataset snapshots.
-   **Privacy:** do not use private user data in the public demo;
    configure retention and redaction.

## 8. System Architecture

### 8.1 High-Level Design (HLD)

``` mermaid
flowchart TB
    U[User / Evaluator] --> FE[React Web Dashboard]
    FE -->|HTTPS / JSON| API[FastAPI API]
    API --> AUTH[Authentication, Validation, Quotas]
    API --> DB[(PostgreSQL)]
    API --> Q[(Redis Queue / Coordination)]
    Q --> W[Evaluation Worker]
    W --> ORCH[Evaluation Orchestrator]
    ORCH --> L[LiteLLM]
    L --> P1[LLM Provider A]
    L --> P2[LLM Provider B]
    L --> P3[LLM Provider C]
    ORCH --> EV[Scoring and Evaluator Service]
    EV --> DB
    W --> DB
    API --> REP[Comparison / Regression / Recommendation Service]
    REP --> DB
    FE -->|Poll run status / fetch results| API
    API --> OBS[Structured Logs / Metrics]
    W --> OBS
```

**Architecture notes**

-   React is a presentation layer; it never receives provider API keys.
-   FastAPI handles validation and job creation, not long-running model
    calls.
-   Redis is a queue/coordination layer, not the system of record.
-   PostgreSQL is the durable source of truth.
-   Workers call LiteLLM through a controlled adapter.
-   The evaluation service separates raw outputs from scoring logic.
-   For a one-week MVP, use a single API service and one worker process;
    preserve boundaries so they can scale separately.

### 8.2 Deployment HLD

``` mermaid
flowchart TB
    Browser[Browser] --> CDN[Static Frontend Hosting]
    Browser -->|HTTPS| LB[HTTPS Endpoint / Load Balancer]
    CDN --> FE[React Static Assets]
    LB --> API[FastAPI Container]
    API --> RDS[(Managed PostgreSQL)]
    API --> REDIS[(Managed Redis or Queue)]
    REDIS --> WORKER[Worker Container]
    WORKER --> LITELLM[LiteLLM Adapter]
    LITELLM --> PROVIDERS[External Model APIs]
    API --> SECRETS[Secret Manager]
    WORKER --> SECRETS
    API --> LOGS[Central Logs and Metrics]
    WORKER --> LOGS
```

For local development, Docker Compose can run the frontend, API, worker,
PostgreSQL, and Redis. For an AWS deployment, candidate services are
ECS/Fargate, RDS PostgreSQL, ElastiCache for Redis, Secrets Manager,
CloudWatch, and S3 for larger report artifacts. This is a target
architecture, not a requirement to provision every AWS service in week
one.

## 9. Low-Level Design (LLD)

### 9.1 Backend component diagram

``` mermaid
flowchart LR
    ROUTER[API Routers] --> SCHEMA[Pydantic Schemas]
    ROUTER --> SERVICE[Application Services]
    SERVICE --> REPO[Repositories]
    REPO --> DB[(PostgreSQL)]
    SERVICE --> QUEUE[Queue Adapter]
    QUEUE --> WORKER[Evaluation Worker]
    WORKER --> RUNNER[Run Orchestrator]
    RUNNER --> ADAPTER[LLM Adapter]
    ADAPTER --> LITELLM[LiteLLM]
    RUNNER --> EVAL[Evaluator Registry]
    EVAL --> AGG[Metric Aggregator]
    AGG --> REG[Regression Detector]
    REG --> RANK[Recommendation Engine]
    AGG --> REPO
    REG --> REPO
    RANK --> REPO
```

### 9.2 Suggested source tree

``` text
ai-reliability-platform/
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── features/
│   │   │   ├── datasets/
│   │   │   ├── runs/
│   │   │   ├── comparisons/
│   │   │   └── recommendations/
│   │   ├── pages/
│   │   └── types/
│   ├── package.json
│   └── Dockerfile
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   └── dependencies.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── logging.py
│   │   │   └── security.py
│   │   ├── schemas/
│   │   ├── models/
│   │   ├── repositories/
│   │   ├── services/
│   │   │   ├── dataset_service.py
│   │   │   ├── run_service.py
│   │   │   ├── scoring_service.py
│   │   │   ├── regression_service.py
│   │   │   └── recommendation_service.py
│   │   ├── evaluation/
│   │   │   ├── orchestrator.py
│   │   │   ├── llm_adapter.py
│   │   │   ├── evaluators/
│   │   │   └── metrics.py
│   │   ├── worker/
│   │   └── db/
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── Dockerfile
├── datasets/
│   └── demo_dataset.json
├── infra/
│   ├── docker-compose.yml
│   └── aws/                  # Optional later
├── docs/
│   ├── architecture.md
│   └── api.md
├── .env.example
├── .gitignore
└── README.md
```

### 9.3 Component responsibilities

  -----------------------------------------------------------------------
  Component                           Responsibility
  ----------------------------------- -----------------------------------
  API routers                         HTTP contract, status codes,
                                      request/response mapping

  Pydantic schemas                    Input validation and typed API
                                      contracts

  Dataset service                     Import, validate, version, and
                                      retrieve test cases

  Run service                         Create run, enforce limits, enqueue
                                      work, expose status

  Queue adapter                       Abstract enqueueing and job state
                                      coordination

  Evaluation worker                   Claim jobs, execute work, persist
                                      progress, handle retries

  Run orchestrator                    Iterate over cases and models with
                                      bounded concurrency

  LLM adapter                         Call LiteLLM, normalize responses
                                      and provider errors

  Evaluator registry                  Execute configured deterministic
                                      and optional judge evaluators

  Metric aggregator                   Compute aggregate quality and
                                      operational metrics

  Regression detector                 Compare current run against a
                                      compatible baseline

  Recommendation engine               Rank eligible models under explicit
                                      constraints

  Repository layer                    Encapsulate database queries and
                                      transactions

  Frontend API client                 Typed requests, loading states, and
                                      error handling

  Dashboard                           Visualize run status, comparisons,
                                      cases, and reports
  -----------------------------------------------------------------------

### 9.4 Component-wise workflow diagram

``` mermaid
flowchart TD
    A[User uploads dataset] --> B[Dataset API validates schema]
    B -->|Invalid| C[Return validation errors]
    B -->|Valid| D[Save immutable dataset version]
    D --> E[User selects models and evaluation profile]
    E --> F[Run API checks permissions and budgets]
    F -->|Rejected| G[Return quota/configuration error]
    F -->|Accepted| H[Create run record]
    H --> I[Enqueue run in Redis]
    I --> J[Worker claims run]
    J --> K[Load dataset snapshot and run config]
    K --> L[Schedule case/model jobs with concurrency cap]
    L --> M[Call model through LiteLLM]
    M --> N[Normalize output and usage metadata]
    N --> O[Run evaluators]
    O --> P[Persist case result and metrics]
    P --> Q{All case/model pairs terminal?}
    Q -->|No| L
    Q -->|Yes| R[Aggregate metrics]
    R --> S[Compare baseline and detect regressions]
    S --> T[Rank eligible models]
    T --> U[Mark run complete and persist report]
    U --> V[Dashboard displays report]
```

### 9.5 Individual model-call workflow

``` mermaid
sequenceDiagram
    participant Worker
    participant Orchestrator
    participant Adapter as LiteLLM Adapter
    participant Provider as Model Provider
    participant Evaluator
    participant DB as PostgreSQL

    Worker->>Orchestrator: Execute run
    Orchestrator->>DB: Load cases and model configuration
    loop Each case/model pair
        Orchestrator->>Adapter: Generate request
        Adapter->>Provider: Request with timeout
        alt Successful response
            Provider-->>Adapter: Output and usage metadata
            Adapter-->>Orchestrator: Normalized success
            Orchestrator->>Evaluator: Score output
            Evaluator-->>Orchestrator: Metric values
            Orchestrator->>DB: Persist result
        else Timeout or provider error
            Provider-->>Adapter: Error / timeout
            Adapter-->>Orchestrator: Normalized failure
            Orchestrator->>DB: Persist failure and attempt metadata
        end
    end
    Orchestrator->>DB: Persist run summary and terminal state
```

### 9.6 Dataset authoring workflow

``` mermaid
flowchart LR
    A[JSON/CSV or UI form] --> B[Parse]
    B --> C[Validate required fields and limits]
    C -->|Errors| D[Show row-level errors]
    C -->|Valid| E[Normalize test cases]
    E --> F[Create immutable version]
    F --> G[Show sample and case count]
    G --> H[Available for evaluation runs]
```

## 10. Data Model

Use PostgreSQL with UUID primary keys, UTC timestamps, foreign keys,
indexes, and Alembic migrations. The schema below is a starting point;
keep raw outputs and secrets separate.

### 10.1 Entities

**Dataset** - `id` UUID primary key - `name` text - `description` text
nullable - `created_at` timestamp - `owner_id` nullable for local/demo
mode; required if authentication is added

**DatasetVersion** - `id` UUID primary key - `dataset_id` UUID foreign
key - `version_number` integer - `schema_version` text - `content_hash`
text - `created_at` timestamp - Unique constraint:
`(dataset_id, version_number)`

**TestCase** - `id` UUID primary key - `dataset_version_id` UUID foreign
key - `case_key` text - `input` JSONB - `expected_output` JSONB
nullable - `evaluation_config` JSONB - `tags` JSONB or a normalized tag
table - `created_at` timestamp - Unique constraint:
`(dataset_version_id, case_key)`

**ModelConfig** - `id` UUID primary key - `alias` text unique,
e.g. `fast-model` - `litellm_model` text - `provider` text - `enabled`
boolean - `config_json` JSONB for safe non-secret settings only -
Provider credentials are referenced by environment/secret name, never
stored as raw values.

**EvaluationRun** - `id` UUID primary key - `dataset_version_id` UUID
foreign key - `status` text: `queued`, `running`, `completed`,
`completed_with_errors`, `failed`, `cancelled` - `baseline_run_id` UUID
nullable - `config_snapshot` JSONB - `started_at`, `completed_at`
timestamps nullable - `created_at` timestamp - `requested_by` nullable -
`error_summary` text nullable

**CaseResult** - `id` UUID primary key - `run_id` UUID foreign key -
`test_case_id` UUID foreign key - `model_alias` text - `status` text:
`success`, `provider_error`, `timeout`, `invalid_output`, `skipped` -
`output` JSONB or text, subject to retention and privacy policy -
`latency_ms` integer nullable - `input_tokens`, `output_tokens` integer
nullable - `estimated_cost_usd` numeric nullable - `error_code` text
nullable - `error_message_redacted` text nullable - `attempt_count`
integer - `created_at` timestamp - Unique constraint:
`(run_id, test_case_id, model_alias)`

**CaseMetric** - `id` UUID primary key - `case_result_id` UUID foreign
key - `metric_name` text - `metric_value` numeric nullable -
`metric_details` JSONB nullable - Unique constraint:
`(case_result_id, metric_name)`

**RunSummary** - `id` UUID primary key - `run_id` UUID foreign key
unique - `model_alias` text - `quality_score` numeric nullable -
`success_rate` numeric - `failure_rate` numeric - `latency_p50_ms`,
`latency_p95_ms` numeric nullable - `total_input_tokens`,
`total_output_tokens` bigint nullable - `estimated_cost_usd` numeric
nullable - `summary_json` JSONB

**RegressionFinding** - `id` UUID primary key - `run_id` UUID foreign
key - `model_alias` text - `metric_name` text - `baseline_value`,
`current_value`, `delta` numeric nullable - `severity` text: `info`,
`warning`, `critical` - `explanation` text - `created_at` timestamp

### 10.2 Important indexes

-   `EvaluationRun(status, created_at)`
-   `EvaluationRun(dataset_version_id, created_at)`
-   `CaseResult(run_id, model_alias)`
-   `CaseResult(test_case_id, model_alias)`
-   `CaseMetric(metric_name)`
-   `RegressionFinding(run_id, severity)`

### 10.3 Dataset JSON example

``` json
{
  "name": "support-ticket-classification",
  "schema_version": "1.0",
  "cases": [
    {
      "case_key": "billing-001",
      "input": {
        "messages": [
          {
            "role": "user",
            "content": "I was charged twice for my subscription."
          }
        ]
      },
      "expected_output": {
        "category": "billing",
        "priority": "medium"
      },
      "evaluation_config": {
        "type": "json_schema",
        "schema": {
          "type": "object",
          "required": ["category", "priority"],
          "properties": {
            "category": {"type": "string"},
            "priority": {"type": "string"}
          }
        }
      },
      "tags": ["classification", "billing"]
    }
  ]
}
```

## 11. Evaluation and Metrics Design

### 11.1 Metrics

  -----------------------------------------------------------------------
  Metric                  Definition              Notes
  ----------------------- ----------------------- -----------------------
  Quality score           Mean of applicable      Report metric and
                          normalized case scores  denominator

  Exact match rate        Exact output matches /  Suitable only for
                          eligible cases          strict-output tasks

  Schema validity         Valid structured        Validate JSON
                          outputs / eligible      independently
                          cases                   

  Task accuracy           Correct predictions /   Requires trustworthy
                          labeled cases           labels

  Judge score             Aggregate rubric score  Subject to judge bias
                          from a judge model      and variance

  Latency p50/p95         Percentiles of          State which population
                          successful and/or all   is used
                          measured attempts       

  Failure rate            Failed terminal         Include timeouts and
                          case/model pairs /      provider errors
                          scheduled pairs         

  Token usage             Sum of                  May be missing for some
                          provider-reported       providers
                          input/output tokens     

  Estimated cost          Sum of known per-model  Label estimates; prices
                          token rates             can change

  Throughput              Completed case/model    Include workload and
                          pairs per second        concurrency
  -----------------------------------------------------------------------

Do not combine unrelated metrics into one score without documenting
normalization and weights. Do not treat missing token usage or cost as
zero.

### 11.2 Evaluator types

**Deterministic evaluators (MVP):** - Exact match after explicitly
configured normalization. - Contains/keyword checks. - Regex match. -
JSON parse and JSON Schema validation. - Classification accuracy when a
trusted label exists.

**Optional evaluators:** - Semantic similarity with a configured
embedding model. - LLM-as-a-judge with a versioned rubric, calibrated
examples, and a recorded judge model. - Pairwise preference
evaluation. - Human review.

For LLM-as-a-judge, record judge model, rubric version, judge prompt
hash, and raw score rationale where safe. Use repeated samples or human
spot checks for important decisions. The judge is another model and can
be wrong.

### 11.3 Cost and usage handling

-   Prefer provider-reported usage and LiteLLM cost metadata where
    available.
-   If estimating cost from a maintained price table, store the
    price-table version and timestamp.
-   If a price is unknown, set cost to `null` and show "unavailable"; do
    not fabricate a zero cost.
-   Make the distinction between provider bill, estimated cost, and
    actual invoiced cost clear.
-   Add per-run maximum case count, token cap where supported,
    wall-clock timeout, concurrency limit, and budget threshold.

## 12. Regression Detection

A regression is a configured, meaningful degradation compared with a
compatible baseline. Compare runs only when their dataset version,
evaluation configuration, and metric definition are compatible---or
clearly label differences.

### Example policy

-   Quality score falls by more than 3 percentage points: warning.
-   Failure rate rises by more than 2 percentage points: warning.
-   p95 latency rises by more than 25%: warning.
-   Estimated cost per eligible case rises by more than 20%:
    informational or warning depending on budget.
-   A critical task metric falls below an absolute minimum: critical.

These are initial configurable defaults, not universal thresholds. Tune
them to the task and dataset size. For small datasets, show sample
counts and avoid overconfident claims.

### Regression workflow

1.  Load current and baseline summaries.
2.  Verify compatible dataset and metric configuration.
3.  Compute absolute and relative deltas.
4.  Apply per-metric thresholds and minimum sample requirements.
5.  Persist a finding with baseline/current values and explanation.
6.  Display severity and supporting cases in the UI.
7.  Require human review before treating a result as a production
    promotion decision.

## 13. Model Recommendation Logic

The recommendation engine should rank models only among models that pass
required constraints. Example constraints:

-   Minimum quality score.
-   Maximum failure rate.
-   Maximum p95 latency.
-   Maximum estimated cost per case.
-   Minimum sample count.

For eligible models, use a configurable normalized score, for example:

`overall_score = 0.60 * quality_score + 0.25 * latency_score + 0.15 * cost_score`

All component scores must be normalized to a documented 0--1 scale;
higher must consistently mean better. If a metric is missing, either
exclude that component and renormalize transparently or mark the model
ineligible. Never silently assume missing cost or latency is zero.

The report should show: - Selected workload and dataset version. -
Constraints and scoring weights. - Per-model metric table. -
Eligibility/pass-fail reasons. - Sample count and missing metrics. -
Recommended model and a short evidence-based explanation. - A note that
the recommendation applies to this workload and test dataset only.

## 14. API Design

Use versioned REST endpoints under `/api/v1`. Exact response schemas
should be captured in OpenAPI.

  ----------------------------------------------------------------------------------
  Method                  Endpoint                           Purpose
  ----------------------- ---------------------------------- -----------------------
  GET                     `/health`                          Liveness check

  GET                     `/ready`                           Readiness check for
                                                             DB/queue

  POST                    `/api/v1/datasets`                 Create dataset

  GET                     `/api/v1/datasets`                 List datasets

  GET                     `/api/v1/datasets/{id}`            Dataset detail

  POST                    `/api/v1/datasets/{id}/versions`   Create immutable
                                                             dataset version

  GET                     `/api/v1/datasets/{id}/versions`   List versions

  POST                    `/api/v1/runs`                     Validate and queue
                                                             evaluation run

  GET                     `/api/v1/runs`                     List runs

  GET                     `/api/v1/runs/{id}`                Run status and summary

  POST                    `/api/v1/runs/{id}/cancel`         Request safe
                                                             cancellation

  GET                     `/api/v1/runs/{id}/results`        Paginated case-level
                                                             results

  GET                     `/api/v1/runs/{id}/comparison`     Model comparison

  GET                     `/api/v1/runs/{id}/regressions`    Regression findings

  GET                     `/api/v1/runs/{id}/report`         Machine-readable report

  GET                     `/api/v1/models`                   List allowed model
                                                             aliases

  GET                     `/api/v1/evaluation-profiles`      List supported
                                                             evaluator profiles
  ----------------------------------------------------------------------------------

### Example create-run request

``` json
{
  "dataset_version_id": "UUID",
  "model_aliases": ["model-a", "model-b"],
  "baseline_run_id": "UUID",
  "evaluation_profile": "classification-v1",
  "max_concurrency": 3,
  "max_cases": 100
}
```

The server must enforce configured hard limits regardless of values sent
by the client.

### API behavior

-   Return `202 Accepted` when a run is successfully queued.
-   Return `400` for malformed input, `401/403` for
    authentication/authorization errors, `404` for missing resources,
    `409` for incompatible state or duplicate conflicts, and `429` for
    rate/quota limits.
-   Use a stable error envelope containing `code`, `message`, and
    optional `details`.
-   Add pagination to list/result endpoints.
-   Use idempotency keys for run creation if retrying a client request
    could otherwise create duplicate runs.
-   Do not return stack traces, credentials, raw provider headers, or
    internal infrastructure details.

## 15. Run State Machine and Workflow

``` mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running
    queued --> cancelled
    running --> completed
    running --> completed_with_errors
    running --> failed
    running --> cancelled
    completed --> [*]
    completed_with_errors --> [*]
    failed --> [*]
    cancelled --> [*]
```

Rules: - State changes must be validated and persisted. - A worker must
safely recover or mark a job if a worker crashes. - Retries must be
bounded and limited to transient errors. - Do not retry invalid input,
authentication failures, or unsupported model configuration blindly. -
Cancellation is best-effort; already-running provider requests may not
be cancellable. - A run with some provider failures can still be
`completed_with_errors` if the configured policy permits.

## 16. Tech Stack

  -----------------------------------------------------------------------
  Layer                   Technology              Purpose
  ----------------------- ----------------------- -----------------------
  Frontend                React + TypeScript +    Interactive dashboard
                          Vite                    

  UI / charts             A maintained component  Tables, metrics, charts
                          library + Recharts or   
                          equivalent              

  Backend                 Python + FastAPI        Typed REST API

  LLM integration         LiteLLM                 Provider abstraction
                                                  and usage metadata

  Validation              Pydantic                Input and configuration
                                                  validation

  ORM / DB                SQLAlchemy + PostgreSQL Durable storage

  Migrations              Alembic                 Versioned schema
                                                  changes

  Queue / coordination    Redis plus RQ, Celery,  Asynchronous jobs
                          or Dramatiq             

  Testing                 pytest, HTTPX;          Backend and frontend
                          Vitest/React Testing    tests
                          Library                 

  Containers              Docker + Docker Compose Reproducible local
                                                  environment

  CI                      GitHub Actions          Lint, tests, build

  Deployment (later)      AWS ECS/Fargate, RDS,   Hosted production-style
                          ElastiCache, Secrets    deployment
                          Manager, CloudWatch     

  Optional telemetry      OpenTelemetry           Trace and metric export
  -----------------------------------------------------------------------

**Keep the queue implementation simple for week one.** Choose one worker
framework and use it consistently; do not introduce multiple queues or
orchestration frameworks without a clear need.

## 17. Security, Privacy, and Abuse Controls

-   Keep provider API keys in environment variables locally and a secret
    manager in hosted environments.
-   Never put secrets in React environment variables that are bundled
    into browser code.
-   Commit `.env.example`, never `.env`; configure `.gitignore` and
    secret scanning.
-   Use an explicit allowlist of model aliases rather than accepting
    arbitrary provider/model identifiers from anonymous users.
-   Set request-size limits, dataset case limits, maximum output tokens,
    request timeouts, concurrency caps, and per-user quotas.
-   Sanitize and redact exception messages before persistence and
    display.
-   Avoid logging full prompts/outputs by default; support redaction and
    retention settings.
-   Use synthetic, non-sensitive data in the public demo.
-   Protect against prompt injection in test content, especially if a
    judge model or tools are later added.
-   Treat model outputs and evaluation artifacts as untrusted data.
-   Restrict CORS to the deployed frontend origin.
-   Add authentication before enabling user-specific datasets or live
    provider calls.
-   Do not expose internal admin endpoints or arbitrary model-provider
    configuration.
-   Add a spend cap and a kill switch for live evaluations.
-   Rotate any key that is accidentally committed or exposed.

## 18. Testing Strategy

### Unit tests

-   Dataset validation and normalization.
-   Evaluator correctness.
-   Metric aggregation, percentiles, and missing values.
-   Cost estimation and unknown-price behavior.
-   Regression thresholds and recommendation ranking.
-   State-machine transition validation.
-   Secret and error-message redaction.

### Integration tests

-   API + test PostgreSQL.
-   Run creation and queue submission.
-   Worker success, timeout, retry, and provider error paths.
-   Persistence of partial results and terminal run state.
-   Baseline comparison for compatible and incompatible runs.

### End-to-end tests

-   Create dataset → launch run → wait for completion → view comparison
    → inspect regression.
-   Demo mode should use deterministic mock model responses so tests do
    not require paid API access.
-   A small, optional live smoke test can run only when credentials are
    explicitly configured.

### Reliability tests

-   Simulate rate limits, network errors, timeouts, malformed model
    output, missing usage metadata, worker restarts, and duplicate job
    delivery.
-   Confirm that retries are bounded and result rows are not duplicated.
-   Test concurrency and budget enforcement.

## 19. One-Week AI-Assisted Implementation Plan

Assumption: one developer, approximately 4--6 focused hours per day, AI
coding assistant available, and an intentionally constrained MVP. Build
a working end-to-end slice first. Keep deployment and optional
judge-model features out of the critical path.

### Day 1 --- Specification, scaffold, and vertical slice

**Deliverables** - Repository and source tree. - Docker Compose for API,
worker, PostgreSQL, and Redis. - FastAPI health endpoints and React
shell. - Database connection and first migration. - One demo dataset and
mock model adapter. - README with setup steps.

**AI-assisted tasks** - Ask AI to scaffold a typed FastAPI application
and React + TypeScript app. - Ask it to generate SQLAlchemy models and
Alembic migration from the approved schema. - Review all generated files
and run the app locally before adding features.

**Exit check:** a browser can reach the frontend and the API health
endpoint works.

### Day 2 --- Dataset management and validation

**Deliverables** - Dataset create/list/detail endpoints. - JSON import
and row-level validation errors. - Immutable dataset versioning and
content hash. - Dataset management UI and seeded sample data. - Unit
tests for malformed and valid datasets.

**AI-assisted tasks** - Generate Pydantic schemas, service methods,
repository tests, and UI forms. - Have AI propose edge cases; write or
verify tests before accepting implementation.

**Exit check:** a user can create a dataset, inspect it, and launch from
a stable version.

### Day 3 --- Asynchronous evaluation pipeline

**Deliverables** - Create-run endpoint returning `202 Accepted`. -
Redis-backed worker using one chosen queue framework. - Run state
machine and progress persistence. - Mock provider adapter with success,
timeout, and error scenarios. - Case/model result persistence.

**AI-assisted tasks** - Generate worker skeleton and tests for retry
boundaries. - Ask AI to review concurrency and idempotency risks. - Use
deterministic fake responses for development.

**Exit check:** an evaluation run completes asynchronously and partial
results survive individual failures.

### Day 4 --- LiteLLM integration and metrics

**Deliverables** - LiteLLM adapter for configured model aliases. -
Server-side provider credentials. - Timeouts, bounded retries,
concurrency and run limits. - Latency, usage, cost metadata, status, and
error capture. - Exact match, contains, regex, JSON validity/schema, and
classification evaluators.

**AI-assisted tasks** - Ask AI to implement the adapter against the
installed LiteLLM version and current documentation. - Require unit
tests with mocked LiteLLM responses. - Verify provider-specific
usage/cost fields; treat missing metadata as unknown.

**Exit check:** the same test cases run against two configured model
aliases, or against mocks when API keys are absent.

### Day 5 --- Comparison, regression, recommendation

**Deliverables** - Aggregated quality and reliability summaries. -
p50/p95 latency and token/cost totals where available. - Baseline
selection and compatibility checks. - Configurable regression
thresholds. - Explainable model ranking with hard constraints. - Unit
tests for metrics and regression logic.

**AI-assisted tasks** - Ask AI to suggest edge cases for small samples,
null metrics, and incompatible baselines. - Independently validate
formulas and test expected values.

**Exit check:** a run can be compared with a baseline and produce a
traceable report.

### Day 6 --- Dashboard, tests, and hardening

**Deliverables** - Dataset, run list, run detail, comparison, and
case-inspection pages. - Loading, empty, error, and partial-failure
states. - Backend integration tests and core frontend tests. -
Structured logs, request IDs, redaction, and rate limits. - Responsive
layout and a seeded demo mode.

**AI-assisted tasks** - Generate typed API client hooks and UI test
scaffolding. - Ask AI to review for security problems and missing
failure states. - Run lint, type checking, tests, and dependency checks.

**Exit check:** a new user can follow the main workflow without
developer intervention.

### Day 7 --- Deployment, documentation, and resume packaging

**Deliverables** - Docker images and production build. - CI workflow for
lint, tests, and build. - Public demo with sample data; live calls
disabled or strictly limited by default. - Deployment instructions,
architecture diagrams, API docs, screenshots, and a short demo video. -
README with limitations, cost controls, and a roadmap.

**AI-assisted tasks** - Ask AI to review the README for completeness and
generate a smoke-test checklist. - Use AI to review deployment
configuration, but manually verify secret handling and public
endpoints. - Capture benchmark results from repeatable runs; do not
invent performance claims.

**Exit check:** a recruiter can open the demo, explore a sample report,
and inspect the source code.

### If the week gets compressed

Prioritize in this order: 1. Mock-backed end-to-end run. 2. Dataset
versioning and persistent results. 3. LiteLLM adapter and operational
metrics. 4. Baseline regression logic. 5. Dashboard. 6. Deployment and
polished documentation. 7. Optional judge-model evaluation.

Do not sacrifice secret management, bounded spending, or tests merely to
add more features.

## 20. How to Use AI Coding Tools Effectively

Use AI for scaffolding, boilerplate, test generation, code review, and
documentation. Work in small tasks that can be verified.

### Recommended loop

1.  Give the assistant one component and its acceptance criteria.
2.  Ask it to list assumptions and propose file changes before editing.
3.  Generate a small implementation.
4.  Run formatting, lint, type checking, and tests.
5.  Inspect the diff, especially SQL queries, authentication, retries,
    and secret handling.
6.  Ask AI to critique the code for edge cases.
7.  Commit the verified change.
8.  Continue to the next component.

### Example implementation prompt

> Implement the dataset-versioning feature for this AI Reliability &
> Evaluation Platform. Follow the existing repository structure. Use
> FastAPI, Pydantic, SQLAlchemy, PostgreSQL, and Alembic. Create the
> required request/response schemas, service, repository, endpoint,
> migration, and pytest tests. Dataset versions must be immutable and
> include a deterministic content hash. Validate input size and row
> count. Do not put business logic in the route handler. Do not invent
> existing files or APIs---inspect the repository first. After
> implementation, run the relevant tests and report changed files,
> assumptions, and any failures. Do not claim tests passed unless you
> ran them.

### Example code-review prompt

> Review this change as a senior backend engineer. Look for race
> conditions, duplicate job execution, unbounded retries, missing
> database transactions, inaccurate metrics, provider-specific
> assumptions, secret leakage, prompt/output logging, and inadequate
> tests. Identify concrete failure scenarios and propose the smallest
> safe fixes. Do not rewrite unrelated files.

## 21. Deployment and Demo Strategy

### Local development

Use Docker Compose to run: - `frontend` - `api` - `worker` -
`postgres` - `redis`

Provide `.env.example` with placeholders only. Seed a demo dataset and a
mock provider so the application can be explored without provider
credentials.

### Public portfolio demo

Recommended first deployment: - React static frontend on a frontend
host. - FastAPI API and worker on a container host. - Managed
PostgreSQL. - Managed Redis only if the selected queue requires it. -
Secrets stored in the hosting platform's secret manager. - Sample
results visible to anonymous users. - Live model runs disabled by
default or gated by authentication and strict quotas.

### AWS production-style option

-   ECS/Fargate for API and worker containers.
-   RDS PostgreSQL for persistence.
-   ElastiCache for Redis if required.
-   Secrets Manager for provider credentials.
-   CloudWatch for logs, alarms, and metrics.
-   S3 for exported reports if needed.
-   IAM least-privilege roles and HTTPS ingress.

Check current provider pricing and free-tier rules before deployment.
Free tiers can sleep, have limited compute, or change; do not promise
continuous availability without verifying the plan.

## 22. Risks and Mitigations

  -----------------------------------------------------------------------
  Risk                                Mitigation
  ----------------------------------- -----------------------------------
  LLM output is nondeterministic      Record settings, repeat important
                                      tests, and report variance where
                                      appropriate

  Judge model is biased               Version rubrics, calibrate with
                                      examples, and use human spot checks

  Provider rate limits                Bounded concurrency, backoff for
                                      transient errors, and
                                      provider-aware limits

  Cost overruns                       Hard budgets, case/token caps,
                                      allowlisted models, and a kill
                                      switch

  Missing usage or price metadata     Preserve null values and label
                                      estimates clearly

  Dataset leakage or sensitive data   Synthetic public demo data,
                                      redaction, access control,
                                      retention policy

  Duplicate worker delivery           Idempotent result writes and unique
                                      database constraints

  Baseline mismatch                   Validate dataset/evaluator
                                      compatibility before comparing

  AI-generated code defects           Tests, code review, static
                                      analysis, and incremental changes

  Free-host sleep/cold starts         Document limitations or select a
                                      paid plan if needed
  -----------------------------------------------------------------------

## 23. Demo Scenario

Use a synthetic customer-support classification dataset with labels such
as `billing`, `technical`, and `account_access`.

1.  Run the dataset against two configured models.
2.  Show task accuracy and JSON/schema validity.
3.  Compare p50/p95 latency, failures, token usage, and estimated cost.
4.  Select the first run as a baseline.
5.  Simulate a prompt or model configuration change that reduces
    classification accuracy.
6.  Run the evaluation again and show a regression warning.
7.  Display why the recommended model wins under the chosen quality,
    latency, and cost constraints.

The demo should be repeatable. A mock mode can simulate the regression
without making paid provider calls. Clearly label simulated data and
results.

## 24. Portfolio Deliverables

The finished project should include:

-   Public Git repository with a clear README.
-   Live demo URL, if hosting is available.
-   Architecture and component workflow diagrams.
-   API documentation generated from OpenAPI.
-   Docker Compose setup.
-   Demo dataset and reproducible demo script.
-   Automated tests and CI status.
-   Screenshots or a short walkthrough video.
-   A benchmark report showing methodology, sample count, limitations,
    and measured results.
-   A security section describing secret handling, rate limits, and cost
    safeguards.
-   A roadmap distinguishing implemented features from planned features.

### Resume bullet template

**AI Reliability & Evaluation Platform \| Python, FastAPI, LiteLLM,
PostgreSQL, Redis, React, Docker**

-   Built a multi-model LLM evaluation platform that executes versioned
    test datasets and compares task quality, latency, token usage,
    estimated cost, and failure rates through LiteLLM.
-   Implemented asynchronous evaluation workers, bounded retries,
    persistent case-level results, baseline regression detection, and
    explainable model recommendations.
-   Delivered a containerized web dashboard with automated tests and CI;
    measured **\[actual result\]** across **\[actual workload/sample
    size\]**.

Replace bracketed values only after running and documenting real
benchmarks.

## 25. Definition of Done

The MVP is complete when:

-   [ ] The project starts locally using documented commands.
-   [ ] A seeded dataset can be viewed and versioned.
-   [ ] An evaluation run can be queued and processed asynchronously.
-   [ ] The same dataset can be evaluated against at least two model
    aliases (or deterministic mocks).
-   [ ] Case-level success and failure results persist.
-   [ ] Metrics are correctly computed and missing values are handled
    honestly.
-   [ ] Baseline comparison produces explainable regression findings.
-   [ ] Model recommendation logic is documented and tested.
-   [ ] Dashboard covers the complete primary user journey.
-   [ ] Secrets are server-side and not committed.
-   [ ] Public demo has strict resource and cost controls.
-   [ ] Core tests pass in CI.
-   [ ] README explains architecture, setup, limitations, and
    deployment.
-   [ ] All claimed benchmarks are reproducible and measured.

------------------------------------------------------------------------

## Final recommendation

Build a narrow but complete product first: **versioned datasets →
asynchronous runs → LiteLLM adapter → scoring → regression report →
dashboard**. Use deterministic demo responses for repeatable tests, then
enable a small number of live model calls with strict limits. This
delivers a credible engineering project in one week while leaving a
clear path to a more production-grade platform.
