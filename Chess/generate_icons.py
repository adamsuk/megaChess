#!/usr/bin/env python3
"""
Generates chess and checkers piece PNG icons using pygame draw primitives.

Run once from the Chess/ directory:
    python generate_icons.py

Produces: assets/pieces/{color}_{piece}.png
Re-run whenever you want to regenerate (e.g. after changing colours/shapes).
"""
import os
import pygame

SIZE = 80          # canvas size in pixels
C    = SIZE // 2   # horizontal centre


def blank():
    s = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    s.fill((0, 0, 0, 0))
    return s


def save(surface, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    pygame.image.save(surface, path)


# ---------------------------------------------------------------------------
# Piece drawers  –  each takes (fill, border) RGB tuples, returns a Surface
# ---------------------------------------------------------------------------

def draw_pawn(f, b):
    s = blank()
    # head
    pygame.draw.circle(s, f, (C, 20), 12)
    pygame.draw.circle(s, b, (C, 20), 12, 2)
    # body
    pts = [(C - 16, 66), (C + 16, 66), (C + 10, 38), (C - 10, 38)]
    pygame.draw.polygon(s, f, pts)
    pygame.draw.polygon(s, b, pts, 2)
    # base
    pygame.draw.rect(s, f, (C - 20, 63, 40, 9), border_radius=4)
    pygame.draw.rect(s, b, (C - 20, 63, 40, 9), 2, border_radius=4)
    return s


def draw_rook(f, b):
    s = blank()
    # column
    pygame.draw.rect(s, f, (C - 12, 28, 24, 36))
    pygame.draw.rect(s, b, (C - 12, 28, 24, 36), 2)
    # battlements (3 merlons)
    for bx in (C - 12, C - 4, C + 4):
        pygame.draw.rect(s, f, (bx, 12, 7, 20))
        pygame.draw.rect(s, b, (bx, 12, 7, 20), 2)
    # base
    pygame.draw.rect(s, f, (C - 18, 62, 36, 10), border_radius=4)
    pygame.draw.rect(s, b, (C - 18, 62, 36, 10), 2, border_radius=4)
    return s


def draw_knight(f, b):
    s = blank()
    pts = [
        (C - 10, 66), (C + 12, 66), (C + 12, 50),
        (C + 18, 38), (C + 16, 26), (C + 8,  14),
        (C -  4, 10), (C - 12, 16), (C - 14, 28),
        (C -  6, 38), (C - 16, 48), (C - 16, 58),
    ]
    pygame.draw.polygon(s, f, pts)
    pygame.draw.polygon(s, b, pts, 2)
    # eye
    pygame.draw.circle(s, b, (C + 6, 20), 3)
    return s


def draw_bishop(f, b):
    s = blank()
    # ball on top
    pygame.draw.circle(s, f, (C, 14), 8)
    pygame.draw.circle(s, b, (C, 14), 8, 2)
    # body
    pts = [(C - 4, 20), (C + 4, 20), (C + 14, 60), (C - 14, 60)]
    pygame.draw.polygon(s, f, pts)
    pygame.draw.polygon(s, b, pts, 2)
    # band
    pygame.draw.line(s, b, (C - 10, 44), (C + 10, 44), 2)
    # base
    pygame.draw.rect(s, f, (C - 18, 58, 36, 10), border_radius=4)
    pygame.draw.rect(s, b, (C - 18, 58, 36, 10), 2, border_radius=4)
    return s


def draw_queen(f, b):
    s = blank()
    # crown points
    pts = [(C - 16, 34), (C - 16, 16), (C - 6, 28), (C, 10),
           (C + 6, 28),  (C + 16, 16), (C + 16, 34)]
    pygame.draw.polygon(s, f, pts)
    pygame.draw.polygon(s, b, pts, 2)
    # balls on crown tips
    for cx2, cy in ((C - 16, 16), (C, 10), (C + 16, 16)):
        pygame.draw.circle(s, f, (cx2, cy), 5)
        pygame.draw.circle(s, b, (cx2, cy), 5, 2)
    # body
    pts2 = [(C - 16, 34), (C + 16, 34), (C + 14, 62), (C - 14, 62)]
    pygame.draw.polygon(s, f, pts2)
    pygame.draw.polygon(s, b, pts2, 2)
    # base
    pygame.draw.rect(s, f, (C - 18, 60, 36, 10), border_radius=4)
    pygame.draw.rect(s, b, (C - 18, 60, 36, 10), 2, border_radius=4)
    return s


def draw_king(f, b):
    s = blank()
    # vertical bar of cross
    pygame.draw.rect(s, f, (C - 4,  6, 8, 24))
    pygame.draw.rect(s, b, (C - 4,  6, 8, 24), 2)
    # horizontal bar of cross
    pygame.draw.rect(s, f, (C - 10, 12, 20, 8))
    pygame.draw.rect(s, b, (C - 10, 12, 20, 8), 2)
    # neck
    pygame.draw.rect(s, f, (C - 8, 28, 16, 10))
    pygame.draw.rect(s, b, (C - 8, 28, 16, 10), 2)
    # body
    pts = [(C - 14, 34), (C + 14, 34), (C + 14, 62), (C - 14, 62)]
    pygame.draw.polygon(s, f, pts)
    pygame.draw.polygon(s, b, pts, 2)
    # base
    pygame.draw.rect(s, f, (C - 18, 60, 36, 10), border_radius=4)
    pygame.draw.rect(s, b, (C - 18, 60, 36, 10), 2, border_radius=4)
    return s


def draw_checkers_man(f, b):
    s = blank()
    pygame.draw.circle(s, f, (C, C), 30)
    pygame.draw.circle(s, b, (C, C), 30, 3)
    pygame.draw.circle(s, b, (C, C), 18, 2)
    return s


def draw_checkers_king(f, b):
    s = blank()
    pygame.draw.circle(s, f, (C, C), 30)
    pygame.draw.circle(s, b, (C, C), 30, 3)
    pygame.draw.circle(s, b, (C, C), 20, 2)
    # crown dots
    for dx, dy in ((0, -20), (-14, -14), (14, -14)):
        pygame.draw.circle(s, b, (C + dx, C + dy), 4)
    return s


# ---------------------------------------------------------------------------

DRAWERS = {
    'pawn':          draw_pawn,
    'rook':          draw_rook,
    'knight':        draw_knight,
    'bishop':        draw_bishop,
    'queen':         draw_queen,
    'king':          draw_king,
    'checkers_man':  draw_checkers_man,
    'checkers_king': draw_checkers_king,
}

COLOURS = {
    'white': ((240, 240, 230), ( 60,  60,  60)),
    'black': (( 40,  30,  30), (200, 200, 200)),
}


def main():
    pygame.init()
    print('Generating piece icons...')
    for piece_name, drawer in DRAWERS.items():
        for color_name, (fill, border) in COLOURS.items():
            path = os.path.join('assets', 'pieces', f'{color_name}_{piece_name}.png')
            save(drawer(fill, border), path)
            print(f'  {path}')
    print('Done.')


if __name__ == '__main__':
    main()
