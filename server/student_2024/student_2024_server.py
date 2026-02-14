
from fastmcp import FastMCP
from tools.document_retriver import query_rag


mcp = FastMCP("regulations-rag")

@mcp.tool()
async def search_regulations(query: str) -> str:
    """
    This tool returns the FINAL answer.

    RULES:
    - The Regulations 2024 document IS available.
    - The returned text IS the final answer.
    - Do NOT apologize.
    - Do NOT mention configuration, API keys, or access issues.
    """
    return await query_rag(query)

if __name__ == "__main__":
    mcp.run(transport="http",host="127.0.0.1",port=3002)
