import textwrap
from pathlib import Path

import pytest

from interviewd.config import InterviewConfig
from interviewd.data.question_bank import Question, QuestionBank


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_bank(tmp_path: Path, content: str) -> QuestionBank:
    """Write a behavioral.yaml fixture and return a QuestionBank pointing at it."""
    (tmp_path / "behavioral.yaml").write_text(textwrap.dedent(content), encoding="utf-8")
    return QuestionBank(str(tmp_path))


_MINIMAL_YAML = """\
    questions:
      - id: b001
        text: "Tell me about a time you led a team."
        tags: [leadership]
        difficulty: mid
        follow_up: "What would you do differently?"
      - id: b002
        text: "Describe a conflict you resolved."
        tags: [conflict]
        difficulty: entry
        follow_up: "What did you learn?"
      - id: b003
        text: "Give an example of handling ambiguity."
        tags: [decision_making]
        difficulty: senior
        follow_up: "How did you validate the decision?"
"""


# ---------------------------------------------------------------------------
# Question model
# ---------------------------------------------------------------------------

def test_question_model_required_fields():
    q = Question(id="x001", text="Hello?", difficulty="mid")
    assert q.id == "x001"
    assert q.follow_up == ""
    assert q.tags == []


def test_question_model_full():
    q = Question(id="x002", text="Q?", tags=["t1"], difficulty="senior", follow_up="FU")
    assert q.tags == ["t1"]
    assert q.difficulty == "senior"


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def test_load_returns_all_questions(tmp_path):
    bank = _make_bank(tmp_path, _MINIMAL_YAML)
    config = InterviewConfig(type="behavioral", difficulty="staff", num_questions=10)
    questions = bank.pick(config, seed=0)
    assert len(questions) == 3  # only 3 in fixture


def test_missing_type_raises(tmp_path):
    bank = QuestionBank(str(tmp_path))  # empty dir
    config = InterviewConfig(type="behavioral", difficulty="mid", num_questions=5)
    with pytest.raises(FileNotFoundError, match="behavioral"):
        bank.pick(config)


# ---------------------------------------------------------------------------
# Difficulty filtering
# ---------------------------------------------------------------------------

def test_entry_difficulty_excludes_harder_questions(tmp_path):
    bank = _make_bank(tmp_path, _MINIMAL_YAML)
    config = InterviewConfig(type="behavioral", difficulty="entry", num_questions=10)
    questions = bank.pick(config, seed=0)
    assert all(q.difficulty == "entry" for q in questions)


def test_mid_difficulty_includes_entry_and_mid(tmp_path):
    bank = _make_bank(tmp_path, _MINIMAL_YAML)
    config = InterviewConfig(type="behavioral", difficulty="mid", num_questions=10)
    questions = bank.pick(config, seed=0)
    difficulties = {q.difficulty for q in questions}
    assert difficulties == {"entry", "mid"}
    assert "senior" not in difficulties


def test_senior_difficulty_excludes_staff(tmp_path):
    bank = _make_bank(tmp_path, _MINIMAL_YAML)
    config = InterviewConfig(type="behavioral", difficulty="senior", num_questions=10)
    questions = bank.pick(config, seed=0)
    assert all(q.difficulty != "staff" for q in questions)


# ---------------------------------------------------------------------------
# num_questions cap
# ---------------------------------------------------------------------------

def test_pick_respects_num_questions(tmp_path):
    bank = _make_bank(tmp_path, _MINIMAL_YAML)
    config = InterviewConfig(type="behavioral", difficulty="staff", num_questions=2)
    questions = bank.pick(config, seed=0)
    assert len(questions) == 2


def test_pick_returns_fewer_when_bank_is_small(tmp_path):
    bank = _make_bank(tmp_path, _MINIMAL_YAML)
    config = InterviewConfig(type="behavioral", difficulty="entry", num_questions=99)
    questions = bank.pick(config, seed=0)
    # Only one entry-level question in the fixture
    assert len(questions) == 1


# ---------------------------------------------------------------------------
# Determinism and randomness
# ---------------------------------------------------------------------------

def test_pick_is_deterministic_with_seed(tmp_path):
    bank = _make_bank(tmp_path, _MINIMAL_YAML)
    config = InterviewConfig(type="behavioral", difficulty="staff", num_questions=2)
    first = bank.pick(config, seed=42)
    second = bank.pick(config, seed=42)
    assert [q.id for q in first] == [q.id for q in second]


def test_pick_varies_without_seed(tmp_path):
    # Build a larger fixture so sampling can produce different orders
    items = "\n".join(
        f'  - id: b{i:03d}\n    text: "Q {i}?"\n    difficulty: mid\n    follow_up: ""'
        for i in range(20)
    )
    yaml_content = f"questions:\n{items}\n"
    bank = _make_bank(tmp_path, yaml_content)
    config = InterviewConfig(type="behavioral", difficulty="mid", num_questions=5)
    results = [tuple(q.id for q in bank.pick(config)) for _ in range(10)]
    # At least two different orderings in 10 draws (astronomically unlikely to be same)
    assert len(set(results)) > 1


# ---------------------------------------------------------------------------
# available_types
# ---------------------------------------------------------------------------

def test_available_types(tmp_path):
    (tmp_path / "behavioral.yaml").write_text("questions: []", encoding="utf-8")
    (tmp_path / "technical.yaml").write_text("questions: []", encoding="utf-8")
    bank = QuestionBank(str(tmp_path))
    assert bank.available_types() == ["behavioral", "technical"]


def test_available_types_empty_dir(tmp_path):
    bank = QuestionBank(str(tmp_path))
    assert bank.available_types() == []
