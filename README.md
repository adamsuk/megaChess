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

## Piece editor

From the main menu press **E** (or click "Edit Pieces") to open the piece editor.

- **Left panel** — list of piece types. Click to select.
- **Right panel** — move rules for the selected piece. Each boolean flag (`sliding`, `directional`, `move_only`, `capture_only`, `jump_capture`) is shown as a toggle button. Click to flip it.
- **Clone** — duplicate the selected piece as `<name>_custom` so you can tweak it without losing the original.
- **Reset** — restore all piece definitions to the bundled defaults.
- **Save** — write the current definitions to `Chess/defs/custom_pieces.json`. The next game uses these rules.
- **Play** — return to the game using the current (possibly unsaved) definitions.

Press **Esc** or click **← Back** to return to the main menu without saving.

## Here's where things stand:

✅ Done

- Data-driven movement — PieceMoves reads move_rules from JSON. No hardcoded per-piece methods. All 6 chess pieces + 2 checkers pieces fully defined.

- Full chess rules — castling, en passant, pawn promotion all implemented.

- Check / checkmate — board.is_in_check(), legal_moves_safe() (simulate+undo), ChessWinCondition with timed "IN CHECK!" banner and permanent checkmate/stalemate messages.

- Pluggable win conditions — ChessWinCondition and CheckersWinCondition are swappable via game.win_condition. Checkers logic preserved, not removed.

- SVG icons — 8 SVG templates with {fill}/{stroke} placeholders. Colourised at runtime via a pure-Python renderer — no native library dependencies.

- Save / load — press S/L (or click buttons) to persist and restore game state to JSON.

- Piece editor — in-game UI to toggle move_rule flags (sliding, directional, etc.), clone pieces, and save custom variants to JSON.

- Tests — 87% line coverage, 210+ tests across per-module test files.

❌ Not Started (the "Mega" vision)

- Custom board layouts (pre-game layout picker UI backed by JSON)
