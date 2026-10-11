"""Generate an answer from retrieved context.

The app tries LLM providers in order and uses the first one available:

  1. Groq  — hosted, OpenAI-compatible API (needs GROQ_API_KEY + internet).
  2. Ollama — a local LLM server, if one is running.
  3. Extractive fallback — returns the most relevant sentences from the context.

The fallback guarantees the app always produces a cited answer, even with no
API key, no local LLM, and no internet. All paths are generators that yield
text, so the same code powers both the normal and the streaming endpoints.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterator

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_llm_override = None  # used by tests: a callable (question, context) -> str


def set_llm(fn) -> None:
    global _llm_override
    _llm_override = fn


# Returned verbatim when the retrieved context does not answer the question.
NO_CONTEXT_MESSAGE = (
    "No relevant content was found in the uploaded documents for this "
    "namespace to answer that question."
)


def build_prompt(question: str, context: str, history: str) -> str:
    return (
        "You are a strict document assistant. Answer the question using ONLY the "
        "context below. Do NOT use outside or general knowledge. If the context "
        "does not contain the answer, reply with EXACTLY this sentence and "
        f"nothing else: \"{NO_CONTEXT_MESSAGE}\"\n\n"
        f"Conversation so far:\n{history or '(none)'}\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {question}\n\nAnswer:"
    )


def _extractive_answer(question: str, context: str) -> str:
    """Pick the sentences from the context that best overlap the question."""
    sentences = re.split(r"(?<=[.!?])\s+", context)
    q_words = {w.lower() for w in re.findall(r"\w+", question)}
    scored = []
    for sentence in sentences:
        s_words = {w.lower() for w in re.findall(r"\w+", sentence)}
        overlap = len(q_words & s_words)
        if overlap:
            scored.append((overlap, sentence.strip()))
    scored.sort(reverse=True)
    if not scored:
        return "I couldn't find an answer in the uploaded documents."
    return " ".join(s for _, s in scored[:3])


def _stream_groq(prompt: str) -> Iterator[str]:
    """Stream tokens from Groq's OpenAI-compatible chat API."""
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": settings.groq_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
    }
    with httpx.stream(
        "POST", settings.groq_url, headers=headers, json=body, timeout=60.0
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            # Groq sends Server-Sent Events: lines prefixed with "data: ".
            if not line or not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload.strip() == "[DONE]":
                break
            data = json.loads(payload)
            delta = data["choices"][0]["delta"].get("content")
            if delta:
                yield delta


def _stream_ollama(prompt: str) -> Iterator[str]:
    """Stream tokens from a local Ollama server."""
    with httpx.stream(
        "POST",
        f"{settings.ollama_url}/api/generate",
        json={"model": settings.ollama_model, "prompt": prompt, "stream": True},
        timeout=60.0,
    ) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if not line:
                continue
            data = json.loads(line)
            if data.get("response"):
                yield data["response"]


def generate_stream(question: str, context: str, history: str = "") -> Iterator[str]:
    """Yield the answer piece by piece, trying each provider in order."""
    if _llm_override is not None:
        yield _llm_override(question, context)
        return

    prompt = build_prompt(question, context, history)

    # 1. Groq (only if an API key is configured).
    if settings.groq_api_key:
        try:
            yielded = False
            for token in _stream_groq(prompt):
                yielded = True
                yield token
            if yielded:
                return
        except Exception as exc:
            logger.info("Groq unavailable, trying next provider: %s", exc)

    # 2. Ollama (local).
    try:
        yielded = False
        for token in _stream_ollama(prompt):
            yielded = True
            yield token
        if yielded:
            return
    except Exception as exc:
        logger.info("Ollama unavailable, using extractive fallback: %s", exc)

    # 3. Extractive fallback (always works).
    yield _extractive_answer(question, context)
