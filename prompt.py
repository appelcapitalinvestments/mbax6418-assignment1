"""
MBAX 6418 — Assignment 1, Step 1
The classification prompt and the structured-output schema.

Design follows two things Dobolyi taught directly:

  Week 3, slide 19 — the worked classification prompt from his own research
  (Dobolyi, Tamburrino, Borden & Faruque 2026). Its moves are reused here:
  a defined role, an explicit definition with stated exclusions, "###" section
  separators, a fixed response scale, a scripted insertion point for the data,
  and an all-caps format lock at the end.

  Week 3, slide 22 — structured outputs. His words: "Prompting a model to
  answer a specific way or to use a specific scale does not guarantee
  adherence. If adherence is key (e.g., classification tasks, downstream use),
  consider structured outputs, which dictate exactly how a model must respond."
  So the prompt asks for JSON and a Pydantic model validates what comes back.

The six-part framework from Lee & Palmer (2025, p. 14), which he showed twice,
maps onto the prompt below: role, background, objectives, parameters,
precision, format.
"""

from typing import Literal

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Structured output schema
# --------------------------------------------------------------------------

class ReviewAnalysis(BaseModel):
    """One classified review.

    Step 5 extends this with a `primary_emotion` field.
    Step 6 widens `sentiment` to include NEUTRAL.
    Keeping the shape small now makes both edits one-liners later.
    """

    sentiment: Literal["POSITIVE", "NEGATIVE"]
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Model's own stated confidence, 0.0 to 1.0.",
    )


# --------------------------------------------------------------------------
# The prompt
# --------------------------------------------------------------------------

# This block is byte-identical on every call. Only the review changes, which
# lets the server's prefix cache do its job — port 9000 reports `cached_tokens`,
# so after the first call the instructions are not re-processed. That is
# Week 2, slide 12 (prompt/prefix caching) applied to a 150-call run.

SYSTEM_PROMPT = """You are an expert annotator of e-commerce product reviews. Please follow all the instructions very carefully.

### Consider the following definition of review sentiment:
- POSITIVE means the reviewer is, on balance, satisfied with the product or the purchase experience.
- NEGATIVE means the reviewer is, on balance, dissatisfied with the product or the purchase experience.
- Judge the reviewer's attitude toward the product or purchase, not the quality of their writing.
- If the title and the body disagree, weight the body, because it carries the reasoning.
- A terse review is still classifiable. Brevity is not neutrality.
- An angry or profane review is NEGATIVE even when it gives no specific reason.
- A review describing a problem that was resolved to the reviewer's satisfaction is POSITIVE.
- You will not be shown a star rating. Do not speculate about one, and do not mention ratings in your answer.

### Task Overview
You will be given the title and body of a single Amazon review. You will determine whether its sentiment is POSITIVE or NEGATIVE, and state how confident you are.

### You will respond using this exact JSON structure and nothing else:
{"sentiment": "POSITIVE", "confidence": 0.0}

- `sentiment` must be exactly the string POSITIVE or the string NEGATIVE.
- `confidence` must be a number between 0.0 and 1.0 reflecting your certainty.

### Your Task
Answer immediately with the JSON object and nothing else.
YOUR RESPONSE MUST BE VALID JSON MATCHING THE STRUCTURE ABOVE EXACTLY, WITHOUT ALTERATIONS, WITHOUT MARKDOWN CODE FENCES, AND WITHOUT ANY SURROUNDING TEXT.
What is the sentiment of the review below?"""


def build_messages(title: str, text: str) -> list[dict]:
    """Assemble the two-message payload for one review.

    The system message never varies. The user message carries only the review,
    which is what makes the shared prefix cacheable across the whole run.
    """
    title = (title or "").strip()
    text = (text or "").strip()
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"# Title:\n{title}\n\n# Text:\n{text}"},
    ]


# --------------------------------------------------------------------------
# Ground truth
# --------------------------------------------------------------------------

def rating_to_label(rating: float) -> Literal["POSITIVE", "NEGATIVE"]:
    """The correct answer, derived from the star rating.

    Assignment spec, Step 2: ">=4 positive, else negative". The model never
    sees this. It exists only to score against afterwards.
    """
    return "POSITIVE" if float(rating) >= 4 else "NEGATIVE"
