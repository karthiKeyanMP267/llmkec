
import logging

from fastmcp import FastMCP
from tools.document_retriver import query_rag

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

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
    logger.info("search_regulations called with query: %s", query)
    result = await query_rag(query)
    logger.info("search_regulations returning %d chars", len(result))
    return result

if __name__ == "__main__":
    logger.info("Starting regulations-rag MCP server on 127.0.0.1:3002")
    mcp.run(transport="http",host="127.0.0.1",port=3002)
