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

## Here's where things stand:

✅ Done

- Data-driven movement — PieceMoves reads move_rules from JSON. No hardcoded per-piece methods. All 6 chess pieces + 2 checkers pieces fully defined.

- Check / checkmate — board.is_in_check(), legal_moves_safe() (simulate+undo), ChessWinCondition with timed "IN CHECK!" banner and permanent checkmate/stalemate messages.

- Pluggable win conditions — ChessWinCondition and CheckersWinCondition are swappable via game.win_condition. Checkers logic preserved, not removed.

- SVG icons — 8 SVG templates with {fill}/{stroke} placeholders. Colourised at runtime via cairosvg — one file per piece, no colour duplicates.

⚠️ Stubbed / Incomplete

- Pawn promotion — board.king() exists but is pass

- En passant & castling — not modelled

- Tests — PieceMoves is untested, coverage sits around 40%

❌ Not Started (the "Mega" vision)

- Runtime board/piece customisation UI

- Save/load configurations
