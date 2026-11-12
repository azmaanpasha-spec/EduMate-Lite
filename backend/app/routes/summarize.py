from fastapi import APIRouter, Depends

from ..schemas import SummarizeRequest, SummarizeResponse
from ..services.ai_service import AIService, get_ai_service

router = APIRouter(prefix="/api/summarize", tags=["Summarizer"])

SUMMARY_SYSTEM_PROMPT = """You are EduMate, an academic assistant that summarizes study material for college students.
Only use information found in the provided text. Do not add outside facts.
Write in clear, simple language and format the summary in Markdown."""

def word_limit(original_words: int, length: str) -> int:
    """A summary must be shorter than the original: about 25% (short) or 50% (detailed)."""
    if length == "short":
        return max(30, min(150, original_words // 4))
    return max(60, min(600, original_words // 2))


def build_instructions(length: str, limit: int) -> str:
    if length == "short":
        return (
            f"Write a SHORT summary of at most {limit} words: 3 to 5 concise bullet points "
            "covering only the most important ideas. No introduction sentence."
        )
    return (
        f"Write a DETAILED summary of at most {limit} words: a 1-2 sentence overview, then short "
        "headings with bullet points for the key concepts, definitions and examples, and end with "
        "a brief 'Key Takeaways' list. Be concise: the summary must be much shorter than the original."
    )


@router.post("", response_model=SummarizeResponse)
def summarize(req: SummarizeRequest, ai: AIService = Depends(get_ai_service)):
    """Summarize study notes or any long text."""
    limit = word_limit(len(req.text.split()), req.length)
    prompt = f"{build_instructions(req.length, limit)}\n\nText to summarize:\n\"\"\"\n{req.text}\n\"\"\""
    summary = ai.generate(SUMMARY_SYSTEM_PROMPT, [{"role": "user", "content": prompt}], temperature=0.3)
    return SummarizeResponse(
        summary=summary,
        length=req.length,
        original_words=len(req.text.split()),
        summary_words=len(summary.split()),
    )
