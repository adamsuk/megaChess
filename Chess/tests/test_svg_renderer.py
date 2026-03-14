"""Tests for svg_renderer.py — _parse_color, _parse_path, render_svg."""
import os
import sys

os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('SDL_AUDIODRIVER', 'dummy')

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import unittest
import pygame
pygame.init()
pygame.display.set_mode((1, 1))   # required for SRCALPHA surfaces

from svg_renderer import _parse_color, _parse_path, render_svg


# ---------------------------------------------------------------------------
# _parse_color
# ---------------------------------------------------------------------------

class TestParseColor(unittest.TestCase):

    def test_six_digit_hex(self):
        self.assertEqual(_parse_color('#FF8040'), (255, 128, 64, 255))

    def test_black(self):
        self.assertEqual(_parse_color('#000000'), (0, 0, 0, 255))

    def test_white(self):
        self.assertEqual(_parse_color('#FFFFFF'), (255, 255, 255, 255))

    def test_three_digit_hex_expands(self):
        # #F80 → #FF8800
        self.assertEqual(_parse_color('#F80'), (255, 136, 0, 255))

    def test_lowercase_hex(self):
        self.assertEqual(_parse_color('#ff0000'), (255, 0, 0, 255))

    def test_whitespace_stripped(self):
        self.assertEqual(_parse_color('  #FF0000  '), (255, 0, 0, 255))

    def test_none_string_returns_none(self):
        self.assertIsNone(_parse_color('none'))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_color(''))

    def test_none_value_returns_none(self):
        self.assertIsNone(_parse_color(None))

    def test_unknown_format_returns_none(self):
        self.assertIsNone(_parse_color('red'))


# ---------------------------------------------------------------------------
# _parse_path
# ---------------------------------------------------------------------------

class TestParsePath(unittest.TestCase):

    def test_simple_triangle(self):
        result = _parse_path('M 0 0 L 10 0 L 5 10 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)
        self.assertGreaterEqual(len(result[0]), 3)

    def test_scale_applied(self):
        result = _parse_path('M 0 0 L 10 0 L 0 10 Z', 2.0, 3.0)
        pts = result[0]
        self.assertIn((20.0, 0.0), pts)
        self.assertIn((0.0, 30.0), pts)

    def test_empty_path_returns_empty(self):
        self.assertEqual(_parse_path('', 1.0, 1.0), [])

    def test_two_subpaths(self):
        d = 'M 0 0 L 5 0 L 0 5 Z M 10 10 L 15 10 L 10 15 Z'
        self.assertEqual(len(_parse_path(d, 1.0, 1.0)), 2)

    def test_relative_lineto(self):
        result = _parse_path('M 10 10 l 5 0 l 0 5 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)

    def test_horizontal_command(self):
        result = _parse_path('M 0 0 H 10 V 10 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)

    def test_lowercase_hv_commands(self):
        result = _parse_path('M 5 5 h 5 v 5 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)

    def test_implicit_lineto_after_move(self):
        result = _parse_path('M 0 0 10 0 5 10 Z', 1.0, 1.0)
        self.assertGreaterEqual(len(result[0]), 3)

    def test_cubic_bezier_adds_points(self):
        result = _parse_path('M 0 0 C 0 5 10 5 10 0 Z', 1.0, 1.0)
        self.assertGreater(len(result[0]), 3)

    def test_relative_cubic_bezier(self):
        result = _parse_path('M 10 40 c 0 -30 60 -30 60 0 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)

    def test_quadratic_bezier_adds_points(self):
        result = _parse_path('M 0 0 Q 5 10 10 0 Z', 1.0, 1.0)
        self.assertGreater(len(result[0]), 2)

    def test_relative_quadratic_bezier(self):
        result = _parse_path('M 10 70 q 30 -60 60 0 Z', 1.0, 1.0)
        self.assertEqual(len(result), 1)


# ---------------------------------------------------------------------------
# render_svg
# ---------------------------------------------------------------------------

class TestRenderSvg(unittest.TestCase):

    def test_returns_correct_size(self):
        svg = '<svg viewBox="0 0 80 80"></svg>'
        self.assertEqual(render_svg(svg, (64, 64)).get_size(), (64, 64))

    def test_renders_circle(self):
        svg = '<svg viewBox="0 0 80 80"><circle cx="40" cy="40" r="20" fill="#FF0000"/></svg>'
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_renders_circle_with_stroke(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<circle cx="40" cy="40" r="20" fill="#FF0000" stroke="#000000" stroke-width="2"/>'
               '</svg>')
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_zero_radius_circle_skipped(self):
        svg = '<svg viewBox="0 0 80 80"><circle cx="40" cy="40" r="0" fill="#FF0000"/></svg>'
        self.assertIsNotNone(render_svg(svg, (80, 80)))

    def test_renders_rect(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<rect x="10" y="10" width="60" height="60" fill="#00FF00"/>'
               '</svg>')
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_renders_rect_with_stroke_and_rx(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<rect x="5" y="5" width="70" height="70" rx="5"'
               ' fill="#FFFFFF" stroke="#000000" stroke-width="1"/>'
               '</svg>')
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_none_fill_skips_fill_draw(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<rect x="10" y="10" width="60" height="60" fill="none" stroke="#000000"/>'
               '</svg>')
        self.assertIsNotNone(render_svg(svg, (80, 80)))

    def test_renders_polygon(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<polygon points="40,5 5,75 75,75" fill="#0000FF"/>'
               '</svg>')
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_renders_polygon_with_stroke(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<polygon points="40,5 5,75 75,75" fill="none" stroke="#FF0000" stroke-width="2"/>'
               '</svg>')
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_renders_line(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<line x1="0" y1="0" x2="80" y2="80" stroke="#FF0000" stroke-width="2"/>'
               '</svg>')
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_renders_path(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<path d="M 10 10 L 70 10 L 40 70 Z" fill="#FFFF00"/>'
               '</svg>')
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_renders_path_cubic_bezier(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<path d="M 10 40 C 10 10 70 10 70 40 Z" fill="#FF00FF"/>'
               '</svg>')
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_renders_path_quadratic_bezier(self):
        svg = ('<svg viewBox="0 0 80 80">'
               '<path d="M 10 70 Q 40 10 70 70 Z" fill="#00FFFF"/>'
               '</svg>')
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))

    def test_custom_viewbox(self):
        svg = '<svg viewBox="0 0 160 160"></svg>'
        self.assertEqual(render_svg(svg, (80, 80)).get_size(), (80, 80))


if __name__ == '__main__':
    unittest.main(verbosity=2)
