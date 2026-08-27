from app.parsing.links import extract_links


def test_extracts_and_classifies_github_linkedin_and_site():
    text = """
    Jane Doe
    github.com/janedoe
    https://www.linkedin.com/in/janedoe
    Personal site: janedoe.dev
    Email: jane@gmail.com
    """
    links = extract_links(text)
    kinds = {l.kind for l in links}
    assert "github" in kinds
    assert "linkedin" in kinds
    assert "site" in kinds

    github = next(l for l in links if l.kind == "github")
    assert github.username == "janedoe"

    site = next(l for l in links if l.kind == "site")
    assert "janedoe.dev" in site.url


def test_ignores_email_domains():
    text = "Contact me at jane@gmail.com"
    links = extract_links(text)
    assert all("gmail.com" not in l.domain for l in links)


def test_dedupes_repeated_links():
    text = "github.com/janedoe github.com/janedoe github.com/janedoe"
    links = extract_links(text)
    assert len(links) == 1


def test_no_links_in_plain_text():
    assert extract_links("Just some plain text with no URLs at all.") == []


def test_degree_abbreviations_are_not_mistaken_for_links():
    # Regression: "B.Tech" was extracted as a link to b.tech and background-checked, because
    # .tech is a real TLD. Same collision exists for B.Com/M.Com against .com.
    text = """
    Education & Certifications
    B.Tech in Electrical and Electronics Engineering, 2014 - 2018
    M.Tech in Computer Science
    B.Com in Accounting
    """
    links = extract_links(text)
    domains = {l.domain for l in links}
    assert "b.tech" not in domains
    assert "m.tech" not in domains
    assert "b.com" not in domains
