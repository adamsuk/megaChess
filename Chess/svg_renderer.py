"""
Minimal SVG renderer for piece icon templates.

Uses only Python stdlib (xml.etree.ElementTree) and pygame.draw — no native
library dependencies, so it works on every platform pygame supports including
Android (Pydroid3).

Handles the four element types present in assets/pieces/*.svg:
  <circle>, <rect>, <polygon>, <line>

Coordinates are scaled from the SVG's viewBox to the requested output size.
"""
import xml.etree.ElementTree as ET
import pygame


def _parse_color(value):
    """Convert a #RRGGBB hex string to (R, G, B, 255), or None for 'none'."""
    if not value or value == 'none':
        return None
    v = value.strip()
    if v.startswith('#'):
        h = v[1:]
        if len(h) == 3:
            h = h[0] * 2 + h[1] * 2 + h[2] * 2
        return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
    return None


def render_svg(svg_string, size):
    """
    Parse svg_string and draw it onto a new transparent pygame Surface of `size`.

    Args:
        svg_string: SVG markup as a string (with {fill}/{stroke} already substituted).
        size: (width, height) tuple in pixels.

    Returns:
        A pygame.Surface with SRCALPHA transparency.
    """
    root = ET.fromstring(svg_string)

    vb = root.get('viewBox', '0 0 80 80').split()
    vb_w, vb_h = float(vb[2]), float(vb[3])
    sx = size[0] / vb_w
    sy = size[1] / vb_h

    surface = pygame.Surface(size, pygame.SRCALPHA)
    surface.fill((0, 0, 0, 0))

    for elem in root.iter():
        tag = elem.tag.split('}')[-1]  # strip XML namespace if present

        fill   = _parse_color(elem.get('fill',   'none'))
        stroke = _parse_color(elem.get('stroke', 'none'))
        sw     = max(1, round(float(elem.get('stroke-width', '1'))))

        if tag == 'circle':
            cx = round(float(elem.get('cx', 0)) * sx)
            cy = round(float(elem.get('cy', 0)) * sy)
            r  = round(float(elem.get('r',  0)) * min(sx, sy))
            if r > 0:
                if fill:   pygame.draw.circle(surface, fill,   (cx, cy), r)
                if stroke: pygame.draw.circle(surface, stroke, (cx, cy), r, sw)

        elif tag == 'rect':
            x  = round(float(elem.get('x',      0)) * sx)
            y  = round(float(elem.get('y',      0)) * sy)
            w  = round(float(elem.get('width',  0)) * sx)
            h  = round(float(elem.get('height', 0)) * sy)
            rx = round(float(elem.get('rx',     0)) * sx)
            if w > 0 and h > 0:
                if fill:   pygame.draw.rect(surface, fill,   (x, y, w, h), border_radius=rx)
                if stroke: pygame.draw.rect(surface, stroke, (x, y, w, h), sw, border_radius=rx)

        elif tag == 'polygon':
            pairs = elem.get('points', '').split()
            pts = []
            for pair in pairs:
                px_str, py_str = pair.split(',')
                pts.append((round(float(px_str) * sx), round(float(py_str) * sy)))
            if len(pts) >= 3:
                if fill:   pygame.draw.polygon(surface, fill,   pts)
                if stroke: pygame.draw.polygon(surface, stroke, pts, sw)

        elif tag == 'line':
            x1 = round(float(elem.get('x1', 0)) * sx)
            y1 = round(float(elem.get('y1', 0)) * sy)
            x2 = round(float(elem.get('x2', 0)) * sx)
            y2 = round(float(elem.get('y2', 0)) * sy)
            if stroke:
                pygame.draw.line(surface, stroke, (x1, y1), (x2, y2), sw)

    return surface
