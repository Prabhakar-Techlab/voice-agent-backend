"""POST /api/v1 — accept a question/statement, return the best suggestion."""
import logging

import anthropic
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.suggest import get_suggestion

logger = logging.getLogger(__name__)
router = APIRouter()


class FinalContext(BaseModel):
    client_name: str | None = None
    sales_agent_name: str | None = None
    prompt_text: str | None = None


class SuggestRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Question or statement to get a suggestion for")
    final_context: FinalContext | None = Field(None, description="Optional conversation context")


class SuggestResponse(BaseModel):
    suggestion: str


@router.post("/api/v1/suggest_response", response_model=SuggestResponse)
async def suggest(body: SuggestRequest):
    """Return the best suggestion for the given question or statement."""
    try:
        suggestion = await get_suggestion(body.text, body.final_context)
        return SuggestResponse(suggestion=suggestion)
    except anthropic.AuthenticationError:
        raise HTTPException(status_code=500, detail="Claude API authentication failed — check ANTHROPIC_API_KEY")
    except anthropic.RateLimitError:
        raise HTTPException(status_code=429, detail="Claude API rate limit exceeded — please retry later")
    except anthropic.APIStatusError as exc:
        logger.exception("Claude API error: %s", exc)
        raise HTTPException(status_code=502, detail="Claude API error")
    except Exception as exc:
        logger.exception("Unexpected error in /api/v1: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error")
