from pathlib import Path


SKILL = Path(__file__).resolve().parents[2] / "skills" / "marketing" / "ngocviet-marketing" / "SKILL.md"


def _text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_skill_exists_and_has_frontmatter():
    text = _text()
    assert text.startswith("---\n")
    assert "name: ngocviet-marketing" in text
    assert "description:" in text


def test_skill_is_draft_first_and_approval_gated():
    text = _text()
    assert "Default permission = READ + RESEARCH + DRAFT" in text
    assert "explicit human approval" in text
    assert "APPROVAL_REQUIRED" in text


def test_skill_requires_product_truth_and_evidence_boundary():
    text = _text()
    assert "Product Master" in text
    assert "Source Registry" in text
    assert "untrusted evidence" in text
    assert "NEEDS_VERIFICATION" in text


def test_skill_blocks_unapproved_spend_and_publish():
    text = _text().lower()
    assert "modify bids/budgets" in text
    assert "launch/edit/spend requires a separate explicit approval" in text
    assert "fail closed" in text


def test_skill_uses_existing_hermes_cron():
    text = _text()
    assert "use Hermes's existing cron capability instead of adding another scheduler" in text
