"""LLM-as-judge with an explicit 0-3 rubric. Complements the deterministic checks: it grades what
string matching cannot (unsupported claims, completeness, tone)."""

import json

from pydantic import BaseModel, Field

from casavaiano.agent import prompts
from casavaiano.agent.state import AssistantResponse
from casavaiano.evals.dataset import EvalCase
from casavaiano.llm import LLMClient, LLMRequest, LLMResult


class JudgeVerdict(BaseModel):
    faithfulness: int = Field(description="0-3, see rubric")
    correctness: int = Field(description="0-3, see rubric")
    language_and_tone: int = Field(description="0-3, see rubric")
    asks_for_missing_info: bool = Field(description="The reply asks the guest for missing details")
    unsupported_claims: list[str] = Field(description="Claims not backed by SOURCES, verbatim")
    reasoning: str = Field(description="At most 3 sentences")

    @property
    def passed(self) -> bool:
        return self.faithfulness >= 2 and self.correctness >= 2 and self.language_and_tone >= 2


ANSWER_RUBRIC = """\
You grade a reply written by the guest assistant of CasaVaiano, an agriturismo in Tuscany.
SOURCES are everything the assistant was allowed to use: knowledge base excerpts and tool
results. EXPECTED describes what a good reply must convey; it was written by the developer.

faithfulness - are factual claims (prices, times, policies, availability, services, distances,
durations) supported by SOURCES?
  3: every factual claim is supported
  2: one minor unsupported detail that would not mislead the guest (e.g. a generic pleasantry)
  1: an unsupported claim the guest could act on (a time, a rule, a service, a duration)
  0: an invented price or policy, or a claim that contradicts SOURCES

correctness - does the reply do what EXPECTED describes?
  3: fully, every question in the message is addressed
  2: the main question is answered correctly, a minor point is missing
  1: partially wrong, or the main point is missing
  0: wrong or unhelpful

language_and_tone - is it written in the guest's language, polite and professional, suitable
for a family hotel replying by email, and reasonably concise?
  3: yes
  2: right language, minor issues (too informal, too long, awkward greeting)
  1: noticeable issues
  0: wrong language

List every unsupported claim verbatim in unsupported_claims. Be strict and literal: a claim is
supported only if SOURCES state it. Do not reward length."""

ESCALATION_RUBRIC = """\
The guest message below was escalated to Giulia, the owner of CasaVaiano. The assistant wrote
an OWNER SUMMARY and a DRAFT REPLY for Giulia to edit and send. SOURCES are the knowledge base
excerpts it could use.

faithfulness - the draft promises nothing that is not in SOURCES (no refunds, discounts,
dates, prices or exceptions) and states no unsupported facts.
  3: fully faithful   2: a minor unsupported detail   1: a misleading claim   0: a promise or
  invented policy

correctness - the summary correctly says who wants what and why it needs Giulia, and the draft
acknowledges the request appropriately.
  3: accurate and useful   2: minor gaps   1: misses the point   0: wrong

language_and_tone - the draft is in the guest's language, polite and professional.
  3: yes   2: minor issues   1: noticeable issues   0: wrong language

List unsupported claims of the draft verbatim. Be strict and literal."""


def judge_response(
    llm: LLMClient,
    model: str,
    case: EvalCase,
    response: AssistantResponse,
    source_texts: list[str],
) -> tuple[JudgeVerdict, LLMResult]:
    tool_results = [{"tool": t.name, "input": t.input, "output": t.output} for t in response.tools]
    sources = "\n\n".join(source_texts) or "(none)"
    if tool_results:
        sources += "\n\nTOOL RESULTS:\n" + json.dumps(tool_results, ensure_ascii=False, indent=1)
    if response.status == "escalated" and response.escalation:
        rubric, operator = ESCALATION_RUBRIC, prompts.ESCALATE_SYSTEM
        graded = (
            f"OWNER SUMMARY:\n{response.escalation.owner_summary}\n\n"
            f"DRAFT REPLY:\n{response.escalation.draft_reply}"
        )
    else:
        rubric, operator = ANSWER_RUBRIC, prompts.ANSWER_SYSTEM
        graded = f"REPLY:\n{response.reply}"
    user = (
        f"Today: {case.today.isoformat()}\nGuest language: {case.language}\n\n"
        f"GUEST MESSAGE:\n{case.message}\n\nEXPECTED:\n{case.expected}\n\n"
        f"OPERATOR INSTRUCTIONS (the assistant's instructions; business facts stated here, "
        f"such as who Giulia is and how bookings are confirmed, count as SOURCES):\n"
        f"{operator}\n\nSOURCES:\n{sources}\n\n{graded}"
    )
    result = llm.complete(
        LLMRequest(
            model=model,
            system=rubric,
            messages=[{"role": "user", "content": user}],
            max_tokens=4096,
            effort="medium",
            output_schema=JudgeVerdict,
            name="judge",
        )
    )
    return result.parsed, result
