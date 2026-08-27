"""A curated skill dictionary with synonyms, and normalization helpers.

This is the "don't ask the model things you already know" piece: whether "JS" and "JavaScript"
are the same skill is a lookup, not a judgment call worth spending model tokens on. The LLM only
ever sees this taxonomy indirectly (as normalized strings); it never has to reconcile aliases.
"""

from __future__ import annotations

from rapidfuzz import fuzz, process

# canonical skill -> synonyms/aliases (lowercase). Deliberately broad across engineering, data,
# product/design, and general business roles since recruiters use this tool beyond just SWE reqs.
SKILL_SYNONYMS: dict[str, list[str]] = {
    # Languages
    "javascript": ["js", "java script", "ecmascript"],
    "typescript": ["ts"],
    "python": ["python3", "py"],
    "java": [],
    "c++": ["cpp", "c plus plus"],
    "c#": ["csharp", "c sharp", ".net c#"],
    "go": ["golang"],
    "rust": [],
    "ruby": [],
    "php": [],
    "swift": [],
    "kotlin": [],
    "scala": [],
    "r": ["r language", "r programming"],
    "sql": ["structured query language"],
    "bash": ["shell scripting", "shell"],
    # Frontend
    "react": ["react.js", "reactjs"],
    "vue": ["vue.js", "vuejs"],
    "angular": ["angularjs"],
    "next.js": ["nextjs"],
    "html": ["html5"],
    "css": ["css3"],
    "tailwind css": ["tailwind", "tailwindcss"],
    # Backend / frameworks
    "node.js": ["nodejs", "node"],
    "express": ["express.js", "expressjs"],
    "django": [],
    "flask": [],
    "fastapi": [],
    "spring": ["spring boot", "springboot"],
    "ruby on rails": ["rails"],
    "graphql": [],
    "rest api": ["rest", "restful api", "restful", "api design"],
    "grpc": [],
    # Data / ML
    "machine learning": ["ml"],
    "deep learning": ["dl"],
    "natural language processing": ["nlp"],
    "computer vision": ["cv"],
    "pytorch": ["torch"],
    "tensorflow": ["tf"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "pandas": [],
    "numpy": [],
    "spark": ["apache spark", "pyspark"],
    "hadoop": [],
    "airflow": ["apache airflow"],
    "data engineering": [],
    "data analysis": ["data analytics"],
    "etl": ["extract transform load"],
    "llm": ["large language model", "large language models", "genai", "generative ai"],
    "prompt engineering": [],
    "a/b testing": ["ab testing", "experimentation"],
    "statistics": ["statistical analysis"],
    # Databases
    "postgresql": ["postgres"],
    "mysql": [],
    "mongodb": ["mongo"],
    "redis": [],
    "elasticsearch": ["elastic search"],
    "dynamodb": [],
    "sqlite": [],
    "cassandra": [],
    # Cloud / DevOps
    "aws": ["amazon web services"],
    "gcp": ["google cloud platform", "google cloud"],
    "azure": ["microsoft azure"],
    "docker": ["containerization"],
    "kubernetes": ["k8s"],
    "terraform": ["iac", "infrastructure as code"],
    "ci/cd": ["cicd", "continuous integration", "continuous deployment"],
    "jenkins": [],
    "github actions": [],
    "linux": ["unix"],
    "nginx": [],
    "microservices": ["microservice architecture"],
    "system design": ["distributed systems"],
    "monitoring": ["observability"],
    # Mobile
    "ios development": ["ios", "swiftui"],
    "android development": ["android"],
    "react native": [],
    "flutter": [],
    # QA / general engineering
    "unit testing": ["test driven development", "tdd"],
    "agile": ["scrum", "kanban"],
    "git": ["version control", "github", "gitlab"],
    "code review": [],
    "debugging": [],
    "performance optimization": [],
    "security": ["application security", "appsec"],
    # Product / Design
    "product management": ["product manager"],
    "product strategy": ["roadmapping", "roadmap planning"],
    "user research": ["ux research"],
    "wireframing": [],
    "figma": [],
    "sketch": [],
    "ui/ux design": ["ux design", "ui design", "user experience design"],
    "user experience": ["ux"],
    "prototyping": [],
    "design systems": [],
    # Data tools / BI
    "excel": ["microsoft excel"],
    "tableau": [],
    "power bi": ["powerbi"],
    "looker": [],
    # Business / soft skills
    "project management": ["pmp"],
    "stakeholder management": [],
    "communication": [
        "verbal communication", "written communication", "strong communication",
        "excellent communication", "communication skills",
    ],
    "leadership": ["team leadership"],
    "cross-functional collaboration": ["cross functional collaboration"],
    "negotiation": [],
    "public speaking": ["presentation skills"],
    "problem solving": [
        "analytical thinking", "analytical skills", "problem-solving skills",
        "critical thinking", "critical thinking skills",
    ],
    "mentoring": ["coaching"],
    "teamwork": ["team player", "team work", "collaboration", "collaborative"],
    "time management": [],
    "attention to detail": ["detail oriented", "detail-oriented"],
    "adaptability": ["flexibility", "adaptable"],
    "interpersonal skills": ["interpersonal"],
    "work ethic": ["strong work ethic"],
    "multitasking": [],
    "organizational skills": ["organization skills", "organized"],
    "creativity": ["creative thinking", "creative"],
    "self-motivated": ["self starter", "self-starter", "proactive"],
    "customer success": [],
    "sales": ["b2b sales", "b2c sales"],
    "crm": ["salesforce", "hubspot"],
    "marketing": ["digital marketing"],
    "seo": ["search engine optimization"],
    "content strategy": ["content marketing"],
    "financial modeling": [],
    "accounting": [],
}

# Canonical skills that are near-universal resume/JD filler — every posting claims them, so a
# "match" or "gap" on one carries no real signal, and a generated interview question about them
# ("tell me about your communication skills") isn't a useful use of a recruiter's time either.
# Filtered out entirely wherever skills get normalized (skills/extract.py) — never reaches
# scoring or question generation — rather than filtered per-caller, so there's exactly one place
# this list needs updating.
GENERIC_SKILLS: frozenset[str] = frozenset(
    {
        "communication",
        "problem solving",
        "teamwork",
        "time management",
        "attention to detail",
        "adaptability",
        "interpersonal skills",
        "work ethic",
        "multitasking",
        "organizational skills",
        "creativity",
        "self-motivated",
    }
)


def is_generic_skill(skill: str) -> bool:
    """True for filler skills like "communication" or "problem solving" that add no matching
    signal. Checks the normalized form, so phrasing variations (already collapsed by
    normalize_skill via SKILL_SYNONYMS) are caught without needing to be listed here directly."""
    return normalize_skill(skill) in GENERIC_SKILLS


# The non-technical remainder of the "Business / soft skills" section above (after the generic
# filler ones are excluded entirely — see GENERIC_SKILLS). Used only to *prefer* technical gaps
# when generating interview questions (questions/generate.py), not to exclude these — a genuinely
# required business skill still counts toward the match score.
NON_TECH_SKILLS: frozenset[str] = frozenset(
    {
        "project management",
        "stakeholder management",
        "leadership",
        "cross-functional collaboration",
        "negotiation",
        "public speaking",
        "mentoring",
        "customer success",
        "sales",
        "marketing",
        "seo",
        "content strategy",
        "financial modeling",
        "accounting",
    }
)


def is_technical_skill(skill: str) -> bool:
    """Best-effort technology signal for prioritizing interview questions. Defaults to True for
    anything not explicitly tagged otherwise: the technology space is far too open-ended to
    enumerate (a JD can name any language/framework/tool), so it's more robust to maintain the
    much smaller, closed list of known non-technical business skills instead."""
    normalized = normalize_skill(skill)
    return normalized not in NON_TECH_SKILLS and normalized not in GENERIC_SKILLS


_ALIAS_TO_CANONICAL: dict[str, str] = {}
for canonical, aliases in SKILL_SYNONYMS.items():
    _ALIAS_TO_CANONICAL[canonical] = canonical
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias] = canonical

_ALL_LOOKUP_KEYS = list(_ALIAS_TO_CANONICAL.keys())

FUZZY_MATCH_THRESHOLD = 88


def normalize_skill(raw: str) -> str:
    """Map free text to a canonical skill name. Unknown skills are returned cleaned but as-is —
    we still want to track skills outside the curated list, just without alias collapsing.
    """
    cleaned = raw.strip().lower()
    if not cleaned:
        return cleaned
    if cleaned in _ALIAS_TO_CANONICAL:
        return _ALIAS_TO_CANONICAL[cleaned]

    match = process.extractOne(cleaned, _ALL_LOOKUP_KEYS, scorer=fuzz.WRatio)
    if match and match[1] >= FUZZY_MATCH_THRESHOLD:
        return _ALIAS_TO_CANONICAL[match[0]]

    return cleaned


def skills_equivalent(a: str, b: str) -> bool:
    """True if two (already-normalized-or-not) skill strings refer to the same skill."""
    na, nb = normalize_skill(a), normalize_skill(b)
    if na == nb:
        return True
    return fuzz.WRatio(na, nb) >= FUZZY_MATCH_THRESHOLD
