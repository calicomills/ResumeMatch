from app.scoring.match import MatchWeights, compute_match
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


def test_default_weights_reproduce_original_fixed_weighting():
    # Locks in that MatchWeights() defaults behave exactly like the old hardcoded constants —
    # a caller that never touches weights (e.g. the single-candidate endpoint) must see no change.
    jd = JDRequirements(required_skills=["python", "docker"], min_years_experience=2, education="")
    resume = ResumeProfile(skills=["python"], years_experience=1, education="")
    assert compute_match(jd, resume).score == compute_match(jd, resume, weights=MatchWeights()).score


def test_weights_are_normalized_regardless_of_scale():
    jd = JDRequirements(required_skills=["python", "docker"], min_years_experience=0, education="")
    resume = ResumeProfile(skills=["python"], years_experience=0, education="")
    a = compute_match(jd, resume, weights=MatchWeights(required=55, nice_to_have=0, experience=0, education=0, companies=0))
    b = compute_match(jd, resume, weights=MatchWeights(required=1, nice_to_have=0, experience=0, education=0, companies=0))
    assert a.score == b.score == 50  # 1 of 2 required skills matched, weighted 100% on required


def test_weighting_toward_skills_vs_experience_changes_score():
    jd = JDRequirements(required_skills=["python", "docker", "kubernetes"], min_years_experience=10, education="")
    # Strong skills, weak experience.
    resume = ResumeProfile(skills=["python", "docker", "kubernetes"], years_experience=1, education="")

    skills_heavy = compute_match(
        jd, resume, weights=MatchWeights(required=90, nice_to_have=0, experience=10, education=0, companies=0)
    )
    experience_heavy = compute_match(
        jd, resume, weights=MatchWeights(required=10, nice_to_have=0, experience=90, education=0, companies=0)
    )
    assert skills_heavy.score > experience_heavy.score


def test_no_target_companies_is_neutral():
    jd = JDRequirements(required_skills=[], min_years_experience=0, education="")
    resume = ResumeProfile(skills=[], years_experience=0, education="", companies=["Acme Corp"])
    result = compute_match(jd, resume, weights=MatchWeights(companies=100), target_companies=None)
    assert result.score == 100
    assert result.companies_matched == []
    assert result.companies_missing == []


def test_target_company_match_and_miss():
    jd = JDRequirements(required_skills=[], min_years_experience=0, education="")
    resume = ResumeProfile(skills=[], years_experience=0, education="", companies=["Google", "Small Startup Inc"])
    result = compute_match(
        jd,
        resume,
        weights=MatchWeights(required=0, nice_to_have=0, experience=0, education=0, companies=100),
        target_companies=["Google", "Meta"],
    )
    assert result.companies_matched == ["Google"]
    assert result.companies_missing == ["Meta"]
    assert result.score == 50  # 1 of 2 target companies matched, weighted 100% on companies


def test_company_matching_tolerates_suffix_variation():
    jd = JDRequirements(required_skills=[], min_years_experience=0, education="")
    resume = ResumeProfile(skills=[], years_experience=0, education="", companies=["Google LLC"])
    result = compute_match(
        jd, resume, weights=MatchWeights(companies=100), target_companies=["Google"]
    )
    assert result.companies_matched == ["Google"]
