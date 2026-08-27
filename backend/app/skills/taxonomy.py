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
    "communication": ["verbal communication", "written communication"],
    "leadership": ["team leadership"],
    "cross-functional collaboration": ["cross functional collaboration"],
    "negotiation": [],
    "public speaking": ["presentation skills"],
    "problem solving": ["analytical thinking", "analytical skills"],
    "mentoring": ["coaching"],
    "customer success": [],
    "sales": ["b2b sales", "b2c sales"],
    "crm": ["salesforce", "hubspot"],
    "marketing": ["digital marketing"],
    "seo": ["search engine optimization"],
    "content strategy": ["content marketing"],
    "financial modeling": [],
    "accounting": [],
}

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
