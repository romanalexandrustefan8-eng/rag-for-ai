from typing import Any
from google.adk.agents import llm_agent
from google.adk.sessions import vertex_ai_session_service
from vertexai.preview.reasoning_engines import AdkApp
from google.adk.tools import agent_tool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools import url_context
import chromadb


import chromadb

client = chromadb.CloudClient(
  cloud_port=443,
  cloud_host='europe-west1.gcp.trychroma.com',
  api_key='YOUR_API_KEY',
  tenant='f1032ecf-7290-412c-9e06-ba50fa9f082f',
  database='Law-database'
)
# --- 1. THE RAG TOOL (from retrieval.py logic) ---
def law_retrieval_tool(query: str) -> str:
    """
    Searches the internal legal database for Romanian laws, ANAF policies, 
    and Monitorul Oficial documents. Use this FIRST for official records.
    
    Args:
        query: The legal term or specific policy to look up in the RAG model.
    """
    # REPLACE THIS LINE with your actual RAG/Vector DB search logic
    return f"[RAG DATA]: Found official documentation regarding: {query}"

VertexAiSessionService = vertex_ai_session_service.VertexAiSessionService

# --- 2. THE MAIN AGENT CLASS ---
class AgentClass:
    def __init__(self):
        self.app = None

    def session_service_builder(self):
        return VertexAiSessionService()

    def set_up(self):
        """Sets up the ADK application with specialized agents."""
        
        # Google Search Agent
        law_agent_google_search_agent = llm_agent.LlmAgent(
            name='Law_Agent_google_search_agent',
            model='gemini-2.5-pro',
            description='Agent specialized in performing Google searches.',
            instruction='Use the GoogleSearchTool to find information on the web.',
            tools=[GoogleSearchTool()],
        )

        # URL Content Fetcher Agent
        law_agent_url_context_agent = llm_agent.LlmAgent(
            name='Law_Agent_url_context_agent',
            model='gemini-2.5-pro',
            description='Agent specialized in fetching content from URLs.',
            instruction='Use the UrlContextTool to retrieve content from provided URLs.',
            tools=[url_context],
        )

        # Main Expert Agent (The Brain)
        root_agent = llm_agent.LlmAgent(
            name='Law_Agent',
            model='gemini-2.5-pro',
            description='Expert at reading and understanding Romanian law language.',
            instruction=(
                'Your purpose is to take complicated financial language and transform it into '
                'easy-to-understand language. ALWAYS check law_retrieval_tool FIRST for '
                'internal RAG database records. If information is missing, use sub-agents '
                'to check ANAF and Monitorul Oficial via Google Search or URL fetching. '
                'Identify potential loopholes in new fiscal policies.'
            ),
            tools=[
                law_retrieval_tool,  # Connected RAG logic
                agent_tool.AgentTool(agent=law_agent_google_search_agent),
                agent_tool.AgentTool(agent=law_agent_url_context_agent)
            ],
        )

        self.app = AdkApp(
            agent=root_agent,
            session_service_builder=self.session_service_builder
        )

    async def stream_query(self, query: str, user_id: str = 'test') -> Any:
        """Executes the streaming query."""
        async for chunk in self.app.async_stream_query(
            message=query,
            user_id=user_id,
        ):
            yield chunk

# --- 3. INITIALIZATION ---
app_instance = AgentClass()
app_instance.set_up()



