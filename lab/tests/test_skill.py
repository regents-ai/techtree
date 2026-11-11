import json
from pathlib import Path

from payment_terms import offers

SKILL = Path(__file__).resolve().parents[1] / "skills" / "payment-terms" / "SKILL.md"


def test_skill_holds_no_held_out_task_or_answer() -> None:
    text = SKILL.read_text()
    for item in offers.generate(0)["held_out"]:
        resource = item.answer["resource"]
        assert item.prompt not in text
        assert json.dumps(item.answer) not in text
        assert item.answer["accepts"][0]["payTo"] not in text
        assert resource["url"] not in text
        assert resource["description"] not in text


def test_skill_names_the_fixed_fields() -> None:
    text = SKILL.read_text()
    for fixed in (offers.NETWORK, offers.USDC, offers.MIME_TYPE, '"USD Coin"', '"exact"'):
        assert fixed in text
