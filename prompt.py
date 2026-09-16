"""
MBAX 6418 - Assignment 1
The classification prompt and the structured-output schema.

Covers Step 1 (binary sentiment), Step 5 (LLM-predicted emotion) and Step 6
(three-class sentiment). Steps 5 and 6 were implemented together rather than
one after the other, because both change the shape of the model's output and
doing them in one pass avoided building the dashboard twice. The Step 2 binary
run is preserved in results/ as evidence of the earlier stage.

Design follows two things Dobolyi taught directly:

  Week 3, slide 19 - the worked classification prompt from his own research
  (Dobolyi, Tamburrino, Borden & Faruque 2026). Its moves are reused here:
  a defined role, an explicit definition with stated exclusions, "###" section
  separators, a fixed response scale, a scripted insertion point for the data,
  and an all-caps format lock at the end.

  Week 3, slide 22 - structured outputs. His words: "Prompting a model to
  answer a specific way or to use a specific scale does not guarantee
  adherence. If adherence is key (e.g., classification tasks, downstream use),
  consider structured outputs, which dictate exactly how a model must respond."

The six-part framework from Lee & Palmer (2025, p. 14), which he showed twice,
maps onto the prompt below: role, background, objectives, parameters,
precision, format.
"""

from typing import Literal

from pydantic import BaseModel, Field

from emotion import EMOTIONS

Sentiment3 = Literal["POSITIVE", "NEUTRAL", "NEGATIVE"]
Sentiment2 = Literal["POSITIVE", "NEGATIVE"]


# --------------------------------------------------------------------------
# Structured output schema
# --------------------------------------------------------------------------

class ReviewAnalysis(BaseModel):
    """One classified review: three-class sentiment plus a primary emotion."""

    sentiment: Sentiment3
    primary_emotion: Literal[EMOTIONS]  # type: ignore[valid-type]
    confidence: float = Field(ge=0.0, le=1.0)


class ReviewAnalysisBinary(BaseModel):
    """Step 1 and 2 shape, kept so the earlier saved run stays reproducible."""

    sentiment: Sentiment2
    confidence: float = Field(ge=0.0, le=1.0)


# --------------------------------------------------------------------------
# The prompt
# --------------------------------------------------------------------------

# This block is byte-identical on every call. Only the review changes, which
# lets the server's prefix cache do its job - port 9000 reports `cached_tokens`,
# so after the first call the instructions are not re-processed. That is
# Week 2, slide 12 (prompt/prefix caching) applied to a 150-call run.

_EMOTION_LIST = ", ".join(EMOTIONS)

SYSTEM_PROMPT = f"""You are an expert annotator of e-commerce product reviews. Please follow all the instructions very carefully.

### Consider the following definition of review sentiment:
- POSITIVE means the reviewer is, on balance, satisfied with the product or the purchase experience.
- NEUTRAL means the reviewer is genuinely mixed or lukewarm: satisfied in some respects and dissatisfied in others, or reporting the product worked while expressing reservation. NEUTRAL is a real answer, not a fallback for uncertainty.
- NEGATIVE means the reviewer is, on balance, dissatisfied with the product or the purchase experience.
- Judge the reviewer's attitude toward the product or purchase, not the quality of their writing.
- If the title and the body disagree, weight the body, because it carries the reasoning.
- A terse review is still classifiable. Brevity is not neutrality.
- An angry or profane review is NEGATIVE even when it gives no specific reason.
- A review describing a problem that was resolved to the reviewer's satisfaction is POSITIVE.
- A review that praises the product but registers one clear complaint is NEUTRAL, not POSITIVE.
- You will not be shown a star rating. Do not speculate about one, and do not mention ratings in your answer.

### Also determine the reviewer's primary emotion:
Choose exactly one from this list: {_EMOTION_LIST}.
Pick the single emotion that best characterises the reviewer's feeling. If the review is flat or purely transactional, choose the closest fit rather than refusing.

### Task Overview
You will be given the title and body of a single Amazon review. You will determine its sentiment, its primary emotion, and how confident you are.

### You will respond using this exact JSON structure and nothing else:
{{"sentiment": "POSITIVE", "primary_emotion": "joy", "confidence": 0.0}}

- `sentiment` must be exactly POSITIVE, NEUTRAL, or NEGATIVE.
- `primary_emotion` must be exactly one of: {_EMOTION_LIST}.
- `confidence` must be a number between 0.0 and 1.0 reflecting your certainty.

### Your Task
Answer immediately with the JSON object and nothing else.
YOUR RESPONSE MUST BE VALID JSON MATCHING THE STRUCTURE ABOVE EXACTLY, WITHOUT ALTERATIONS, WITHOUT MARKDOWN CODE FENCES, AND WITHOUT ANY SURROUNDING TEXT.
What is the sentiment and primary emotion of the review below?"""


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

def rating_to_label(rating: float) -> Sentiment3:
    """Three-class ground truth, per the Step 6 table.

        4-5  POSITIVE
        3    NEUTRAL
        1-2  NEGATIVE

    The model never sees this. It exists only to score against afterwards.
    """
    r = float(rating)
    if r >= 4:
        return "POSITIVE"
    if r == 3:
        return "NEUTRAL"
    return "NEGATIVE"


def rating_to_label_binary(rating: float) -> Sentiment2:
    """Step 2's rule, kept so the earlier run stays reproducible.

    Note what this does to 3-star reviews: it forces them into NEGATIVE. The
    Step 2 run produced direct evidence that this is wrong - a 3-star review
    reading "Very easy to use. I wish I knew about it earlier" was scored as a
    model error when the model called it POSITIVE.
    """
    return "POSITIVE" if float(rating) >= 4 else "NEGATIVE"
