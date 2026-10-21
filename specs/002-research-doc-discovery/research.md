# Research: Research Document Discovery

## ClinicalTrials.gov API

**Decision**: Use the official ClinicalTrials.gov REST API v2 endpoint
`GET https://clinicaltrials.gov/api/v2/studies`.

**Rationale**: It is the approved source for this feature, requires no private
credential, returns structured study metadata, and avoids general web crawling.
The official search-area documentation confirms `query.term` for the basic topic
search. A live read-only request confirmed that
`filter.advanced=AREA[LastUpdatePostDate]RANGE[after,before]` filters the update
window, `sort=LastUpdatePostDate:desc` returns newest records first, and the
selected response fields map as expected.

**Alternatives considered**:

- General web search: rejected because provenance and source reliability would be
  less deterministic.
- PubMed/Europe PMC: deferred until a literature source adapter is specified.
- HTML scraping: rejected because the official API is simpler and more stable.

## Source Metadata

**Decision**: Request only `NCTId`, `BriefTitle`, `OfficialTitle`,
`OverallStatus`, `StudyType`, `LastUpdatePostDate`, `StudyFirstPostDate`,
`BriefSummary`, and `LeadSponsorName`.

**Rationale**: This supports relevance review, date filtering, deduplication,
source links, and a short evidence snippet without storing full study records.

**Alternatives considered**: Downloading full study documents in this stage was
rejected because the approved scope stops before ingestion.

## Agent Shape

**Decision**: Use one research agent with two callable capabilities:
`get_current_datetime` and `search_clinical_trials`.

**Rationale**: A single agent remains understandable and cheap. The application
can enforce tool order, retain authoritative tool output, and apply deterministic
screening independently of generated text.

**Alternatives considered**:

- Multiple specialist agents: rejected for coordination, latency, and evaluation
  overhead before a measured need.
- Fully deterministic search without a model: rejected because topic selection
  and relevance reflection are part of the requested first feature.

## Reflection and Trust

**Decision**: Treat the model's candidate classification as advisory and resolve
it against deterministic rules.

**Rationale**: Prompt-only reliability is insufficient. The model can assess
topic relevance, but application code must decide whether a record has an
approved source, a valid date, a unique identifier, and complete metadata.

**Alternatives considered**: Accepting model classifications directly was
rejected because it could allow fabricated or ineligible candidates.

## Current Time

**Decision**: Return the current time in UTC using ISO 8601 and record it in the
run. Block source search until the tool succeeds.

**Rationale**: The current time is an audit value and the gateway for a valid
discovery run. It does not replace the explicit user-provided date window.

**Alternatives considered**: Injecting the time silently from application code
was rejected because the user explicitly requested a small time tool and
inspectable tool use.

## Output and Reproducibility

**Decision**: Emit one JSON object to standard output.

**Rationale**: It is directly inspectable, redirectable to a file, and easy to
compare across runs without adding a database or UI.

**Alternatives considered**: A database, dashboard, or artifact service was
rejected as unnecessary for a one-user practice project.

## Network Isolation

**Decision**: Add `httpx` as a direct dependency and test the source adapter with
`httpx.MockTransport`.

**Rationale**: The request contract can be verified without network access and
the tests remain reproducible.

**Alternatives considered**: Live integration tests were rejected because they
would be slow, rate-limited, and dependent on changing public data.
