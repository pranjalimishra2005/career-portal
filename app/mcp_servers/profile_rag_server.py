import os
import sys

# Silence logs and progress bars to keep stdout clean for MCP JSON-RPC
os.environ["TQDM_DISABLE"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import json
from typing import Optional
from mcp.server.fastmcp import FastMCP

from app.db.retriever import query_profile
from app.db.vector_store import get_profile_collection

# Pre-warm Chroma collection & BGE-Small model on the main thread at boot
get_profile_collection()

# Initialize FastMCP Server
mcp = FastMCP("profile-rag-server")


@mcp.tool()
async def search_profile(query: str, top_k: int = 3, section: Optional[str] = None) -> str:
    """
    Semantically searches the candidate profile knowledge base.
    
    Args:
        query: What to search for (e.g. 'FastAPI experience', 'Docker projects')
        top_k: Number of relevant facts to retrieve (default: 3)
        section: Optional section filter ('experience', 'project', 'education', 'skill', 'faq')
    
    Returns:
        JSON string containing matching facts with chunk IDs and similarity scores.
    """
    results = query_profile(query_text=query, top_k=top_k, source_type=section)
    
    output = []
    for r in results:
        output.append({
            "chunk_id": r.chunk_id,
            "source_type": r.source_type,
            "similarity_score": r.similarity_score,
            "content": r.content,
            "metadata": r.metadata
        })
        
    return json.dumps(output, indent=2)


@mcp.tool()
async def get_faq_answer(question: str) -> str:
    """
    Retrieves candidate's verified answer to common ATS screening questions
    (e.g., work authorization, relocation, salary expectations).
    
    Args:
        question: The ATS form question
        
    Returns:
        The exact pre-approved factual answer, or a notice if no matching FAQ exists.
    """
    results = query_profile(query_text=question, top_k=1, source_type="faq")
    
    if not results or results[0].similarity_score < 0.65:
        return json.dumps({
            "found": False,
            "message": "No high-confidence pre-approved answer found for this question."
        })
        
    best = results[0]
    return json.dumps({
        "found": True,
        "chunk_id": best.chunk_id,
        "answer": best.content,
        "similarity_score": best.similarity_score
    }, indent=2)


if __name__ == "__main__":
    mcp.run()