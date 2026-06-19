from epy_slides.slide_md import expand_for_pptx, expand_for_revealjs


def test_layout_directive_adds_class_revealjs():
    out = expand_for_revealjs("## Title\n<!-- layout: two-column -->\n\nx\n")
    assert "<!-- layout:" not in out
    assert ".slide-two-column" in out
    assert out.startswith("## Title {")


def test_centered_layout_adds_center():
    out = expand_for_revealjs("## Q\n<!-- layout: quote -->\n")
    assert ".center" in out
    assert ".slide-quote" in out


def test_orphan_directive_dropped():
    out = expand_for_revealjs("<!-- layout: blank -->\n\ntext\n")
    assert "layout:" not in out
    assert "text" in out


def test_pptx_section_promoted_to_h1():
    out = expand_for_pptx("## Intro\n<!-- layout: section -->\n")
    first = out.splitlines()[0]
    assert first.startswith("# ")
    assert not first.startswith("##")


def test_pptx_callout_to_blockquote():
    src = '::: {.callout-note title="Heads up"}\nBody line\n:::\n'
    out = expand_for_pptx(src)
    assert "> **Heads up**" in out
    assert ".callout-note" not in out


def test_pptx_strips_pause_and_layout():
    src = "## A\n<!-- layout: title-content -->\n\nfoo\n\n. . .\n\nbar\n"
    out = expand_for_pptx(src)
    assert "layout:" not in out
    assert ". . ." not in out
    assert "foo" in out
    assert "bar" in out


def test_front_matter_preserved():
    src = "---\ntitle: T\n---\n\n## A\n"
    assert "title: T" in expand_for_revealjs(src)
    assert "title: T" in expand_for_pptx(src)


def test_columns_pass_through_both_writers():
    src = "## A\n\n:::: {.columns}\n::: {.column}\nx\n:::\n::::\n"
    assert ".columns" in expand_for_revealjs(src)
    assert ".columns" in expand_for_pptx(src)


def test_fenced_code_not_touched():
    src = "## A\n\n```\n<!-- layout: x -->\n. . .\n```\n"
    out = expand_for_pptx(src)
    assert "<!-- layout: x -->" in out
    assert ". . ." in out
