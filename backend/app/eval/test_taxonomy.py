from app.skills.taxonomy import is_generic_skill, is_technical_skill, normalize_skill, skills_equivalent


def test_known_alias_normalizes_to_canonical():
    assert normalize_skill("JS") == "javascript"
    assert normalize_skill("Postgres") == "postgresql"
    assert normalize_skill("k8s") == "kubernetes"


def test_case_and_whitespace_insensitive():
    assert normalize_skill("  Python3  ") == "python"


def test_unknown_skill_passes_through_lowercased():
    assert normalize_skill("Zephyr RTOS") == "zephyr rtos"


def test_skills_equivalent_across_aliases():
    assert skills_equivalent("JavaScript", "js") is True
    assert skills_equivalent("React.js", "react") is True
    assert skills_equivalent("Python", "Java") is False


def test_fuzzy_typo_tolerance():
    # small typo should still resolve to the canonical skill
    assert normalize_skill("Kubernets") == "kubernetes"


def test_generic_filler_skills_are_flagged():
    assert is_generic_skill("communication") is True
    assert is_generic_skill("Problem-Solving Skills") is True
    assert is_generic_skill("Problem Solving") is True
    assert is_generic_skill("excellent communication skills") is True
    assert is_generic_skill("teamwork") is True
    assert is_generic_skill("team player") is True


def test_real_skills_are_not_flagged_as_generic():
    assert is_generic_skill("python") is False
    assert is_generic_skill("kubernetes") is False
    assert is_generic_skill("sales") is False  # a real (if non-technical) skill, not filler


def test_technical_skills_are_flagged_technical():
    assert is_technical_skill("python") is True
    assert is_technical_skill("kubernetes") is True
    assert is_technical_skill("Zephyr RTOS") is True  # unknown skill defaults to technical


def test_business_skills_are_not_flagged_technical():
    assert is_technical_skill("sales") is False
    assert is_technical_skill("negotiation") is False
    assert is_technical_skill("leadership") is False


def test_generic_skills_are_not_flagged_technical_either():
    # already filtered out entirely upstream, but should never register as a "technical gap" if
    # one somehow slipped through
    assert is_technical_skill("communication") is False
