# Usage Guide

This guide describes what the project does and how to run each implemented stage
from setup through evaluation and presentation.

## 1. What it does

Clinical Doc Assist can:

1. Search ClinicalTrials.gov for public clinical research records.
2. Screen candidates with a bounded DeepSeek research agent.
3. Build normalized evidence documents and deterministic chunks.
4. Embed chunks with a local TEI model and index them in Qdrant.
5. Retrieve ranked evidence with NCT IDs, sections, URLs, and content hashes.
6. Generate answers grounded only in retrieved evidence and allowlisted metadata.
7. Validate claim-level citations and abstain when evidence is insufficient.
8. Link retrieval and answering into a reproducible pipeline artifact.
9. Evaluate the pipeline against a fixed 20-case GLP-1 test set.
10. Compare compatible runs that change exactly one configuration value.
11. Render deterministic plain-text answers with deduplicated sources.

## 2. What it does not do

- It does not use private patient records or protected health information.
- It does not provide clinical advice or decision support.
- It currently discovers trial records instead of parsing arbitrary PDF protocols.
- It does not claim that an answer is trustworthy based on an aggregate score.
- It does not automatically rewrite prompts after a failed evaluation.
- It does not include an API, dashboard, or production monitoring stack.

## 3. Prerequisites

| Requirement | Needed for |
| --- | --- |
| Python 3.11+ | Every stage |
| Git Bash | Recommended command shell on Windows |
| DeepSeek API key | Discovery and answering |
| Internet access | Discovery, corpus detail fetches, and DeepSeek calls |
| Docker Desktop with Linux containers | TEI and Qdrant retrieval |
| About 1-2 GB free disk space | Python environment, Docker images, and model cache |

Verify the tools:

```bash
python --version
docker --version
docker compose version
git --version
```

## 4. First-time setup

Run these commands from Git Bash:

```bash
cd /path/to/clinical_doc_assist

python -m venv .venv
source .venv/Scripts/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

Create local configuration:

```bash
cp .env.example .env
```

Edit `.env` and set at least:

```dotenv
DEEPSEEK_API_KEY=your-real-key
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-flash
```

The retrieval defaults are already listed in `.env.example`. Do not commit `.env`.

Reinstall the editable package whenever a console entry point is added:

```bash
python -m pip install -e ".[dev]"
```

If a console command is unavailable, the module form works from the activated
virtual environment:

```bash
python -m clinical_doc_assist.research.cli --help
```

## 5. Start local retrieval services

```bash
docker compose up -d
docker compose ps
```

The first TEI startup downloads `BAAI/bge-small-en-v1.5`.

Check the services:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/info
curl http://127.0.0.1:6333/healthz
curl http://127.0.0.1:6333/readyz
```

Stop the containers without deleting data:

```bash
docker compose stop
```

Remove containers while preserving named volumes:

```bash
docker compose down
```

## 6. Fast path: ask one question end to end

Use this after discovery, corpus creation, and indexing are complete.

```bash
clinical-doc-ask \
  "What did NCT07424430 aim to evaluate?" \
  --collection clinical_evidence_v1 \
  --limit 5
```

Module equivalent:

```bash
python -m clinical_doc_assist.orchestration.cli \
  "What did NCT07424430 aim to evaluate?" \
  --collection clinical_evidence_v1 \
  --limit 5
```

This creates three linked artifacts:

```text
artifacts/retrieval/<retrieval-id>.json
artifacts/answers/<answer-id>.json
artifacts/pipelines/<pipeline-id>.json
```

The command prints the pipeline JSON. The answer is `insufficient_evidence` when
the collection does not contain adequate evidence.

## 7. Controlled staged workflow

The staged workflow is recommended when learning or debugging the system.

### Step 1: Discover and screen public records

```bash
clinical-doc-discover \
  "GLP-1 cardiovascular outcomes" \
  --updated-after 2023-01-01 \
  --updated-before 2026-10-21 \
  --limit 20 \
  --output artifacts/discovery/glp1-cardio.json
```

Discovery rules:

- `--limit` must be between 1 and 20.
- Dates use `YYYY-MM-DD`.
- The agent records current UTC time before searching.
- ClinicalTrials.gov is the only accepted source.
- The stage stops before corpus assembly.

Inspect `status`, `accepted`, `rejected`, and `needs_review` in the JSON artifact.

### Step 2: Build the evidence corpus

Repeat `--discovery-run` for each discovery artifact:

```bash
clinical-doc-corpus build \
  --discovery-run artifacts/discovery/glp1-cardio.json \
  --output artifacts/corpus/glp1-pilot
```

Optional chunk controls:

```bash
clinical-doc-corpus build \
  --discovery-run artifacts/discovery/glp1-cardio.json \
  --output artifacts/corpus/glp1-small-chunks \
  --max-chars 1200 \
  --overlap-chars 120
```

The output directory contains:

```text
manifest.json
documents.jsonl
chunks.jsonl
```

The manifest can be `completed` or `partial`. A partial corpus keeps successful
documents and exposes failed detail fetches.

### Step 3: Index corpus chunks

```bash
clinical-doc-retrieve index \
  --corpus artifacts/corpus/glp1-pilot \
  --collection clinical_evidence_v1 \
  --replace
```

Without `--replace`, reindexing the same corpus is idempotent because Qdrant point
IDs are deterministic.

An index manifest is written under `artifacts/index-runs/`.

### Step 4: Retrieve evidence

```bash
clinical-doc-retrieve search \
  "What cardiovascular outcomes were reported for semaglutide?" \
  --collection clinical_evidence_v1 \
  --limit 5 \
  --output artifacts/retrieval/semaglutide-cardio.json
```

The retrieval JSON records:

- Original query and collection.
- Ranking score and rank.
- Chunk and document IDs.
- NCT ID and section.
- Evidence text and source URL.
- Embedding model and content hash.

### Step 5: Answer from saved evidence

This stage does not require Docker when the retrieval artifact already exists:

```bash
clinical-doc-answer \
  --retrieval-run artifacts/retrieval/semaglutide-cardio.json \
  --output artifacts/answers/semaglutide-cardio-answer.json
```

The answer record can contain:

- `answered` with validated claims and citations.
- `insufficient_evidence` with a reason.
- `failed` with visible errors.

Raw model output is retained only for audit. It is not authoritative answer text.

## 8. Evaluate a fixed case set

The checked-in pilot suite is:

```text
evaluation/cases/glp1-eval-v1.json
```

### Generated evaluation

This mode runs feature 006 for all 20 cases. It requires DeepSeek, TEI, and Qdrant.

```bash
clinical-doc-eval run \
  --cases evaluation/cases/glp1-eval-v1.json \
  --collection clinical_evidence_v1 \
  --limit 5 \
  --output-dir artifacts/evaluations
```

### Saved evaluation

Saved mode is offline and deterministic. Create one JSON object mapping every case
ID to a pipeline path:

```json
{
  "glp1-001": "artifacts/pipelines/pipeline-001.json",
  "glp1-002": "artifacts/pipelines/pipeline-002.json"
}
```

The map must contain exactly the 20 case IDs with no missing or unknown entries.

```bash
clinical-doc-eval run \
  --cases evaluation/cases/glp1-eval-v1.json \
  --pipeline-map artifacts/evaluations/glp1-pipeline-map.json \
  --output-dir artifacts/evaluations
```

The command writes:

```text
artifacts/evaluations/<evaluation-id>.json
artifacts/evaluations/<evaluation-id>-verdicts.json
```

Quality failures are results, not crashes. Invalid case files, broken artifact
links, and incompatible configurations exit with an input error.

### Compare one controlled change

```bash
clinical-doc-eval compare \
  --baseline artifacts/evaluations/baseline.json \
  --candidate artifacts/evaluations/candidate.json \
  --output artifacts/evaluations/comparison.json
```

The reports must use the same case IDs and rubric versions. Exactly one
configuration value may differ.

See [evaluation-baseline.md](evaluation-baseline.md) for the initial results and
known limitations.

## 9. Present an answer

Without evaluation:

```bash
clinical-doc-present \
  --pipeline artifacts/pipelines/pipeline-001.json
```

With exact matching evaluation verdicts:

```bash
clinical-doc-present \
  --pipeline artifacts/pipelines/pipeline-001.json \
  --case-id glp1-001 \
  --evaluation artifacts/evaluations/evaluation-verdicts.json \
  --output artifacts/presentations/glp1-001.txt
```

The output contains:

- `ANSWER`: an extractive paragraph of at most 180 words.
- `QUALITY`: status, citation check, and any exact matching verdict.
- `SUPPORTING DETAIL`: every validated claim.
- `SOURCES`: deduplicated numbered source groups.
- `LIMITATIONS`: evaluation scope and non-clinical-use warning.

The complete output must remain below 1,000 words. Oversized content fails rather
than dropping claims.

## 10. Persist a readability review

Use the five-case rubric in
`human-readability-v1`:

| Criterion | Range |
| --- | --- |
| Direct answer | 0-2 |
| Claim completeness | 0-2 |
| Citation clarity | 0-2 |
| Structure | 0-2 |
| Caution and limitations | 0-2 |

Passing requires at least 8/10 and no zero for citation clarity or caution.

```bash
clinical-doc-eval review \
  --input artifacts/evaluations/presentation-review-input.json \
  --output-dir artifacts/evaluations/presentation-reviews
```

Reviews require five unique case IDs and the exact supported rubric version.

## 11. Run tests

Fast offline suite:

```bash
python -m pytest -o addopts= -q
python -m ruff check .
```

When Docker services are running:

```bash
RUN_DOCKER_INTEGRATION=1 python -m pytest -o addopts= -q tests/integration
```

All offline tests should pass, with three optional Docker tests skipped. The
env-gated integration suite adds those three tests when the services are running.

## 12. Troubleshooting

### A console command is missing

Reinstall the editable package:

```bash
python -m pip install -e ".[dev]"
```

### Docker ports are already in use

Check conflicting services:

```bash
docker compose ps
netstat -ano | findstr ":8080 :6333"
```

### TEI is still starting

```bash
docker compose logs -f embeddings
```

The first model download can take several minutes.

### Answers are `insufficient_evidence`

- Confirm the corpus was built successfully.
- Confirm the collection was indexed.
- Search the collection directly with `clinical-doc-retrieve search`.
- Check whether the question asks about an NCT ID absent from the evidence.

### Evaluation reports retrieval misses

Retrieval misses are quality findings, not infrastructure errors. Compare the
expected evidence IDs with the retrieval results and the corpus manifest.

### Windows displays non-ASCII characters incorrectly

JSON and text artifacts are UTF-8. Use a UTF-8-aware terminal for readable em
dashes and other Unicode characters; evaluation logic itself is unaffected.
