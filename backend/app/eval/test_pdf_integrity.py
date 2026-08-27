"""Unit tests for the pure classification/reconstruction helpers in pdf_integrity.py, using
pdfplumber-shaped word/rect dicts directly rather than generating real PDF files. This covers the
actual detection logic (the part worth being confident about); the pdfplumber-integration glue in
extract_pdf_text_and_hidden_spans was verified manually against a crafted real PDF.
"""

from app.parsing.pdf_integrity import (
    PALE_LUMINANCE_THRESHOLD,
    TINY_FONT_THRESHOLD,
    _classify_word,
    _has_contrasting_fill_behind,
    _luminance,
    _words_to_text,
)

PAGE_W, PAGE_H = 612.0, 792.0  # standard US Letter, points


def _word(text="hello", x0=100, x1=140, top=100, bottom=112, size=11.0, color=(0.0, 0.0, 0.0)):
    return {"text": text, "x0": x0, "x1": x1, "top": top, "bottom": bottom, "size": size, "non_stroking_color": color}


def test_luminance_grayscale_float():
    assert _luminance(1.0) == 1.0
    assert _luminance(0.0) == 0.0


def test_luminance_rgb_white_and_black():
    assert _luminance((1, 1, 1)) == 1.0
    assert _luminance((0, 0, 0)) == 0.0


def test_luminance_cmyk():
    # pure black in CMYK
    assert _luminance((0, 0, 0, 1)) == 0.0
    # no ink at all -> white
    assert _luminance((0, 0, 0, 0)) == 1.0


def test_luminance_none_and_unrecognized_shape():
    assert _luminance(None) is None
    assert _luminance((1, 2, 3, 4, 5)) is None


def test_normal_black_text_is_not_flagged():
    word = _word(color=(0, 0, 0), size=11.0)
    assert _classify_word(word, PAGE_W, PAGE_H, filled_rects=[]) is None


def test_white_text_on_blank_page_is_flagged():
    word = _word(color=(1, 1, 1), size=11.0)
    assert _classify_word(word, PAGE_W, PAGE_H, filled_rects=[]) == "white_on_white"


def test_white_text_on_a_colored_header_bar_is_not_flagged():
    # legitimate design: a dark rectangle behind white heading text
    word = _word(color=(1, 1, 1), size=14.0, x0=50, x1=200, top=20, bottom=40)
    dark_rect = {"fill": True, "non_stroking_color": (0.1, 0.1, 0.4), "x0": 0, "x1": PAGE_W, "top": 0, "bottom": 60}
    assert _classify_word(word, PAGE_W, PAGE_H, filled_rects=[dark_rect]) is None


def test_tiny_font_is_flagged_even_if_black():
    word = _word(color=(0, 0, 0), size=TINY_FONT_THRESHOLD - 0.1)
    assert _classify_word(word, PAGE_W, PAGE_H, filled_rects=[]) == "tiny_font"


def test_off_page_word_is_flagged():
    word = _word(x0=-500, x1=-450, top=100, bottom=112)
    assert _classify_word(word, PAGE_W, PAGE_H, filled_rects=[]) == "off_page"


def test_near_white_just_under_threshold_is_not_flagged():
    just_visible = PALE_LUMINANCE_THRESHOLD - 0.05
    word = _word(color=(just_visible, just_visible, just_visible))
    assert _classify_word(word, PAGE_W, PAGE_H, filled_rects=[]) is None


def test_contrasting_fill_check_ignores_pale_rects():
    word = _word(color=(1, 1, 1), x0=50, x1=200, top=20, bottom=40)
    pale_rect = {"fill": True, "non_stroking_color": (0.99, 0.99, 0.99), "x0": 0, "x1": PAGE_W, "top": 0, "bottom": 60}
    # the "background" rect is itself basically white, so this is still hidden text, not design
    assert _has_contrasting_fill_behind(word, [pale_rect]) is False


def test_words_to_text_groups_by_line():
    words = [
        {"text": "Hello", "top": 100},
        {"text": "world", "top": 100.5},
        {"text": "Second", "top": 130},
        {"text": "line", "top": 131},
    ]
    assert _words_to_text(words) == "Hello world\nSecond line"


def test_words_to_text_empty():
    assert _words_to_text([]) == ""
