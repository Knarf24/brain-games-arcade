"""Brain Games Arcade: the game logic for four puzzle games, in plain Python.

2048, Mastermind, Hangman and Cows and Bulls. The same code runs in the browser
(Pyodide) and on a computer (desktop.py). Nothing here touches the screen: every
game is a small class with a `state()` that the page draws.

Extras that make it more than four separate games:
  * Daily puzzles: the same puzzles for everyone on a given day (seeded by date).
  * Coach: for the code-breaking games it counts how many secret codes are still
    possible after your clues, and can suggest a good next guess.
  * Stats: games played, wins, best scores and a daily streak, kept as a small
    dict the page saves in the browser.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import random
from datetime import date, timedelta

# ---------------------------------------------------------------- helpers


def make_rng(game: str, day: str | None = None) -> random.Random:
    """A random generator. With a day ("2026-11-26") it is the same for everyone."""
    if day is None:
        return random.Random()
    digest = hashlib.sha256(f"brain-games:{game}:{day}".encode()).hexdigest()
    return random.Random(int(digest[:16], 16))


# ---------------------------------------------------------------- 2048


class Game2048:
    """Slide tiles, join equal numbers, reach 2048. Based on GfG '2048 Game in Python'."""

    name = "2048"
    SIZE = 4

    def __init__(self, rng: random.Random, size: int = 4):
        self.rng = rng
        self.size = size
        self.grid = [[0] * size for _ in range(size)]
        self.score = 0
        self.moves = 0
        self.won = False
        self.keep_going = False
        self.over = False
        self.last_new: list[int] | None = None
        self.last_merged: list[list[int]] = []
        self._undo: tuple | None = None
        self._add_tile()
        self._add_tile()

    def _empty(self):
        return [(r, c) for r in range(self.size) for c in range(self.size) if self.grid[r][c] == 0]

    def _add_tile(self):
        empty = self._empty()
        if not empty:
            return
        r, c = self.rng.choice(empty)
        self.grid[r][c] = 4 if self.rng.random() < 0.1 else 2
        self.last_new = [r, c]

    @staticmethod
    def _slide_row(row: list[int]) -> tuple[list[int], int, list[int]]:
        """Slide one row to the left. Returns (new row, points, merged column indexes)."""
        tiles = [v for v in row if v]
        out, points, merged = [], 0, []
        i = 0
        while i < len(tiles):
            if i + 1 < len(tiles) and tiles[i] == tiles[i + 1]:
                out.append(tiles[i] * 2)
                points += tiles[i] * 2
                merged.append(len(out) - 1)
                i += 2
            else:
                out.append(tiles[i])
                i += 1
        return out + [0] * (len(row) - len(out)), points, merged

    def _can_move(self) -> bool:
        if self._empty():
            return True
        n = self.size
        for r in range(n):
            for c in range(n):
                v = self.grid[r][c]
                if c + 1 < n and self.grid[r][c + 1] == v:
                    return True
                if r + 1 < n and self.grid[r + 1][c] == v:
                    return True
        return False

    def move(self, direction: str) -> bool:
        """direction: left, right, up or down. Returns True if anything moved."""
        if self.over or (self.won and not self.keep_going):
            return False
        n = self.size
        before = [row[:] for row in self.grid]
        undo = (before, self.score, self.moves, self.won)
        points_total = 0
        merged_cells: list[list[int]] = []
        for i in range(n):
            if direction in ("left", "right"):
                line = self.grid[i][:]
            else:
                line = [self.grid[r][i] for r in range(n)]
            rev = direction in ("right", "down")
            if rev:
                line.reverse()
            new, points, merged = self._slide_row(line)
            if rev:
                new.reverse()
                merged = [n - 1 - m for m in merged]
            points_total += points
            for m in merged:
                merged_cells.append([i, m] if direction in ("left", "right") else [m, i])
            if direction in ("left", "right"):
                self.grid[i] = new
            else:
                for r in range(n):
                    self.grid[r][i] = new[r]
        if self.grid == before:
            return False
        self._undo = undo
        self.score += points_total
        self.moves += 1
        self.last_merged = merged_cells
        self._add_tile()
        if not self.won and any(v >= 2048 for row in self.grid for v in row):
            self.won = True
        self.over = not self._can_move()
        return True

    def undo(self) -> bool:
        """Take back the last move (one step only)."""
        if not self._undo:
            return False
        grid, self.score, self.moves, self.won = self._undo
        self.grid = [row[:] for row in grid]
        self.over = False
        self.last_new, self.last_merged, self._undo = None, [], None
        return True

    def continue_after_win(self):
        self.keep_going = True

    def best_tile(self) -> int:
        return max(v for row in self.grid for v in row)

    def finished(self) -> bool:
        return self.over or (self.won and not self.keep_going)

    def state(self) -> dict:
        return {
            "game": self.name,
            "grid": self.grid,
            "score": self.score,
            "moves": self.moves,
            "best_tile": self.best_tile(),
            "won": self.won,
            "keep_going": self.keep_going,
            "over": self.over,
            "can_undo": self._undo is not None,
            "new": self.last_new,
            "merged": self.last_merged,
        }


# ---------------------------------------------------------------- code-breaking (shared)


def score_mastermind(secret: tuple, guess: tuple) -> tuple[int, int]:
    """(exact, near): right colour in the right place, right colour in the wrong place."""
    exact = sum(s == g for s, g in zip(secret, guess))
    common = sum(min(secret.count(c), guess.count(c)) for c in set(guess))
    return exact, common - exact


def score_cows_bulls(secret: str, guess: str) -> tuple[int, int]:
    """(bulls, cows): right digit in the right place, right digit in the wrong place."""
    bulls = sum(s == g for s, g in zip(secret, guess))
    cows = sum(1 for g in guess if g in secret) - bulls
    return bulls, cows


class _CodeBreaker:
    """Shared by Mastermind and Cows and Bulls: guesses, clues and the coach."""

    max_tries = 10

    def __init__(self):
        self.guesses: list[dict] = []
        self.solved = False
        self.hints_used = 0
        self._possible = None  # filled lazily

    def all_codes(self) -> list:
        raise NotImplementedError

    def score(self, secret, guess):
        raise NotImplementedError

    def possible(self) -> list:
        """Every code that still fits all the clues so far."""
        if self._possible is None:
            codes = self.all_codes()
            for g in self.guesses:
                guess, clue = g["_code"], (g["a"], g["b"])
                codes = [c for c in codes if self.score(c, guess) == clue]
            self._possible = codes
        return self._possible

    def _record(self, code, clue):
        self.guesses.append({"_code": code, "a": clue[0], "b": clue[1]})
        if self._possible is not None:
            self._possible = [c for c in self._possible if self.score(c, code) == clue]

    def suggest(self):
        """A good next guess: the one that leaves the fewest codes in the worst case
        (Knuth's minimax idea), checked over a sample to stay fast in the browser."""
        possible = self.possible()
        if len(possible) <= 2:
            return possible[0]
        if not self.guesses:
            return self.opening_guess()
        rng = random.Random(len(possible))
        candidates = possible if len(possible) <= 60 else rng.sample(possible, 60)
        sample = possible if len(possible) <= 400 else rng.sample(possible, 400)
        best, best_worst = None, None
        for cand in candidates:
            buckets: dict = {}
            for secret in sample:
                k = self.score(secret, cand)
                buckets[k] = buckets.get(k, 0) + 1
            worst = max(buckets.values())
            if best_worst is None or worst < best_worst:
                best, best_worst = cand, worst
        return best

    def opening_guess(self):
        return self.possible()[0]

    def finished(self) -> bool:
        return self.solved or len(self.guesses) >= self.max_tries

    def tries_left(self) -> int:
        return self.max_tries - len(self.guesses)


# ---------------------------------------------------------------- Mastermind


class Mastermind(_CodeBreaker):
    """Crack the hidden colour code. Based on GfG 'Mastermind Game using Python'."""

    name = "mastermind"
    COLOURS = ["red", "blue", "green", "yellow", "purple", "orange"]

    def __init__(self, rng: random.Random, pegs: int = 4, colours: int = 6, repeats: bool = True):
        super().__init__()
        self.pegs = pegs
        self.colours = self.COLOURS[:colours]
        self.repeats = repeats
        if repeats:
            self.secret = tuple(rng.randrange(colours) for _ in range(pegs))
        else:
            self.secret = tuple(rng.sample(range(colours), pegs))

    def all_codes(self):
        n = len(self.colours)
        if self.repeats:
            return list(itertools.product(range(n), repeat=self.pegs))
        return list(itertools.permutations(range(n), self.pegs))

    def score(self, secret, guess):
        return score_mastermind(secret, guess)

    def opening_guess(self):
        # Knuth's classic opener (two colours, two each) works well for 4 pegs.
        if self.repeats and self.pegs == 4:
            return (0, 0, 1, 1)
        return tuple(range(self.pegs))

    def check(self, guess: list[int]) -> dict:
        if self.finished():
            raise ValueError("This game is over. Start a new one.")
        code = tuple(int(x) for x in guess)
        if len(code) != self.pegs or any(not 0 <= c < len(self.colours) for c in code):
            raise ValueError(f"Pick {self.pegs} colours.")
        if not self.repeats and len(set(code)) != len(code):
            raise ValueError("Each colour can be used only once in this mode.")
        clue = self.score(self.secret, code)
        self._record(code, clue)
        self.solved = clue[0] == self.pegs
        return self.state()

    def hint(self) -> dict:
        self.hints_used += 1
        return {"suggest": list(self.suggest()), "possible": len(self.possible())}

    def state(self) -> dict:
        done = self.finished()
        return {
            "game": self.name,
            "pegs": self.pegs,
            "colours": self.colours,
            "repeats": self.repeats,
            "guesses": [{"code": list(g["_code"]), "exact": g["a"], "near": g["b"]} for g in self.guesses],
            "tries_left": self.tries_left(),
            "max_tries": self.max_tries,
            "solved": self.solved,
            "over": done,
            "secret": list(self.secret) if done else None,
            "possible": len(self.possible()),
            "hints_used": self.hints_used,
        }


# ---------------------------------------------------------------- Cows and Bulls


class CowsBulls(_CodeBreaker):
    """Guess the secret number with different digits. Based on GfG 'Cows and Bulls game'."""

    name = "cowsbulls"

    def __init__(self, rng: random.Random, digits: int = 4):
        super().__init__()
        self.digits = digits
        first = rng.choice("123456789")  # no leading zero
        rest = rng.sample([d for d in "0123456789" if d != first], digits - 1)
        self.secret = first + "".join(rest)

    def all_codes(self):
        return [
            "".join(p)
            for p in itertools.permutations("0123456789", self.digits)
            if p[0] != "0"
        ]

    def score(self, secret, guess):
        return score_cows_bulls(secret, guess)

    def opening_guess(self):
        return "1234"[: self.digits] if self.digits <= 4 else "123456789"[: self.digits]

    def check(self, guess: str) -> dict:
        if self.finished():
            raise ValueError("This game is over. Start a new one.")
        g = str(guess).strip()
        if len(g) != self.digits or not g.isdigit():
            raise ValueError(f"Type a {self.digits}-digit number.")
        if g[0] == "0":
            raise ValueError("The number can't start with 0.")
        if len(set(g)) != len(g):
            raise ValueError("Every digit must be different.")
        clue = self.score(self.secret, g)
        self._record(g, clue)
        self.solved = clue[0] == self.digits
        return self.state()

    def hint(self) -> dict:
        self.hints_used += 1
        return {"suggest": self.suggest(), "possible": len(self.possible())}

    def state(self) -> dict:
        done = self.finished()
        return {
            "game": self.name,
            "digits": self.digits,
            "guesses": [{"code": g["_code"], "bulls": g["a"], "cows": g["b"]} for g in self.guesses],
            "tries_left": self.tries_left(),
            "max_tries": self.max_tries,
            "solved": self.solved,
            "over": done,
            "secret": self.secret if done else None,
            "possible": len(self.possible()),
            "hints_used": self.hints_used,
        }


# ---------------------------------------------------------------- Hangman

WORDS = {
    "Animals": {
        "elephant": "The largest land animal, with a long trunk",
        "giraffe": "Tallest animal, eats leaves from tall trees",
        "zebra": "Black and white stripes",
        "cheetah": "The fastest land animal",
        "penguin": "A bird that swims but cannot fly",
        "hippopotamus": "Big river animal whose name means 'river horse'",
        "crocodile": "Reptile with strong jaws that lives in rivers",
        "kangaroo": "Hops and carries its baby in a pouch",
        "dolphin": "Clever sea mammal that clicks and whistles",
        "butterfly": "Starts life as a caterpillar",
        "rhinoceros": "Has one or two horns on its nose",
        "meerkat": "Small animal that stands up to keep watch",
        "tortoise": "Slow, lives long and carries its home",
        "octopus": "Eight arms and three hearts",
        "flamingo": "Pink bird that often stands on one leg",
    },
    "Countries": {
        "zimbabwe": "Home of Victoria Falls and Great Zimbabwe",
        "nigeria": "Africa's most populous country",
        "kenya": "Famous for the Maasai Mara and runners",
        "egypt": "Land of the pyramids and the Nile",
        "brazil": "Largest country in South America",
        "japan": "Island nation, land of the rising sun",
        "canada": "Second-largest country, maple leaf flag",
        "australia": "A country that is also a continent",
        "ghana": "First sub-Saharan colony to win independence",
        "morocco": "North African country with Marrakesh",
        "botswana": "Home of the Okavango Delta",
        "mexico": "Tacos, mariachi and ancient pyramids",
        "india": "Most populous country in the world",
        "norway": "Fjords and the northern lights",
        "argentina": "Tango and Patagonia",
    },
    "Food": {
        "banana": "Yellow fruit you peel",
        "pineapple": "Spiky outside, sweet yellow inside",
        "avocado": "Green fruit used for guacamole",
        "mango": "Juicy tropical fruit with a big stone",
        "chocolate": "Made from cocoa beans",
        "sandwich": "Filling between two slices of bread",
        "pancake": "Flat and cooked in a pan, often with syrup",
        "spaghetti": "Long thin pasta",
        "pumpkin": "Big orange vegetable",
        "watermelon": "Green outside, red inside, lots of seeds",
        "coconut": "Hard hairy shell with water inside",
        "biscuit": "Small baked treat, good with tea",
        "omelette": "Beaten eggs cooked in a pan",
        "porridge": "Warm breakfast made from oats or maize",
        "strawberry": "Red fruit with seeds on the outside",
    },
    "Science": {
        "gravity": "Why things fall down",
        "oxygen": "The gas we need to breathe",
        "planet": "Earth is one of these",
        "volcano": "Mountain that can erupt with lava",
        "magnet": "Pulls iron towards it",
        "skeleton": "All the bones in a body",
        "electricity": "Flows through wires to power things",
        "telescope": "Used to look at stars",
        "rainbow": "Seven colours after the rain",
        "molecule": "Two or more atoms joined together",
        "photosynthesis": "How plants make food from sunlight",
        "thermometer": "Measures temperature",
        "earthquake": "When the ground shakes",
        "astronaut": "A person who travels to space",
        "battery": "Stores energy for a torch or phone",
    },
    "Sports": {
        "football": "The world's most popular sport",
        "cricket": "Bat, ball and wickets",
        "netball": "Like basketball, but no dribbling",
        "rugby": "Oval ball, scrums and tries",
        "swimming": "Racing in a pool",
        "marathon": "A race of about 42 kilometres",
        "tennis": "Rackets and a net, love means zero",
        "basketball": "Shoot the ball through a hoop",
        "volleyball": "Hit the ball over a high net with your hands",
        "boxing": "Fighting with gloves in a ring",
        "cycling": "Racing on two wheels",
        "chess": "A board game sport with kings and queens",
        "athletics": "Running, jumping and throwing events",
        "golf": "Fewest strokes into the hole wins",
        "hockey": "Sticks and a small ball or puck",
    },
}

HANGMAN_LIVES = 6


class Hangman:
    """Guess the word letter by letter before the drawing is finished.
    Based on GfG 'Hangman Game in Python'."""

    name = "hangman"

    def __init__(self, rng: random.Random, category: str | None = None):
        cats = sorted(WORDS)
        self.category = category if category in WORDS else rng.choice(cats)
        word = rng.choice(sorted(WORDS[self.category]))
        self.word = word
        self.clue = WORDS[self.category][word]
        self.guessed: list[str] = []
        self.wrong: list[str] = []
        self.lives = HANGMAN_LIVES
        self.clue_shown = False

    def pattern(self) -> str:
        return " ".join(ch if ch in self.guessed else "_" for ch in self.word)

    def solved(self) -> bool:
        return all(ch in self.guessed for ch in self.word)

    def finished(self) -> bool:
        return self.solved() or self.lives <= 0

    def guess(self, letter: str) -> dict:
        if self.finished():
            raise ValueError("This game is over. Start a new one.")
        letter = str(letter).strip().lower()
        if len(letter) != 1 or not letter.isalpha() or not letter.isascii():
            raise ValueError("Pick one letter from A to Z.")
        if letter in self.guessed or letter in self.wrong:
            raise ValueError(f"You already tried {letter.upper()}.")
        if letter in self.word:
            self.guessed.append(letter)
        else:
            self.wrong.append(letter)
            self.lives -= 1
        return self.state()

    def show_clue(self) -> dict:
        """Showing the clue costs one life (but never the last one)."""
        if not self.clue_shown and not self.finished() and self.lives > 1:
            self.clue_shown = True
            self.lives -= 1
        return self.state()

    def state(self) -> dict:
        done = self.finished()
        return {
            "game": self.name,
            "category": self.category,
            "pattern": self.pattern(),
            "length": len(self.word),
            "guessed": self.guessed,
            "wrong": self.wrong,
            "lives": self.lives,
            "max_lives": HANGMAN_LIVES,
            "clue": self.clue if (self.clue_shown or done) else None,
            "clue_shown": self.clue_shown,
            "can_clue": not self.clue_shown and not done and self.lives > 1,
            "solved": self.solved(),
            "over": done,
            "word": self.word if done else None,
        }


# ---------------------------------------------------------------- scoring and stats


def points(game) -> int:
    """One score per finished game so the games can share a leaderboard."""
    if isinstance(game, Game2048):
        return game.score
    if isinstance(game, Hangman):
        return (100 + 20 * game.lives) if game.solved() else 0
    if isinstance(game, _CodeBreaker):
        if not game.solved:
            return 0
        return max(10, 100 + 15 * game.tries_left() - 25 * game.hints_used)
    return 0


def is_win(game) -> bool:
    if isinstance(game, Game2048):
        return game.won
    if isinstance(game, Hangman):
        return game.solved()
    return game.solved


def empty_stats() -> dict:
    return {"games": {}, "daily": {}, "streak": 0, "best_streak": 0, "last_daily": None}


def record_result(stats: dict, game_name: str, won: bool, score: int, day: str | None = None) -> dict:
    """Add one finished game to the stats. With a day, it also counts towards the daily streak
    (the streak grows when you finish at least one daily puzzle on consecutive days)."""
    stats = json.loads(json.dumps(stats or empty_stats()))
    for k, v in empty_stats().items():
        stats.setdefault(k, v)
    g = stats["games"].setdefault(game_name, {"played": 0, "won": 0, "best": 0, "total": 0})
    g["played"] += 1
    g["won"] += 1 if won else 0
    g["best"] = max(g["best"], int(score))
    g["total"] += int(score)
    if day:
        done = stats["daily"].setdefault(day, {})
        done[game_name] = {"won": bool(won), "score": int(score)}
        last = stats["last_daily"]
        if last != day:
            yesterday = (date.fromisoformat(day) - timedelta(days=1)).isoformat()
            stats["streak"] = stats["streak"] + 1 if last == yesterday else 1
            stats["last_daily"] = day
        stats["best_streak"] = max(stats["best_streak"], stats["streak"])
        # keep only the last 60 days
        for old in sorted(stats["daily"])[:-60]:
            del stats["daily"][old]
    return stats


def current_streak(stats: dict, today: str) -> int:
    """The streak only counts if the last daily puzzle was today or yesterday."""
    last = (stats or {}).get("last_daily")
    if not last:
        return 0
    yesterday = (date.fromisoformat(today) - timedelta(days=1)).isoformat()
    return stats.get("streak", 0) if last in (today, yesterday) else 0


# ---------------------------------------------------------------- the page talks to this


class Arcade:
    """Holds the game being played. The page sends commands and gets JSON back."""

    def __init__(self):
        self.games: dict[str, object] = {}
        self.daily: dict[str, str | None] = {}

    def new(self, game: str, day: str | None = None, **options) -> dict:
        rng = make_rng(game, day)
        if game == "2048":
            g = Game2048(rng)
        elif game == "mastermind":
            g = Mastermind(rng, repeats=options.get("repeats", True))
        elif game == "hangman":
            g = Hangman(rng, options.get("category"))
        elif game == "cowsbulls":
            g = CowsBulls(rng)
        else:
            raise ValueError(f"Unknown game: {game}")
        self.games[game] = g
        self.daily[game] = day
        return self._out(game)

    def _out(self, game: str) -> dict:
        g = self.games[game]
        s = g.state()
        s["daily"] = self.daily.get(game)
        s["finished"] = g.finished()
        s["points"] = points(g)
        s["win"] = is_win(g)
        return s

    def act(self, game: str, action: str, value=None) -> dict:
        g = self.games[game]
        if action == "move":
            g.move(value)
        elif action == "undo":
            g.undo()
        elif action == "continue":
            g.continue_after_win()
        elif action == "check":
            g.check(value)
        elif action == "guess":
            g.guess(value)
        elif action == "clue":
            g.show_clue()
        elif action == "hint":
            out = self._out(game)
            out["hint"] = g.hint()
            out["points"] = points(g)
            return out
        else:
            raise ValueError(f"Unknown action: {action}")
        return self._out(game)


ARCADE = Arcade()


def call(cmd_json: str) -> str:
    """Single entry point for the web page: JSON in, JSON out, errors as {"error": ...}."""
    try:
        cmd = json.loads(cmd_json)
        op = cmd.pop("op")
        if op == "new":
            out = ARCADE.new(cmd.pop("game"), cmd.pop("day", None), **cmd)
        elif op == "act":
            out = ARCADE.act(cmd["game"], cmd["action"], cmd.get("value"))
        elif op == "record":
            out = record_result(cmd.get("stats"), cmd["game"], cmd["won"], cmd["score"], cmd.get("day"))
        elif op == "streak":
            out = {"streak": current_streak(cmd.get("stats"), cmd["today"])}
        elif op == "categories":
            out = {"categories": sorted(WORDS)}
        else:
            raise ValueError(f"Unknown op: {op}")
        return json.dumps(out)
    except (ValueError, KeyError, TypeError) as e:
        return json.dumps({"error": str(e)})
