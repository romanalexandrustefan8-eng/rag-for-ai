"""
agent.py — Google ADK Law Agent wired to retrieval.py RAG pipeline.
See retrieval.py for full retrieval engine documentation.
"""

from typing import Any, AsyncIterator

from google.adk.agents import llm_agent
from google.adk.sessions import vertex_ai_session_service
from google.adk.tools import agent_tool, FunctionTool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools import url_context
from vertexai.preview.reasoning_engines import AdkApp

from retrieval import (
    retrieve_legal_context,
    save_agent_response,
    get_rag_stats,
    get_engine,
    RetrievalConfig,
)

VertexAiSessionService = vertex_ai_session_service.VertexAiSessionService
_MODEL = "gemini-2.5-pro"

ROOT_INSTRUCTION = """
Ești LawAgent, un expert în legislație financiară și fiscală din România.

WORKFLOW OBLIGATORIU pentru fiecare întrebare:

PASUL 1 — RETRIEVAL (OBLIGATORIU ÎNTOTDEAUNA):
  Apelează retrieve_legal_context(
    query=<întrebarea utilizatorului>,
    session_id=<session_id din CONFIG>,
    language_level=<din CONFIG>,
    sources=<din CONFIG>,
    include_loopholes=<din CONFIG>
  )

PASUL 2 — VERIFICARE FALLBACK:
  Dacă retrieve_legal_context returnează fallback=True:
  → Apelează Law_Agent_google_search_agent pentru a căuta online
  → Dacă găsești URL-uri relevante (anaf.ro, monitoruloficial.ro):
    → Apelează Law_Agent_url_context_agent cu acele URL-uri

PASUL 3 — GENERARE RĂSPUNS:
  Folosește câmpul "prompt" returnat de retrieve_legal_context ca bază.
  Respectă nivelul de limbaj. Citează sursele. Identifică loophole-uri dacă cerut.

PASUL 4 — SALVARE (OBLIGATORIU):
  Apelează save_agent_response(
    response_text=<răspunsul generat>,
    query=<întrebarea originală>,
    session_id=<session_id>,
    sources_json=<json.dumps(sources din pasul 1)>,
    language_level=<nivelul folosit>
  )

REGULI STRICTE:
- Răspunde EXCLUSIV în română
- Nu inventa articole sau legi inexistente
- Recomandă specialist fiscal/juridic pentru cazuri specifice
- Semnalează dacă informația poate fi depășită
"""


class AgentClass:
    def __init__(self):
        self.app: AdkApp | None = None
        self._engine = get_engine(RetrievalConfig(
            language_level="simplu",
            include_loopholes=True,
            n_results=8,
            min_relevance=0.25,
            max_requests_per_minute=55,
        ))

    def session_service_builder(self):
        return VertexAiSessionService()

    def set_up(self):
        # Sub-agent: Google Search
        search_agent = llm_agent.LlmAgent(
            name="Law_Agent_google_search_agent",
            model=_MODEL,
            description=(
                "Performs real-time Google searches for Romanian fiscal legislation. "
                "Use when RAG fallback=True or user asks about very recent law changes."
            ),
            sub_agents=[],
            instruction=(
                "Caută pe Google legislație fiscală românească actuală. "
                "Prioritizează: anaf.ro, monitoruloficial.ro, legislatie.just.ro. "
                "Returnează URL-uri relevante. Răspunde în română."
            ),
            tools=[GoogleSearchTool()],
        )

        # Sub-agent: URL Context
        url_agent = llm_agent.LlmAgent(
            name="Law_Agent_url_context_agent",
            model=_MODEL,
            description=(
                "Reads full content of URLs from ANAF, Monitorul Oficial, "
                "or other official Romanian legal sources."
            ),
            sub_agents=[],
            instruction=(
                "Citește conținutul URL-urilor legislative românești furnizate. "
                "Extrage și structurează textul legal relevant. Răspunde în română."
            ),
            tools=[url_context],
        )

        # Root agent with RAG tools + sub-agents
        root_agent = llm_agent.LlmAgent(
            name="Law_Agent",
            model=_MODEL,
            description=(
                "Expert în legislație financiară și fiscală română. "
                "Simplifică limbajul juridic, identifică excepții fiscale, "
                "accesează RAG (ChromaDB + Firebase) cu date din Monitorul Oficial și ANAF."
            ),
            sub_agents=[search_agent, url_agent],
            instruction=ROOT_INSTRUCTION,
            tools=[
                FunctionTool(func=retrieve_legal_context),
                FunctionTool(func=save_agent_response),
                FunctionTool(func=get_rag_stats),
                agent_tool.AgentTool(agent=search_agent),
                agent_tool.AgentTool(agent=url_agent),
            ],
        )

        self.app = AdkApp(
            agent=root_agent,
            session_service_builder=self.session_service_builder,
        )

    async def stream_query(
        self,
        query: str,
        user_id: str = "default",
        session_id: str | None = None,
        language_level: str = "simplu",
        sources: list[str] | None = None,
        include_loopholes: bool = True,
    ) -> AsyncIterator[Any]:
        if self.app is None:
            raise RuntimeError("Call set_up() before querying.")
        src_str = ",".join(sources or ["monitorul_oficial", "anaf"])
        augmented = (
            f"{query}\n\n"
            f"[CONFIG: session_id={session_id or user_id}, "
            f"language_level={language_level}, "
            f"sources={src_str}, "
            f"include_loopholes={include_loopholes}]"
        )
        async for chunk in self.app.async_stream_query(message=augmented, user_id=user_id):
            yield chunk

    async def query(
        self,
        query: str,
        user_id: str = "default",
        session_id: str | None = None,
        language_level: str = "simplu",
        sources: list[str] | None = None,
        include_loopholes: bool = True,
    ) -> str:
        """Non-streaming — collects all chunks into a single string."""
        parts: list[str] = []
        async for chunk in self.stream_query(
            query=query, user_id=user_id, session_id=session_id,
            language_level=language_level, sources=sources,
            include_loopholes=include_loopholes,
        ):
            if hasattr(chunk, "text"):
                parts.append(chunk.text)
            elif isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, dict) and "text" in chunk:
                parts.append(chunk["text"])
        return "".join(parts)

    async def get_stats(self) -> dict:
        return await self._engine.get_retrieval_stats()


app = AgentClass()


