"""
FinSight LangChain agent.
Wires together the LLM, memory, system prompt, and all four tools.
"""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferWindowMemory
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agent.tools.tools import (
    SpendAnalyserTool,
    MoMCompareTool,
    AnomalyDetectorTool,
    BudgetPlannerTool,
)

SYSTEM_PROMPT = """
You are FinSight, a friendly and sharp personal finance advisor.
You have access to the user's actual transaction data via your tools.

Guidelines:
- Always use a tool before answering any question about spending, budgets, or anomalies.
  Never make up numbers — only quote figures returned by your tools.
- Be concise but warm. Lead with the most important insight, then the detail.
- Format currency as ₹ with commas (e.g. ₹12,400).
- When you detect a problem (overspending, anomaly), always suggest one concrete action.
- If the user uploads new data, acknowledge it and offer to run a summary.
- If a question is outside finance (e.g. general chat), answer briefly and redirect.

Today's date: {today}
"""


def build_agent(session_id: str, db) -> AgentExecutor:
    from datetime import date

    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.2)

    tools = [
        SpendAnalyserTool(session_id=session_id, db=db),
        MoMCompareTool(session_id=session_id, db=db),
        AnomalyDetectorTool(session_id=session_id, db=db),
        BudgetPlannerTool(session_id=session_id, db=db),
    ]

    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT.format(today=date.today().isoformat())),
        MessagesPlaceholder("chat_history", optional=True),
        ("human", "{input}"),
        MessagesPlaceholder("agent_scratchpad"),
    ])

    memory = ConversationBufferWindowMemory(
        memory_key="chat_history",
        return_messages=True,
        k=10,                       # keep last 10 turns
    )

    agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)

    return AgentExecutor(
        agent=agent,
        tools=tools,
        memory=memory,
        verbose=True,               # set False in production
        max_iterations=5,
        handle_parsing_errors=True,
    )
