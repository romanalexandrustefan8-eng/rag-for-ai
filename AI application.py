from typing import Any

from google.adk.agents import llm_agent
from google.adk.sessions import vertex_ai_session_service
from vertexai.preview.reasoning_engines import AdkApp
from google.adk.tools import agent_tool
from google.adk.tools.google_search_tool import GoogleSearchTool
from google.adk.tools import url_context



VertexAiSessionService = vertex_ai_session_service.VertexAiSessionService


class AgentClass:

  def __init__(self):
    self.app = None

  def session_service_builder(self):
    return VertexAiSessionService()

  def set_up(self):
    """Sets up the ADK application."""
    law_agent_google_search_agent = llm_agent.LlmAgent(
      name='Law_Agent_google_search_agent',
      model='gemini-2.5-pro',
      description=(
          'Agent specialized in performing Google searches.'
      ),
      sub_agents=[],
      instruction='Use the GoogleSearchTool to find information on the web.',
      tools=[
        GoogleSearchTool()
      ],
    )
    law_agent_url_context_agent = llm_agent.LlmAgent(
      name='Law_Agent_url_context_agent',
      model='gemini-2.5-pro',
      description=(
          'Agent specialized in fetching content from URLs.'
      ),
      sub_agents=[],
      instruction='Use the UrlContextTool to retrieve content from provided URLs.',
      tools=[
        url_context
      ],
    )
    root_agent = llm_agent.LlmAgent(
      name='Law_Agent',
      model='gemini-2.5-pro',
      description=(
          'you are an expert at reading and understanding law language'
      ),
      sub_agents=[],
      instruction='Your purpose is to take the complicated financial language from the RAG model and the database and transform it into easy-to-understand language for the laws while also showing potential loopholes, you will check the new laws from ANAF and Monitorul Oficial and take all the new fiscal policies there and translate them',
      tools=[
        agent_tool.AgentTool(agent=law_agent_google_search_agent),
        agent_tool.AgentTool(agent=law_agent_url_context_agent)
      ],
    )

    self.app = AdkApp(
        agent=root_agent,
        session_service_builder=self.session_service_builder
    )

  async def stream_query(self, query: str, user_id: str = 'test') -> Any:
    """Streaming query."""
    async for chunk in self.app.async_stream_query(
        message=query,
        user_id=user_id,
    ):
      yield chunk


app = AgentClass()
