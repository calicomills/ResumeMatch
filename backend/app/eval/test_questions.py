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


@pytest.mark.asyncio
async def test_technical_skill_gaps_are_preferred_over_non_technical():
    # A non-technical required skill (e.g. "sales") outranks a technical nice-to-have by the old
    # kind-only ordering, but should now lose to it: technical gaps are preferred first.
    gaps = [
        Gap(kind="required_skill", label="sales"),
        Gap(kind="nice_to_have_skill", label="kubernetes"),
        Gap(kind="required_skill", label="python"),
    ]
    fake = FakeOllamaClient(questions_response=None)
    result = await generate_questions(fake, gaps)
    labels_in_order = [r.gap_label for r in result]
    assert labels_in_order.index("python") < labels_in_order.index("sales")
    assert labels_in_order.index("kubernetes") < labels_in_order.index("sales")


@pytest.mark.asyncio
async def test_technical_required_skill_beats_experience_and_education_gaps():
    gaps = [
        Gap(kind="experience", label="3 yrs vs 5 yrs"),
        Gap(kind="education", label="JD wants: Bachelor's in CS"),
        Gap(kind="required_skill", label="docker"),
    ]
    fake = FakeOllamaClient(questions_response=None)
    result = await generate_questions(fake, gaps)
    assert result[0].gap_label == "docker"


@pytest.mark.asyncio
async def test_leaked_internal_tag_is_rejected_not_shown_to_recruiter():
    # Reproduces a real bug: a small model echoed the internal gap-kind marker back verbatim
    # ("What experience do you have with [nice_to_have_skill] hadoop?") instead of writing prose.
    gaps = [Gap(kind="nice_to_have_skill", label="hadoop")]
    fake = FakeOllamaClient(
        questions_response=["What experience do you have with [nice_to_have_skill] hadoop?"]
    )
    result = await generate_questions(fake, gaps)
    assert len(result) == 1
    assert result[0].source == "fallback"
    assert "[nice_to_have_skill]" not in result[0].question
    assert "hadoop" in result[0].question


@pytest.mark.asyncio
async def test_leaked_tag_check_is_case_insensitive_and_tolerates_spacing():
    gaps = [Gap(kind="required_skill", label="python")]
    fake = FakeOllamaClient(questions_response=["Tell me about your [ Required_Skill ] experience."])
    result = await generate_questions(fake, gaps)
    assert result[0].source == "fallback"


@pytest.mark.asyncio
async def test_prompt_sent_to_model_never_contains_bracket_tags():
    # The root-cause fix: the prompt itself shouldn't hand the model something bracket-shaped to
    # copy in the first place.
    captured = {}

    class CapturingClient:
        async def generate_json(self, prompt, system, default):
            captured["prompt"] = prompt
            return default

        async def generate(self, prompt, system=None):
            return ""

    gaps = [Gap(kind="nice_to_have_skill", label="hadoop"), Gap(kind="required_skill", label="python")]
    await generate_questions(CapturingClient(), gaps)
    assert "[nice_to_have_skill]" not in captured["prompt"]
    assert "[required_skill]" not in captured["prompt"]
    assert "missing nice-to-have skill: hadoop" in captured["prompt"]
