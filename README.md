# megaChess

A PyGame-based chess (and checkers) game that started as an interview hacking challenge and grew into a testbed for AI-assisted development.

## Background

A repo for a chess-based game idea — it came off the back of an interview hacking challenge :)

I got a simple checkers implementation working and set up the foundations for data-driven pieces, boards, and turn-based logic.

Then years passed...

My eldest started playing chess properly just as agentic coding started to return promising results across entire codebases. This felt like the perfect project to see how far that could go.

It's not so mega yet, but it's definitely chess — so that's a start.

---

## Project structure

```
megaChess/
├── Chess/
│   ├── game.py            # Entry point — Game + Graphics classes
│   ├── board.py           # Board state, move generation, check/checkmate
│   ├── pieces.py          # Piece dataclass, PieceMoves (JSON-driven)
│   ├── positions.py       # Position helpers and coordinate utilities
│   ├── win_conditions.py  # ChessWinCondition / CheckersWinCondition
│   ├── svg_renderer.py    # Colourises SVG icons at runtime via cairosvg
│   ├── common.py          # Shared enums: Colours, Directions
│   ├── defs/
│   │   └── pieces_defs.json   # Move rules for all pieces (no hardcoding)
│   ├── assets/pieces/         # One SVG template per piece type
│   └── tests/
│       └── test_chess.py      # pytest test suite (42 tests, ~40 % coverage)
├── pyproject.toml         # Poetry config — deps and dev tools
└── poetry.lock
```

---

## Requirements

- Python 3.11+
- [Poetry](https://python-poetry.org/) for dependency management
- SDL2 system libraries (required by pygame)

### Install SDL2 (Ubuntu/Debian)

```bash
sudo apt-get install libsdl2-dev libsdl2-mixer-dev libsdl2-image-dev libsdl2-ttf-dev
```

### Install Python dependencies

```bash
poetry install             # runtime only (pygame)
poetry install --with dev  # + pytest and pytest-cov
```

---

## Running the game

```bash
poetry run python Chess/game.py
```

Opens an 800 × 800 window. White moves first.

**Controls**

| Action | Input |
|---|---|
| Select a piece | Left-click |
| Move a piece | Left-click a highlighted square |
| Deselect | Left-click the same piece again |

Valid destination squares are highlighted after selecting a piece. The status bar shows whose turn it is and displays "IN CHECK!" when the active king is threatened. Checkmate and stalemate are announced on-screen.

---

## Running the tests

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy poetry run pytest
```

With coverage report:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy poetry run pytest --cov=Chess --cov-report=term-missing
```

CI runs these automatically on every pull request and push to `main` via GitHub Actions (`.github/workflows/tests.yml`).

---

## Architecture highlights

### Data-driven movement (`defs/pieces_defs.json`)

Every piece's legal moves are described in JSON — no per-piece Python methods. `PieceMoves` reads `move_rules` at startup:

```json
"knight": {
  "icon": "assets/pieces/knight.svg",
  "move_rules": [
    {"deltas": [[2,1],[1,2],[-1,2],[-2,1],[-1,-2],[-2,-1],[1,-2],[2,-1]]}
  ]
}
```

Supported rule keys: `deltas`, `sliding`, `directional`, `move_only`, `capture_only`, `first_move_extra_steps`. All 6 chess pieces and 2 checkers pieces are defined this way.

### Pluggable win conditions

`game.win_condition` accepts any object that implements a common interface:

- `ChessWinCondition` — check, checkmate, stalemate
- `CheckersWinCondition` — no legal moves remaining

Swapping game modes means swapping one object.

### Check / checkmate engine

- `board.is_in_check(colour)` — detects whether a king is attacked
- `board.legal_moves_safe(piece)` — filters pseudo-legal moves by simulating each move and undoing it, keeping only those that don't leave the king in check
- Stalemate is detected when `legal_moves_safe` returns an empty set and the king is not in check

### SVG piece icons

Eight SVG templates use `{fill}` and `{stroke}` placeholders. `svg_renderer.py` colourises them at runtime with `cairosvg`, so a single file covers both piece colours.

---

## Status

**Done**

- Data-driven movement rules for all chess and checkers pieces
- Check, checkmate, and stalemate detection
- Legal-move filtering that prevents moving into check
- Pluggable win conditions (chess and checkers)
- SVG icons colourised at runtime
- 42-test pytest suite with coverage reporting
- Poetry-managed dependencies with CI via GitHub Actions

**Stubbed / incomplete**

- Pawn promotion — picker UI exists; `board.king()` is a `pass`
- En passant and castling — not yet modelled
- Test coverage for `PieceMoves`, `win_conditions`, `svg_renderer`, and `game`

**Not started (the "Mega" vision)**

- Runtime board and piece customisation UI
- Save / load game configurations
- Custom piece rules defined in-game
