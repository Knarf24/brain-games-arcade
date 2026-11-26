"""Play Brain Games Arcade in a terminal, with the same Python logic as the web page.

    python desktop.py            # pick a game from the menu
    python desktop.py --daily    # today's daily puzzles
"""

import argparse
from datetime import date

import arcade

KEYS_2048 = {"w": "up", "a": "left", "s": "down", "d": "right"}
COLOUR_KEYS = "rbgypo"  # red blue green yellow purple orange


def ask(prompt):
    try:
        return input(prompt).strip().lower()
    except EOFError:
        raise SystemExit


def play_2048(rng):
    g = arcade.Game2048(rng)
    while not g.finished():
        print("\n".join(" ".join(f"{v or '.':>5}" for v in row) for row in g.grid))
        print(f"score {g.score}")
        k = ask("w/a/s/d to move, u to undo, q to quit: ")
        if k == "q":
            break
        if k == "u":
            g.undo()
        elif k in KEYS_2048 and not g.move(KEYS_2048[k]):
            print("Nothing moved.")
    print("You reached 2048!" if g.won else f"Game over. Score {g.score}." if g.over else f"Stopped. Score {g.score}.")
    return g


def play_mastermind(rng):
    g = arcade.Mastermind(rng)
    print("Colours: r=red b=blue g=green y=yellow p=purple o=orange. Type 4 letters, e.g. rgby. ? = coach.")
    while not g.finished():
        k = ask(f"[{g.tries_left()} tries, {len(g.possible())} codes fit] guess: ")
        if k == "?":
            print("Coach suggests:", "".join(COLOUR_KEYS[c] for c in g.hint()["suggest"]))
            continue
        try:
            s = g.check([COLOUR_KEYS.index(ch) for ch in k])
            last = s["guesses"][-1]
            print(f"  {last['exact']} right place, {last['near']} wrong place")
        except ValueError as e:
            print(" ", e)
    print("Cracked it!" if g.solved else "Out of tries.", "Code:", "".join(COLOUR_KEYS[c] for c in g.secret))
    return g


def play_hangman(rng):
    g = arcade.Hangman(rng)
    print("Topic:", g.category, "  (type ! for a clue, costs 1 life)")
    while not g.finished():
        print(g.pattern(), "  lives:", g.lives, "  wrong:", " ".join(g.wrong))
        k = ask("letter: ")
        if k == "!":
            print("Clue:", g.show_clue()["clue"])
            continue
        try:
            g.guess(k)
        except ValueError as e:
            print(" ", e)
    print("You got it:" if g.solved() else "The word was:", g.word.upper())
    return g


def play_cows_bulls(rng):
    g = arcade.CowsBulls(rng)
    print("Guess the 4-digit number (all digits different). ? = coach.")
    while not g.finished():
        k = ask(f"[{g.tries_left()} tries, {len(g.possible())} numbers fit] guess: ")
        if k == "?":
            print("Coach suggests:", g.hint()["suggest"])
            continue
        try:
            last = g.check(k)["guesses"][-1]
            print(f"  {last['bulls']} bulls, {last['cows']} cows")
        except ValueError as e:
            print(" ", e)
    print("Cracked it!" if g.solved else "Out of tries.", "The number was", g.secret)
    return g


GAMES = {"1": ("2048", play_2048), "2": ("mastermind", play_mastermind),
         "3": ("hangman", play_hangman), "4": ("cowsbulls", play_cows_bulls)}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--daily", action="store_true", help="play today's daily puzzles")
    day = date.today().isoformat() if ap.parse_args().daily else None
    while True:
        k = ask("\n1) 2048  2) Mastermind  3) Hangman  4) Cows and Bulls  q) quit: ")
        if k == "q":
            break
        if k in GAMES:
            name, play = GAMES[k]
            g = play(arcade.make_rng(name, day))
            print(f"Points: {arcade.points(g)}")


if __name__ == "__main__":
    main()
