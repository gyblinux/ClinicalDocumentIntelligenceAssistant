"""Deterministic chunking for normalized evidence documents."""

from __future__ import annotations

import hashlib
import re

from clinical_doc_assist.corpus.models import (
    BuildSettings,
    EvidenceChunk,
    EvidenceDocument,
)

SENTENCE_END = re.compile(r"[.!?](?:\s|$)")
TOKEN_BEFORE_PERIOD = re.compile(r"([A-Za-z][A-Za-z.]*)$")
ABBREVIATIONS = frozenset({"e.g", "i.e", "u.s", "dr", "prof", "mr", "ms", "vs", "fig", "no", "etc"})


def chunk_document(
    document: EvidenceDocument,
    settings: BuildSettings,
) -> tuple[EvidenceChunk, ...]:
    """Chunk every section without crossing document or section boundaries."""

    chunks: list[EvidenceChunk] = []
    for section in document.sections:
        for chunk_index, (start, end) in enumerate(
            _split_offsets(
                section.content,
                max_chars=settings.max_chars,
                overlap_chars=settings.overlap_chars,
            )
        ):
            text = section.content[start:end]
            content_hash = _hash(text)
            chunk_id = _hash(f"{document.nct_id}|{section.name}|{start}|{end}|{content_hash}")[:24]
            chunks.append(
                EvidenceChunk(
                    chunk_id=f"chunk-{chunk_id}",
                    document_id=document.document_id,
                    nct_id=document.nct_id,
                    section=section.name,
                    chunk_index=chunk_index,
                    start_char=start,
                    end_char=end,
                    text=text,
                    content_hash=content_hash,
                    source_url=document.source_url,
                )
            )
    return tuple(chunks)


def _split_offsets(
    text: str,
    *,
    max_chars: int,
    overlap_chars: int,
) -> tuple[tuple[int, int], ...]:
    if not text:
        return ()
    if len(text) <= max_chars:
        return ((0, len(text)),)

    offsets: list[tuple[int, int]] = []
    start = 0
    while start < len(text):
        limit = min(start + max_chars, len(text))
        end = _natural_end(text, start, limit) if limit < len(text) else len(text)
        if end <= start:
            end = limit
        offsets.append((start, end))
        if end >= len(text):
            break
        start = _next_start(text, start, end, overlap_chars)
    return tuple(offsets)


def _natural_end(text: str, start: int, limit: int) -> int:
    minimum = start + (limit - start) // 2

    paragraph_end = text.rfind("\n\n", minimum, limit)
    if paragraph_end >= minimum:
        return paragraph_end + 2

    sentence_end = -1
    for match in SENTENCE_END.finditer(text, minimum, limit):
        if _is_sentence_boundary(text, match.start(), start):
            sentence_end = match.end()
    if sentence_end > minimum:
        return sentence_end

    newline_end = text.rfind("\n", minimum, limit)
    if newline_end >= minimum:
        return newline_end + 1

    space_end = text.rfind(" ", minimum, limit)
    if space_end >= minimum:
        return space_end + 1

    return limit


def _next_start(text: str, start: int, end: int, overlap_chars: int) -> int:
    candidate = max(start + 1, end - overlap_chars)
    if candidate >= end:
        return end

    if candidate > 0 and text[candidate - 1].isalnum() and text[candidate].isalnum():
        whitespace = re.search(r"\s", text[candidate:end])
        if whitespace is not None:
            candidate += whitespace.end()

    while candidate < end and text[candidate].isspace():
        candidate += 1
    return candidate


def _is_sentence_boundary(text: str, punctuation: int, start: int) -> bool:
    if text[punctuation] != ".":
        return True
    match = TOKEN_BEFORE_PERIOD.search(text[start:punctuation])
    if match is None:
        return True
    token = match.group(1).lower()
    return token not in ABBREVIATIONS and not (len(token) == 1 and token.isalpha())


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
