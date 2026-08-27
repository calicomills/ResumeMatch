"""extract_json is the load-bearing function for every LLM call in this app: it's what lets us
never re-argue with the model about output format. Test it against the mess small models
actually produce."""

from app.llm.ollama_client import extract_json


def test_plain_json_object():
    assert extract_json('{"a": 1, "b": 2}') == {"a": 1, "b": 2}


def test_json_in_markdown_fence():
    text = '```json\n{"a": 1}\n```'
    assert extract_json(text) == {"a": 1}


def test_json_with_leading_and_trailing_prose():
    text = 'Sure, here is the JSON you asked for:\n{"a": 1}\nLet me know if you need anything else!'
    assert extract_json(text) == {"a": 1}


def test_json_array():
    text = 'Here you go: ["one", "two", "three"]'
    assert extract_json(text) == ["one", "two", "three"]


def test_nested_braces_in_string_values():
    text = '{"note": "use {curly} braces carefully", "n": 2}'
    assert extract_json(text) == {"note": "use {curly} braces carefully", "n": 2}


def test_garbage_returns_none():
    assert extract_json("I cannot help with that.") is None


def test_truncated_json_returns_none():
    assert extract_json('{"a": 1, "b": [1, 2') is None
