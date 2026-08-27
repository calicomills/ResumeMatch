import pytest

from app.eval.fakes import FakeOllamaClient
from app.questions.generate import generate_questions
from app.scoring.match import Gap


@pytest.mark.asyncio
async def test_no_gaps_produces_no_questions():
    fake = FakeOllamaClient()
    assert await generate_questions(fake, []) == []


@pytest.mark.asyncio
async def test_llm_questions_used_when_well_formed():
    gaps = [Gap(kind="required_skill", label="kubernetes")]
    fake = FakeOllamaClient(questions_response=["Have you deployed anything on Kubernetes in production?"])
    result = await generate_questions(fake, gaps)
    assert len(result) == 1
    assert result[0].source == "llm"
    assert "Kubernetes" in result[0].question


@pytest.mark.asyncio
async def test_malformed_llm_response_falls_back_to_template():
    gaps = [Gap(kind="required_skill", label="kubernetes"), Gap(kind="experience", label="2 yrs vs 5 yrs")]
    # model only returned one question for two gaps, and it's too short to trust
    fake = FakeOllamaClient(questions_response=["ok"])
    result = await generate_questions(fake, gaps)
    assert len(result) == 2
    assert result[0].source == "fallback"
    assert "kubernetes" in result[0].question
    assert result[1].source == "fallback"


@pytest.mark.asyncio
async def test_gaps_are_prioritized_and_capped():
    gaps = [Gap(kind="nice_to_have_skill", label=f"skill{i}") for i in range(10)]
    gaps.append(Gap(kind="required_skill", label="python"))
    fake = FakeOllamaClient(questions_response=None)  # forces fallback for all
    result = await generate_questions(fake, gaps)
    assert len(result) <= 6
    assert result[0].gap_kind == "required_skill"  # required skill prioritized to the front
