# megaChess

A PyGame based game that initially started as Checkers, Chess then all sorts of parameterisation.

## How did it get here?

A repo for a chess-based game idea. This came off the back of an interview hacking challenge I was given :)

I got a simple checkers implementation working and setup the foundations to define pieces, boards and turn based logic.

Then years past...

My eldest started playing chess properly just as agentic started to return promising code across an entire codebase. I'd dabbled for PoCs and minor features but this felt like the perfect project to indulge my curiosity for how far it can go.

It's not so mega at the minute but it's definitely chess, so that's a start.

## Getting started

You'll need Python 3.11+ and [Poetry](https://python-poetry.org/).

On Ubuntu/Debian, install the SDL2 system deps first:

```bash
sudo apt-get install libsdl2-dev libsdl2-mixer-dev libsdl2-image-dev libsdl2-ttf-dev
```

Then:

```bash
poetry install
poetry run python Chess/game.py
```

To run the tests:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy poetry run pytest
```

## Controls

| Key / Action | Effect |
|---|---|
| Click a piece | Select it (legal moves highlighted) |
| Click a highlighted square | Move the selected piece |
| `S` or click **Save** button | Save game to `Chess/saves/autosave.json` |
| `L` or click **Load** button | Load game from `Chess/saves/autosave.json` (greyed out until a save exists) |

## Save / Load

Press **`S`** at any point during a game to save the current board state, whose turn it is, and the active win condition. Press **`L`** to restore it. Saves are written to `Chess/saves/autosave.json` — a human-readable JSON file you can copy, rename, or share.

```json
{
  "board": { "matrix": [...], "en_passant_target": null, "promotion_pending": null },
  "turn": "white",
  "win_condition": "chess"
}
```

## Custom layouts

Drop a JSON file into `Chess/defs/layouts/` and it will appear in the layout picker when you start the game.

```json
{
  "name": "My Variant",
  "win_condition": "chess",
  "pieces_defs": "defs/pieces_defs.json",
  "starting_position": [
    {"x": 4, "y": 7, "piece": "king",  "color": "white"},
    {"x": 4, "y": 0, "piece": "king",  "color": "black"},
    {"x": 0, "y": 4, "piece": "queen", "color": "white"}
  ]
}
```

`win_condition` is either `"chess"` or `"checkers"`. `pieces_defs` points to the piece rules JSON (relative to `Chess/`). Two layouts ship by default: **Standard Chess** and **Standard Checkers**.


## Here's where things stand:

✅ Done

- Data-driven movement — PieceMoves reads move_rules from JSON. No hardcoded per-piece methods. All 6 chess pieces + 2 checkers pieces fully defined.

- Full chess rules — castling, en passant, pawn promotion all implemented.

- Check / checkmate — board.is_in_check(), legal_moves_safe() (simulate+undo), ChessWinCondition with timed "IN CHECK!" banner and permanent checkmate/stalemate messages.

- Pluggable win conditions — ChessWinCondition and CheckersWinCondition are swappable via game.win_condition. Checkers logic preserved, not removed.

- SVG icons — 8 SVG templates with {fill}/{stroke} placeholders. Colourised at runtime via a pure-Python renderer — no native library dependencies.

- Save / load — press S/L (or click buttons) to persist and restore game state to JSON.

- Custom layouts — pre-game picker reads `Chess/defs/layouts/*.json`; ships Standard Chess and Standard Checkers; drop in your own JSON to add a variant.

- Tests — 87% line coverage, 200+ tests across per-module test files.

❌ Not Started (the "Mega" vision)

- Custom piece rules editor (in-game editor to tweak move_rules and save variants)
