"""
retrieval.py
============
RAG Retrieval Engine — bridges ChromaDB vector store + Firebase cache
to the Google ADK agent (agent.py).

Responsibilities:
  ① Semantic retrieval from ChromaDB with relevance scoring
  ② Two-tier caching: in-memory LRU → Firebase Firestore
  ③ API rate-limit budget tracking and back-off
  ④ Input preprocessing: Romanian text normalization, query expansion
  ⑤ Context assembly with ranked, deduplicated chunks
  ⑥ Post-processing: formatting, truncation, loophole tagging
  ⑦ ADK-compatible tool functions (sync wrappers over async logic)
  ⑧ End-to-end testing helpers
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional

from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from vector_store import VectorStore
from firebase_client import FirebaseClient

logger = logging.getLogger("retrieval")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


# ══════════════════════════════════════════════════════════════════════════════
# 1. CONFIGURATION
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RetrievalConfig:
    # Vector search
    n_results: int = 8
    min_relevance: float = 0.25
    max_context_chars: int = 12_000

    # Cache
    memory_cache_size: int = 256
    firebase_cache_ttl_hours: int = 6

    # Rate limiting
    max_requests_per_minute: int = 55
    back_off_base_seconds: float = 2.0
    max_retries: int = 4

    # Prompt
    language_level: str = "simplu"       # simplu | mediu | tehnic
    include_loopholes: bool = True
    include_sources: bool = True

    # Sources
    sources: list[str] = field(default_factory=lambda: ["monitorul_oficial", "anaf"])


# ══════════════════════════════════════════════════════════════════════════════
# 2. IN-MEMORY LRU CACHE
# ══════════════════════════════════════════════════════════════════════════════

class LRUCache:
    def __init__(self, maxsize: int = 256):
        self._cache: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._maxsize = maxsize

    def _key(self, query: str, sources: list[str], level: str) -> str:
        raw = f"{query.strip().lower()}|{'|'.join(sorted(sources))}|{level}"
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def get(self, query: str, sources: list[str], level: str) -> Optional[dict]:
        k = self._key(query, sources, level)
        if k not in self._cache:
            return None
        value, _ = self._cache[k]
        self._cache.move_to_end(k)
        return value

    def set(self, query: str, sources: list[str], level: str, value: dict):
        k = self._key(query, sources, level)
        self._cache[k] = (value, time.monotonic())
        self._cache.move_to_end(k)
        if len(self._cache) > self._maxsize:
            self._cache.popitem(last=False)

    def clear(self):
        self._cache.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


# ══════════════════════════════════════════════════════════════════════════════
# 3. RATE LIMITER
# ══════════════════════════════════════════════════════════════════════════════

class RateLimiter:
    """Token-bucket sliding-window rate limiter."""

    def __init__(self, rpm: int = 55):
        self._rpm = rpm
        self._call_times: list[float] = []

    async def acquire(self):
        now = time.monotonic()
        self._call_times = [t for t in self._call_times if now - t < 60]
        if len(self._call_times) >= self._rpm:
            wait = 60.0 - (now - self._call_times[0]) + 0.05
            logger.warning("Rate limit reached — sleeping %.2fs", wait)
            await asyncio.sleep(wait)
        self._call_times.append(time.monotonic())

    @property
    def current_usage(self) -> int:
        now = time.monotonic()
        return len([t for t in self._call_times if now - t < 60])


# ══════════════════════════════════════════════════════════════════════════════
# 4. INPUT PREPROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

_SYNONYM_MAP: dict[str, list[str]] = {
    "tva": ["taxa pe valoarea adaugata", "TVA", "impozit indirect"],
    "impozit": ["impozit", "taxa", "contributie"],
    "pfa": ["persoana fizica autorizata", "PFA", "liber profesionist"],
    "srl": ["societate cu raspundere limitata", "SRL", "firma"],
    "anaf": ["ANAF", "administratie fiscala", "fisc"],
    "dividende": ["dividende", "distribuire profit", "venituri din dividende"],
    "cas": ["contributie asigurari sociale", "CAS", "pensie"],
    "cass": ["contributie asigurari sanatate", "CASS", "sanatate"],
    "declaratie": ["declaratie", "formularul", "D212", "D100"],
    "microintreprindere": ["micro", "1% impozit", "3% impozit", "impozit pe venit microintreprindere"],
}

_LEGAL_STOPWORDS = {
    "si", "sau", "dar", "in", "la", "de", "cu", "pe", "pentru", "prin",
    "din", "ca", "cel", "cea", "cei", "cele", "al", "a", "ale", "lui",
    "sunt", "este", "fi", "fost", "vor", "va", "voi", "care", "ce", "cum",
}


@dataclass
class ProcessedQuery:
    original: str
    cleaned: str
    normalized: str
    expanded_terms: list[str]
    tokens: list[str]
    search_query: str


class InputPreprocessor:
    def process(self, raw_query: str) -> ProcessedQuery:
        cleaned = self._clean(raw_query)
        normalized = self._normalize_diacritics(cleaned)
        expanded_terms = self._expand_synonyms(normalized)
        tokens = self._tokenize(normalized)
        return ProcessedQuery(
            original=raw_query,
            cleaned=cleaned,
            normalized=normalized,
            expanded_terms=expanded_terms,
            tokens=tokens,
            search_query=self._build_search_query(normalized, expanded_terms),
        )

    @staticmethod
    def _clean(text: str) -> str:
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"[^\w\s\-.,?!ăîșțâĂÎȘȚÂ]", " ", text, flags=re.UNICODE)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _normalize_diacritics(text: str) -> str:
        for old, new in {"ş": "ș", "Ş": "Ș", "ţ": "ț", "Ţ": "Ț"}.items():
            text = text.replace(old, new)
        return text

    def _expand_synonyms(self, text: str) -> list[str]:
        words = text.lower().split()
        expansions = []
        for word in words:
            if word in _SYNONYM_MAP:
                expansions.extend(_SYNONYM_MAP[word])
        return list(set(expansions))

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.findall(r"\b\w+\b", text.lower(), flags=re.UNICODE)
        return [t for t in tokens if t not in _LEGAL_STOPWORDS and len(t) > 2]

    def _build_search_query(self, normalized: str, expansions: list[str]) -> str:
        if not expansions:
            return normalized
        return f"{normalized} {' '.join(expansions[:3])}".strip()


# ══════════════════════════════════════════════════════════════════════════════
# 5. CONTEXT ASSEMBLER
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class RetrievedChunk:
    text: str
    doc_id: str
    title: str
    source: str
    url: str
    date: str
    relevance: float
    chunk_index: int


@dataclass
class AssembledContext:
    context_text: str
    chunks: list[RetrievedChunk]
    sources: list[dict]
    total_chars: int
    truncated: bool


class ContextAssembler:
    def assemble(
        self,
        raw_results: dict,
        max_chars: int = 12_000,
        min_relevance: float = 0.25,
    ) -> AssembledContext:
        chunks = self._parse_results(raw_results)
        chunks = self._filter_relevance(chunks, min_relevance)
        chunks = self._deduplicate(chunks)
        chunks = self._rerank(chunks)
        context_text, truncated = self._build_text(chunks, max_chars)
        sources = self._extract_sources(chunks)
        return AssembledContext(
            context_text=context_text,
            chunks=chunks,
            sources=sources,
            total_chars=len(context_text),
            truncated=truncated,
        )

    def _parse_results(self, raw: dict) -> list[RetrievedChunk]:
        docs = raw.get("documents", [[]])[0]
        metas = raw.get("metadatas", [[]])[0]
        distances = raw.get("distances", [[]])[0]
        chunks = []
        for i, (doc, meta) in enumerate(zip(docs, metas)):
            dist = distances[i] if distances else 0.5
            relevance = max(0.0, 1.0 - dist)
            chunks.append(RetrievedChunk(
                text=doc,
                doc_id=meta.get("doc_id", f"doc_{i}"),
                title=meta.get("title", "Fără titlu"),
                source=meta.get("source", "unknown"),
                url=meta.get("url", ""),
                date=meta.get("date", ""),
                relevance=relevance,
                chunk_index=meta.get("chunk_index", i),
            ))
        return chunks

    def _filter_relevance(self, chunks: list[RetrievedChunk], threshold: float) -> list[RetrievedChunk]:
        filtered = [c for c in chunks if c.relevance >= threshold]
        if not filtered:
            return sorted(chunks, key=lambda c: c.relevance, reverse=True)[:3]
        return filtered

    def _deduplicate(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        seen_fps: set[str] = set()
        unique = []
        for chunk in chunks:
            fp = re.sub(r"\s+", "", chunk.text[:120].lower())
            if fp not in seen_fps:
                seen_fps.add(fp)
                unique.append(chunk)
        return unique

    def _rerank(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        def score(c: RetrievedChunk) -> float:
            base = c.relevance
            try:
                age_days = (datetime.utcnow() - datetime.fromisoformat(c.date)).days
                recency = max(0, (90 - age_days) / 90) * 0.15
            except Exception:
                recency = 0.0
            source_boost = 0.05 if c.source == "anaf" else 0.0
            return base + recency + source_boost
        return sorted(chunks, key=score, reverse=True)

    def _build_text(self, chunks: list[RetrievedChunk], max_chars: int) -> tuple[str, bool]:
        parts: list[str] = []
        total = 0
        truncated = False
        sep = "\n\n" + "─" * 60 + "\n\n"
        for i, chunk in enumerate(chunks):
            header = (
                f"[Sursă {i+1} | {chunk.source.upper()} | "
                f"{chunk.title[:60]} | {chunk.date} | Relevanță: {chunk.relevance:.0%}]"
            )
            block = f"{header}\n{chunk.text}"
            if total + len(block) > max_chars:
                remaining = max_chars - total - len(header) - 60
                if remaining > 200:
                    block = f"{header}\n{chunk.text[:remaining]}...[trunchiat]"
                    parts.append(block)
                truncated = True
                break
            parts.append(block)
            total += len(block)
        return sep.join(parts), truncated

    def _extract_sources(self, chunks: list[RetrievedChunk]) -> list[dict]:
        seen: set[str] = set()
        sources = []
        for chunk in chunks:
            if chunk.doc_id not in seen:
                seen.add(chunk.doc_id)
                sources.append({
                    "doc_id": chunk.doc_id,
                    "title": chunk.title,
                    "source": chunk.source,
                    "url": chunk.url,
                    "date": chunk.date,
                    "relevance": round(chunk.relevance, 3),
                })
        return sources


# ══════════════════════════════════════════════════════════════════════════════
# 6. PROMPT BUILDER
# ══════════════════════════════════════════════════════════════════════════════

LEVEL_INSTRUCTIONS: dict[str, str] = {
    "simplu": (
        "Explică în LIMBAJ SIMPLU, accesibil oricui fără pregătire juridică. "
        "Folosește propoziții scurte, exemple concrete din viața de zi cu zi. "
        "Evită jargonul — dacă folosești un termen tehnic, explică-l imediat. "
        "Structură obligatorie: 1) Ce înseamnă, 2) Impact practic, 3) Ce trebuie să faci."
    ),
    "mediu": (
        "Explică pentru PROFESIONIȘTI (contabili, antreprenori, manageri). "
        "Folosești termeni tehnici când e necesar, cu explicarea implicațiilor practice. "
        "Structură: 1) Rezumat, 2) Prevederi cheie, 3) Obligații/Drepturi, 4) Termene și sancțiuni."
    ),
    "tehnic": (
        "Răspuns JURIDIC COMPLET cu referințe exacte la articole, alineate, termene, excepții. "
        "Include corelații cu alte acte normative. "
        "Structură: 1) Temei legal, 2) Conținut normativ, 3) Aplicare practică, 4) Excepții și derogări."
    ),
}

LOOPHOLE_INSTRUCTION = """
IDENTIFICARE EXCEPȚII ȘI OPORTUNITĂȚI LEGALE:
Analizează textul legislativ și identifică:
  - Excepții de la regulă (când legea nu se aplică)
  - Praguri și limite (sub/peste care se aplică reguli diferite)
  - Scutiri și facilități fiscale aplicabile
  - Opțiuni de optimizare fiscală strict legală
  - Termene ce pot fi valorificate strategic
NOTĂ: Aceste interpretări sunt orientative — recomandă consultarea unui specialist fiscal.
"""

SOURCE_FOOTER = """
SURSE UTILIZATE:
La finalul răspunsului, listează sursele citate cu: denumire act normativ, sursă (MO/ANAF), URL.
"""

SYSTEM_PROMPT = """Ești LawAgent, un expert în legislație financiară și fiscală din România, cu acces la baza de date RAG.
Accesezi documente indexate din Monitorul Oficial al României și ANAF.

REGULI STRICTE:
- Răspunde EXCLUSIV în limba română
- Bazează-te DOAR pe documentele din contextul primit — nu inventa informații
- Dacă o informație lipsește din context, spune explicit că nu ai date suficiente
- Menționează SURSA și ACTUL NORMATIV pentru fiecare afirmație importantă
- Nu oferi sfaturi juridice personalizate — recomandă consultarea unui specialist
- Avertizează dacă legislația a putut fi modificată după data documentului

Integrări disponibile:
  ① ChromaDB — baza de date vectorială cu legislație indexată
  ② Firebase Firestore — istoricul sesiunilor și metadate documente
  ③ Google Search sub-agent — verificarea legislației recente
  ④ URL Context sub-agent — citire directă pagini ANAF/Monitorul Oficial
"""


class PromptBuilder:
    def build_rag_context_prompt(
        self,
        query: ProcessedQuery,
        context: AssembledContext,
        language_level: str = "simplu",
        include_loopholes: bool = True,
        conversation_history: str = "",
    ) -> str:
        level_instr = LEVEL_INSTRUCTIONS.get(language_level, LEVEL_INSTRUCTIONS["simplu"])
        loophole_block = LOOPHOLE_INSTRUCTION if include_loopholes else ""
        history_block = f"\nCONTEXT CONVERSAȚIE ANTERIOARĂ:\n{conversation_history}\n" if conversation_history else ""
        truncation_note = "\n⚠️ [Context trunchiat — au fost găsite mai multe documente relevante.]\n" if context.truncated else ""

        return f"""{SYSTEM_PROMPT}

{'=' * 70}
CONTEXT DIN BAZA DE DATE LEGISLATIVĂ (ChromaDB + Firebase):
{'=' * 70}
{context.context_text}
{truncation_note}
ÎNTREBAREA ORIGINALĂ: {query.original}
TERMENI DE CĂUTARE: {query.search_query}
TERMENI IDENTIFICAȚI: {', '.join(query.tokens[:10])}
{history_block}
{'=' * 70}
INSTRUCȚIUNI:
{'=' * 70}
NIVEL LIMBAJ: {level_instr}

{loophole_block}

{SOURCE_FOOTER}
""".strip()

    def build_fallback_prompt(self, query: ProcessedQuery, language_level: str = "simplu") -> str:
        return f"""{SYSTEM_PROMPT}

Nu am găsit documente relevante în baza de date locală.

ÎNTREBAREA: {query.original}

ACȚIUNI NECESARE:
1. Folosește sub-agentul Google Search pentru a căuta legislația actuală
2. Accesează URL-uri relevante ANAF/Monitorul Oficial cu sub-agentul URL Context
3. Răspunde la nivelul: {LEVEL_INSTRUCTIONS.get(language_level, LEVEL_INSTRUCTIONS['simplu'])}

Indică explicit că informația provine din surse web, nu din baza de date locală.
""".strip()


# ══════════════════════════════════════════════════════════════════════════════
# 7. POST-PROCESSOR
# ══════════════════════════════════════════════════════════════════════════════

class ResponsePostProcessor:
    MAX_CHARS = 8_000

    def process(self, raw_response: str, sources: list[dict], language_level: str) -> dict:
        cleaned = self._clean(raw_response)
        truncated_flag = len(cleaned) > self.MAX_CHARS
        truncated = self._truncate(cleaned)
        loopholes = self._extract_loopholes(truncated)
        quality = self._quality_score(truncated, sources)
        return {
            "response": truncated,
            "loopholes": loopholes,
            "sources": sources,
            "quality_score": quality,
            "language_level": language_level,
            "char_count": len(truncated),
            "truncated": truncated_flag,
            "processed_at": datetime.utcnow().isoformat(),
        }

    def _clean(self, text: str) -> str:
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    def _truncate(self, text: str) -> str:
        if len(text) <= self.MAX_CHARS:
            return text
        cut = text[: self.MAX_CHARS]
        last_period = cut.rfind(". ")
        if last_period > self.MAX_CHARS * 0.7:
            cut = cut[: last_period + 1]
        return cut + "\n\n[Răspuns trunchiat — consultați sursele pentru detalii complete]"

    def _extract_loopholes(self, text: str) -> list[str]:
        patterns = [
            r"(?i)excepție[:\s]+([^\n.]{20,200})",
            r"(?i)scutire[:\s]+([^\n.]{20,200})",
            r"(?i)oportunitate[:\s]+([^\n.]{20,200})",
            r"(?i)facilitat[eă][:\s]+([^\n.]{20,200})",
            r"(?i)optimizare[:\s]+([^\n.]{20,200})",
        ]
        results = []
        for p in patterns:
            results.extend(m.strip() for m in re.findall(p, text)[:2])
        return results[:5]

    def _quality_score(self, text: str, sources: list[dict]) -> float:
        score = 0.5
        if len(text) > 300:
            score += 0.1
        score += min(len(sources) * 0.05, 0.2)
        if any(kw in text.lower() for kw in ["articol", "alineat", "lege", "ordonanță", "hotărâre"]):
            score += 0.1
        if "nu am informații" in text.lower() or "nu știu" in text.lower():
            score -= 0.2
        return max(0.0, min(1.0, score))


# ══════════════════════════════════════════════════════════════════════════════
# 8. RETRIEVAL ENGINE
# ══════════════════════════════════════════════════════════════════════════════

class RetrievalEngine:
    """
    Orchestrates retrieval: VectorStore → Cache → Preprocessor → Assembler → PromptBuilder.
    Exposed to the ADK agent via tool functions at the bottom of this file.
    """

    def __init__(self, config: Optional[RetrievalConfig] = None):
        self.config = config or RetrievalConfig()
        self.vector_store = VectorStore()
        self.firebase = FirebaseClient()
        self.memory_cache = LRUCache(maxsize=self.config.memory_cache_size)
        self.rate_limiter = RateLimiter(rpm=self.config.max_requests_per_minute)
        self.preprocessor = InputPreprocessor()
        self.assembler = ContextAssembler()
        self.prompt_builder = PromptBuilder()
        self.postprocessor = ResponsePostProcessor()
        logger.info(
            "RetrievalEngine ready — %d chunks indexed",
            self.vector_store.collection.count(),
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    async def retrieve_and_build_prompt(
        self,
        query: str,
        session_id: str = "default",
        language_level: Optional[str] = None,
        sources: Optional[list[str]] = None,
        include_loopholes: Optional[bool] = None,
        bypass_cache: bool = False,
    ) -> dict:
        level = language_level or self.config.language_level
        src = sources or self.config.sources
        loopholes = include_loopholes if include_loopholes is not None else self.config.include_loopholes

        await self.rate_limiter.acquire()

        # ① Memory cache
        if not bypass_cache:
            cached = self.memory_cache.get(query, src, level)
            if cached:
                logger.info("Memory cache HIT")
                return {**cached, "cache_hit": True, "cache_source": "memory"}

        # ② Firebase cache
        if not bypass_cache:
            fb_cached = await self._firebase_cache_get(query, src, level)
            if fb_cached:
                self.memory_cache.set(query, src, level, fb_cached)
                logger.info("Firebase cache HIT")
                return {**fb_cached, "cache_hit": True, "cache_source": "firebase"}

        # ③ Preprocess
        processed = self.preprocessor.process(query)
        logger.info("Processed query: tokens=%s", processed.tokens[:5])

        # ④ Retrieve
        raw_results = await self._retrieve_with_retry(processed, src)

        # ⑤ Assemble context
        context = self.assembler.assemble(
            raw_results,
            max_chars=self.config.max_context_chars,
            min_relevance=self.config.min_relevance,
        )

        # ⑥ Conversation history
        history = await self.firebase.get_conversation(session_id)
        history_text = self._format_history(history[-4:])

        # ⑦ Build prompt
        fallback = not context.chunks
        if fallback:
            prompt = self.prompt_builder.build_fallback_prompt(processed, level)
            logger.warning("No local context — fallback to web search")
        else:
            prompt = self.prompt_builder.build_rag_context_prompt(
                query=processed,
                context=context,
                language_level=level,
                include_loopholes=loopholes,
                conversation_history=history_text,
            )

        result = {
            "prompt": prompt,
            "context": {
                "total_chars": context.total_chars,
                "chunk_count": len(context.chunks),
                "truncated": context.truncated,
            },
            "sources": context.sources,
            "processed_query": {
                "original": processed.original,
                "search_query": processed.search_query,
                "tokens": processed.tokens,
                "expansions": processed.expanded_terms,
            },
            "fallback": fallback,
            "cache_hit": False,
            "language_level": level,
        }

        self.memory_cache.set(query, src, level, result)
        await self._firebase_cache_set(query, src, level, result)
        return result

    async def process_agent_response(
        self,
        raw_response: str,
        query: str,
        session_id: str,
        sources: list[dict],
        language_level: str = "simplu",
    ) -> dict:
        processed = self.postprocessor.process(raw_response, sources, language_level)
        ts = datetime.utcnow().isoformat()
        await self.firebase.append_message(session_id, {"role": "user", "content": query, "timestamp": ts})
        await self.firebase.append_message(session_id, {
            "role": "assistant",
            "content": processed["response"],
            "sources": sources,
            "loopholes": processed["loopholes"],
            "quality_score": processed["quality_score"],
            "timestamp": ts,
        })
        return processed

    async def get_retrieval_stats(self) -> dict:
        vs_stats = self.vector_store.get_stats()
        return {
            "vector_store": vs_stats,
            "memory_cache": {"size": self.memory_cache.size, "max": self.config.memory_cache_size},
            "rate_limiter": {"current_rpm": self.rate_limiter.current_usage, "limit": self.config.max_requests_per_minute},
            "config": {
                "n_results": self.config.n_results,
                "min_relevance": self.config.min_relevance,
                "language_level": self.config.language_level,
                "sources": self.config.sources,
            },
        }

    # ── Private ────────────────────────────────────────────────────────────────

    async def _retrieve_with_retry(self, processed: ProcessedQuery, sources: list[str]) -> dict:
        where_filter = {"source": {"$in": sources}} if sources else None
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(self.config.max_retries),
                wait=wait_exponential(multiplier=self.config.back_off_base_seconds, max=30),
                retry=retry_if_exception_type(Exception),
                reraise=True,
            ):
                with attempt:
                    return await asyncio.to_thread(
                        self.vector_store.query,
                        query_text=processed.search_query,
                        n_results=self.config.n_results,
                        where=where_filter,
                    )
        except RetryError as e:
            logger.error("Retrieval failed after %d retries: %s", self.config.max_retries, e)
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    async def _firebase_cache_get(self, query: str, sources: list[str], level: str) -> Optional[dict]:
        try:
            key = self._cache_key(query, sources, level)
            doc = await self.firebase.db.collection("retrieval_cache").document(key).get()
            if not doc.exists:
                return None
            data = doc.to_dict()
            cached_at = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
            if datetime.utcnow() - cached_at > timedelta(hours=self.config.firebase_cache_ttl_hours):
                await self.firebase.db.collection("retrieval_cache").document(key).delete()
                return None
            return data.get("result")
        except Exception as e:
            logger.debug("Firebase cache get error: %s", e)
            return None

    async def _firebase_cache_set(self, query: str, sources: list[str], level: str, result: dict):
        try:
            key = self._cache_key(query, sources, level)
            cacheable = {k: v for k, v in result.items() if k != "prompt"}
            await self.firebase.db.collection("retrieval_cache").document(key).set({
                "result": cacheable,
                "query_preview": query[:100],
                "cached_at": datetime.utcnow().isoformat(),
            })
        except Exception as e:
            logger.debug("Firebase cache set error: %s", e)

    @staticmethod
    def _cache_key(query: str, sources: list[str], level: str) -> str:
        raw = f"{query.strip().lower()}|{'|'.join(sorted(sources))}|{level}"
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    @staticmethod
    def _format_history(history: list[dict]) -> str:
        if not history:
            return ""
        lines = []
        for msg in history:
            role = "Utilizator" if msg.get("role") == "user" else "Asistent"
            lines.append(f"{role}: {msg.get('content', '')[:200]}")
        return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# 9. SINGLETON
# ══════════════════════════════════════════════════════════════════════════════

_engine: Optional[RetrievalEngine] = None


def get_engine(config: Optional[RetrievalConfig] = None) -> RetrievalEngine:
    global _engine
    if _engine is None:
        _engine = RetrievalEngine(config=config)
    return _engine


def _run(coro):
    """Run async coroutine from sync context (ADK tool calls are sync)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)


# ══════════════════════════════════════════════════════════════════════════════
# 10. ADK TOOL FUNCTIONS
#     Registered in agent.py via agent_tool.AgentTool or google.adk.tools.FunctionTool
# ══════════════════════════════════════════════════════════════════════════════

def retrieve_legal_context(
    query: str,
    session_id: str = "default",
    language_level: str = "simplu",
    sources: str = "monitorul_oficial,anaf",
    include_loopholes: bool = True,
) -> dict:
    """
    Retrieve Romanian fiscal/legal context from the RAG vector database.

    Call this FIRST before answering any legal or fiscal question.
    Returns an enriched prompt and cited sources from Monitorul Oficial and ANAF.

    Args:
        query: The user's question about Romanian law or fiscal policy.
        session_id: Conversation ID for multi-turn context.
        language_level: 'simplu' (plain), 'mediu' (professional), 'tehnic' (legal).
        sources: Comma-separated — 'monitorul_oficial', 'anaf', or both.
        include_loopholes: Set True to identify legal exceptions and fiscal optimizations.

    Returns:
        {
          prompt: str,             # Context-enriched prompt to answer with
          sources: list[dict],     # Documents cited
          context: dict,           # Chunk count, char count, truncated flag
          processed_query: dict,   # Cleaned query, tokens, expansions
          fallback: bool,          # True = no local docs, use web search
          cache_hit: bool,
          language_level: str,
        }
    """
    src_list = [s.strip() for s in sources.split(",") if s.strip()]
    return _run(get_engine().retrieve_and_build_prompt(
        query=query,
        session_id=session_id,
        language_level=language_level,
        sources=src_list,
        include_loopholes=include_loopholes,
    ))


def save_agent_response(
    response_text: str,
    query: str,
    session_id: str = "default",
    sources_json: str = "[]",
    language_level: str = "simplu",
) -> dict:
    """
    Post-process and persist the agent's response to Firebase.

    Call this AFTER generating a response to save conversation history
    and extract loopholes/quality metrics.

    Args:
        response_text: The raw LLM-generated answer.
        query: The original user question.
        session_id: Conversation ID.
        sources_json: JSON-encoded list of source dicts from retrieve_legal_context.
        language_level: Language level used.

    Returns:
        {
          response: str,         # Cleaned and formatted response
          loopholes: list[str],  # Extracted legal exceptions/opportunities
          sources: list[dict],
          quality_score: float,  # 0-1 heuristic score
          truncated: bool,
          processed_at: str,
        }
    """
    try:
        sources = json.loads(sources_json)
    except Exception:
        sources = []
    return _run(get_engine().process_agent_response(
        raw_response=response_text,
        query=query,
        session_id=session_id,
        sources=sources,
        language_level=language_level,
    ))


def get_rag_stats() -> dict:
    """
    Return diagnostics: ChromaDB chunk counts, cache usage, rate limiter status.
    Useful for monitoring and debugging the RAG pipeline.
    """
    return _run(get_engine().get_retrieval_stats())


# ══════════════════════════════════════════════════════════════════════════════
# 11. SELF-TEST
# ══════════════════════════════════════════════════════════════════════════════

async def _run_self_test():
    scenarios = [
        ("Ce este TVA-ul și cum se calculează?", "simplu"),
        ("Obligațiile fiscale ale unui SRL în 2024", "mediu"),
        ("Regimul fiscal al microîntreprinderilor", "simplu"),
        ("Excepții CAS pentru PFA cu venituri mici", "tehnic"),
        ("Termene depunere declarații ANAF trimestriale", "mediu"),
        ("Impozit pe dividende persoane fizice", "simplu"),
    ]

    engine = get_engine(RetrievalConfig(language_level="simplu", include_loopholes=True))
    stats = await engine.get_retrieval_stats()

    print("\n" + "═" * 70)
    print("  LegalSimplify — RAG Self-Test Suite")
    print("═" * 70)
    print(f"  VectorStore: {stats['vector_store']['total_chunks']} chunks")
    print(f"  Cache: {stats['memory_cache']['size']}/{stats['memory_cache']['max']} slots")
    print("═" * 70 + "\n")

    passed = 0
    for i, (query, level) in enumerate(scenarios):
        print(f"[{i+1}/{len(scenarios)}] [{level.upper():6}] {query[:58]}...")
        t0 = time.monotonic()
        try:
            result = await engine.retrieve_and_build_prompt(query=query, language_level=level)
            elapsed = time.monotonic() - t0
            chunks = result["context"]["chunk_count"]
            fallback = result["fallback"]
            status = "✅" if not fallback else "⚠️  FALLBACK (web search needed)"
            print(f"         {status} | {elapsed:.2f}s | {chunks} chunks | cache={'HIT' if result['cache_hit'] else 'MISS'}")
            if not fallback:
                passed += 1
        except Exception as e:
            print(f"         ❌ ERROR: {e}")

    print(f"\n  Result: {passed}/{len(scenarios)} with local context found")
    print("═" * 70 + "\n")


if __name__ == "__main__":
    asyncio.run(_run_self_test())
