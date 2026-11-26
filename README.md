# 🧠 Brain Games Arcade

**Live demo:** https://knarf24.github.io/brain-games-arcade/

**The problem:** most free puzzle apps are full of ads, ask you to sign up, and need a connection. Families and schools
want short, healthy screen time that actually trains thinking: logic, memory, spelling and number sense.

**The app:** four classic brain games in one page, free, with no ads and no sign-up. It works on a phone and keeps
working offline after the first visit (you can add it to your home screen).

- **🔢 2048:** swipe tiles and join equal numbers to reach 2048 (planning ahead). One-step undo.
- **🎯 Mastermind:** crack a hidden code of 4 colours in 10 tries (logic). Option for no repeated colours.
- **🔤 Hangman:** guess the word letter by letter, with 75 words in 5 topics and a clue that costs a life (spelling).
- **🐮 Cows and Bulls:** guess a secret 4-digit number from bulls and cows clues (number logic).

What ties them together:

- **Daily puzzles:** everyone gets the same four puzzles each day, so a class or family can compare. Copy your result
  to share it (the code games share an emoji grid, without spoilers).
- **Coach:** in Mastermind and Cows and Bulls it shows how many codes still fit your clues, and can suggest the guess
  that narrows things down the most (Knuth's minimax idea). Hints cost points, so it teaches without giving it away.
- **Streak and stats:** a daily streak, games played, wins and best scores, saved only on your device.

All game logic is **Python** (`arcade.py`) running **inside your browser** with [Pyodide](https://pyodide.org).
It is hosted free on GitHub Pages.

Built by combining four GeeksforGeeks Python projects:

| GeeksforGeeks project | What it does here |
|---|---|
| [2048 Game in Python](https://www.geeksforgeeks.org/python/2048-game-in-python/) | The 2048 board: slide, merge, new tiles, win and game-over checks, plus undo |
| [Mastermind Game using Python](https://www.geeksforgeeks.org/python/mastermind-game-using-python/) | The colour code game with exact and near clues, and the coach |
| [Hangman Game in Python](https://www.geeksforgeeks.org/python/hangman-game-python/) | Word guessing with topics, clues and the drawing |
| [Cows and Bulls game](https://www.geeksforgeeks.org/python/python-cows-and-bulls-game/) | The secret-number game, with a coach that counts the numbers still possible |

## Files

| File | What it is |
|---|---|
| `arcade.py` | All the game rules, scoring, daily puzzles, coach and stats (Python, standard library only) |
| `web/` | The page: `index.html`, `main.js` (drawing, taps, swipes, saving stats), `style.css`, `sw.js` (offline), and Pyodide in `web/pyodide/` |
| `desktop.py` | Play the same games in a terminal: `python desktop.py` (add `--daily` for today's puzzles) |
| `tests/test_arcade.py` | Tests, including the coach solving 15 random codes of each game: `python tests/test_arcade.py` |
| `build_site.sh`, `.github/workflows/pages.yml` | Builds `_site/` and publishes it to GitHub Pages |

## Controls

- **2048:** swipe on a phone, or arrow keys / WASD; Z to undo.
- **Mastermind:** tap colours (or keys 1 to 6), tap a peg to remove it, Enter to check.
- **Hangman:** tap letters or type them.
- **Cows and Bulls:** tap or type digits, Backspace, Enter.

## Privacy

Nothing leaves your device. Stats are kept in your browser's local storage, and "Reset my stats" deletes them.

## License

MIT. Pyodide is MPL-2.0.
