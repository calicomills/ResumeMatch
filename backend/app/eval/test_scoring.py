from app.scoring.match import compute_match
from app.skills.extract import JDRequirements, ResumeProfile


def test_perfect_match_scores_100():
    jd = JDRequirements(
        required_skills=["python", "postgresql"],
        nice_to_have_skills=["kubernetes"],
        min_years_experience=3,
        education="Bachelor's in CS",
    )
    resume = ResumeProfile(
        skills=["python", "postgresql", "kubernetes"],
        years_experience=5,
        education="Bachelor's in Computer Science",
    )
    result = compute_match(jd, resume)
    assert result.score == 100
    assert result.required_missing == []
    assert result.gaps == []


def test_missing_required_skill_produces_gap_and_lowers_score():
    jd = JDRequirements(required_skills=["python", "kubernetes"], min_years_experience=0, education="")
    resume = ResumeProfile(skills=["python"], years_experience=0, education="")
    result = compute_match(jd, resume)
    assert result.score < 100
    assert "kubernetes" in result.required_missing
    assert any(g.kind == "required_skill" and g.label == "kubernetes" for g in result.gaps)


def test_experience_shortfall_is_a_gap():
    jd = JDRequirements(required_skills=[], min_years_experience=5, education="")
    resume = ResumeProfile(skills=[], years_experience=2, education="")
    result = compute_match(jd, resume)
    assert result.experience_ok is False
    assert any(g.kind == "experience" for g in result.gaps)


def test_no_jd_requirements_scores_full_marks():
    jd = JDRequirements(required_skills=[], nice_to_have_skills=[], min_years_experience=0, education="")
    resume = ResumeProfile(skills=[], years_experience=0, education="")
    result = compute_match(jd, resume)
    assert result.score == 100


def test_skill_aliases_count_as_matched():
    jd = JDRequirements(required_skills=["javascript"], min_years_experience=0, education="")
    resume = ResumeProfile(skills=["js"], years_experience=0, education="")
    result = compute_match(jd, resume)
    assert "javascript" in result.required_matched


def test_score_is_deterministic_across_runs():
    jd = JDRequirements(required_skills=["python", "docker"], min_years_experience=2, education="")
    resume = ResumeProfile(skills=["python"], years_experience=1, education="")
    scores = {compute_match(jd, resume).score for _ in range(5)}
    assert len(scores) == 1
