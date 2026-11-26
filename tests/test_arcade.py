"""Tests for arcade.py. Run: python tests/test_arcade.py"""

import json
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import arcade  # noqa: E402
from arcade import (  # noqa: E402
    CowsBulls, Game2048, Hangman, Mastermind, make_rng, record_result,
    score_cows_bulls, score_mastermind, current_streak, call,
)


def test_slide_row():
    s = Game2048._slide_row
    assert s([2, 2, 2, 2]) == ([4, 4, 0, 0], 8, [0, 1])
    assert s([2, 0, 2, 4]) == ([4, 4, 0, 0], 4, [0])
    assert s([4, 4, 8, 0]) == ([8, 8, 0, 0], 8, [0])
    assert s([2, 4, 8, 16]) == ([2, 4, 8, 16], 0, [])


def test_2048_moves_and_undo():
    g = Game2048(random.Random(1))
    g.grid = [[2, 2, 0, 0], [0, 0, 0, 0], [0, 0, 0, 4], [0, 0, 0, 4]]
    assert g.move("left")
    assert g.grid[0][0] == 4 and g.score == 4
    assert g.undo() and g.grid[0][:2] == [2, 2] and g.score == 0
    g.grid = [[0, 0, 0, 2], [0, 0, 0, 0], [0, 0, 0, 4], [0, 0, 0, 4]]
    assert g.move("down") and g.grid[3][3] == 8


def test_2048_win_and_over():
    g = Game2048(random.Random(2))
    g.grid = [[1024, 1024, 0, 0], [0] * 4, [0] * 4, [0] * 4]
    g.move("left")
    assert g.won and g.finished()
    g.continue_after_win()
    assert not g.finished()
    g = Game2048(random.Random(3))
    g.grid = [[2, 4, 2, 4], [4, 2, 4, 2], [2, 4, 2, 4], [4, 2, 4, 2]]
    assert not g._can_move()


def test_mastermind_scoring():
    assert score_mastermind((0, 1, 2, 3), (0, 1, 2, 3)) == (4, 0)
    assert score_mastermind((0, 1, 2, 3), (3, 2, 1, 0)) == (0, 4)
    assert score_mastermind((0, 0, 1, 1), (0, 1, 0, 2)) == (1, 2)
    assert score_mastermind((1, 1, 1, 1), (1, 2, 2, 2)) == (1, 0)


def test_cows_bulls_scoring():
    assert score_cows_bulls("1234", "1234") == (4, 0)
    assert score_cows_bulls("1234", "4321") == (0, 4)
    assert score_cows_bulls("1234", "1243") == (2, 2)
    assert score_cows_bulls("1234", "5678") == (0, 0)


def _solve_with_coach(game, limit):
    for _ in range(limit):
        if game.finished():
            break
        game.check(game.suggest())
    return game


def test_coach_solves_mastermind():
    for seed in range(15):
        g = _solve_with_coach(Mastermind(random.Random(seed)), 10)
        assert g.solved, f"seed {seed}: {g.secret}"
        assert len(g.guesses) <= 7


def test_coach_solves_cows_bulls():
    for seed in range(15):
        g = _solve_with_coach(CowsBulls(random.Random(seed)), 10)
        assert g.solved, f"seed {seed}: {g.secret}"
        assert len(g.guesses) <= 8
        assert g.secret[0] != "0" and len(set(g.secret)) == 4


def test_possible_shrinks():
    g = CowsBulls(random.Random(4))
    n0 = len(g.possible())
    assert n0 == 9 * 9 * 8 * 7
    g.check("1234")
    assert len(g.possible()) < n0
    assert g.secret in g.possible()


def test_input_checks():
    g = CowsBulls(random.Random(5))
    for bad in ["123", "1123", "0123", "12a4"]:
        try:
            g.check(bad)
            raise AssertionError(bad)
        except ValueError:
            pass
    m = Mastermind(random.Random(5), repeats=False)
    try:
        m.check([0, 0, 1, 2])
        raise AssertionError("repeat allowed")
    except ValueError:
        pass


def test_hangman():
    h = Hangman(random.Random(6), "Animals")
    assert h.category == "Animals" and h.word in arcade.WORDS["Animals"]
    for ch in sorted(set(h.word)):
        h.guess(ch)
    assert h.solved() and h.finished() and h.lives == 6
    h = Hangman(random.Random(6), "Animals")
    h.show_clue()
    assert h.lives == 5 and h.state()["clue"]
    wrong = [c for c in "zqxjvkwy" if c not in h.word]
    for c in wrong[:5]:
        h.guess(c)
    assert h.lives == 0 and h.finished() and h.state()["word"] == h.word
    try:
        Hangman(random.Random(1)).guess("1")
        raise AssertionError
    except ValueError:
        pass


def test_words_are_letters_only():
    for cat, words in arcade.WORDS.items():
        for w in words:
            assert w.isalpha() and w.islower() and w.isascii(), w


def test_daily_is_same_for_everyone():
    a = CowsBulls(make_rng("cowsbulls", "2026-11-26")).secret
    b = CowsBulls(make_rng("cowsbulls", "2026-11-26")).secret
    c = CowsBulls(make_rng("cowsbulls", "2026-11-27")).secret
    assert a == b and a != c


def test_stats_and_streak():
    s = record_result(None, "hangman", True, 200, "2026-11-24")
    s = record_result(s, "2048", False, 1500, "2026-11-25")
    s = record_result(s, "2048", True, 3000, "2026-11-25")
    assert s["streak"] == 2 and s["games"]["2048"] == {"played": 2, "won": 1, "best": 3000, "total": 4500}
    assert current_streak(s, "2026-11-26") == 2
    assert current_streak(s, "2026-11-27") == 0
    s = record_result(s, "hangman", True, 100, "2026-11-27")
    assert s["streak"] == 1 and s["best_streak"] == 2
    s = record_result(s, "hangman", True, 100)  # free play: no streak change
    assert s["streak"] == 1 and s["games"]["hangman"]["played"] == 3


def test_call_api():
    out = json.loads(call(json.dumps({"op": "new", "game": "cowsbulls", "day": "2026-11-26"})))
    assert out["possible"] == 4536 and out["daily"] == "2026-11-26" and out["secret"] is None
    out = json.loads(call(json.dumps({"op": "act", "game": "cowsbulls", "action": "check", "value": "11"})))
    assert "error" in out
    out = json.loads(call(json.dumps({"op": "act", "game": "cowsbulls", "action": "hint"})))
    assert out["hint"]["suggest"] == "1234"
    out = json.loads(call(json.dumps({"op": "new", "game": "2048"})))
    assert sum(v > 0 for row in out["grid"] for v in row) == 2
    out = json.loads(call(json.dumps({"op": "act", "game": "2048", "action": "move", "value": "left"})))
    assert "grid" in out


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
        print("ok ", t.__name__)
    print(f"{len(tests)} tests passed")
