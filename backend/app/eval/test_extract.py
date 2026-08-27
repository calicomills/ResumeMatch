import pytest

from app.eval.fakes import FakeOllamaClient
from app.skills.extract import extract_jd_requirements, extract_resume_profile


@pytest.mark.asyncio
async def test_extract_jd_requirements_happy_path():
    fake = FakeOllamaClient(
        jd_response={
            "required_skills": ["Python", "JS"],
            "nice_to_have_skills": ["Kubernetes"],
            "min_years_experience": 3,
            "education": "Bachelor's in CS",
        }
    )
    result = await extract_jd_requirements(fake, "some JD text")
    # aliases get normalized during extraction
    assert result.required_skills == ["python", "javascript"]
    assert result.nice_to_have_skills == ["kubernetes"]
    assert result.min_years_experience == 3
    assert result.education == "Bachelor's in CS"


@pytest.mark.asyncio
async def test_extract_jd_requirements_malformed_response_falls_back_to_defaults():
    # model returned a list instead of an object entirely
    fake = FakeOllamaClient(jd_response=["not", "a", "dict"])
    result = await extract_jd_requirements(fake, "some JD text")
    assert result.required_skills == []
    assert result.min_years_experience == 0


@pytest.mark.asyncio
async def test_extract_jd_requirements_clamps_wild_years_value():
    fake = FakeOllamaClient(jd_response={"min_years_experience": "a lot, like 500"})
    result = await extract_jd_requirements(fake, "some JD text")
    assert result.min_years_experience == 0  # non-numeric -> default, not a crash


@pytest.mark.asyncio
async def test_extract_resume_profile_happy_path():
    fake = FakeOllamaClient(
        resume_response={
            "skills": ["Postgres", "Docker"],
            "years_experience": 4,
            "education": "B.S. Computer Science",
            "highlights": ["Shipped a thing", "Led a team"],
        }
    )
    result = await extract_resume_profile(fake, "some resume text")
    assert result.skills == ["postgresql", "docker"]
    assert result.years_experience == 4
    assert len(result.highlights) == 2


@pytest.mark.asyncio
async def test_extract_resume_profile_caps_out_of_range_experience():
    fake = FakeOllamaClient(resume_response={"years_experience": 999})
    result = await extract_resume_profile(fake, "some resume text")
    assert result.years_experience <= 60


@pytest.mark.asyncio
async def test_filler_tokens_are_dropped_not_treated_as_skills():
    # small models sometimes emit ["none"] instead of [] when there's nothing to report
    fake = FakeOllamaClient(jd_response={"nice_to_have_skills": ["none"], "required_skills": ["Python"]})
    result = await extract_jd_requirements(fake, "some JD text")
    assert result.nice_to_have_skills == []
    assert result.required_skills == ["python"]
