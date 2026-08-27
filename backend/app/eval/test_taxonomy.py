from app.skills.taxonomy import normalize_skill, skills_equivalent


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
