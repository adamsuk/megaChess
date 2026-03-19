"""
Minimal SVG renderer for piece icon templates.

Uses only Python stdlib (xml.etree.ElementTree, re) and pygame.draw — no
native library dependencies, works on every platform pygame supports including
Android (Pydroid3).

Supported elements: <circle>, <rect>, <polygon>, <line>, <path>
Path commands: M/m, L/l, H/h, V/v, C/c, Q/q, Z/z

Coordinates are scaled from the SVG's viewBox to the requested output size.
"""
import re
import xml.etree.ElementTree as ET
import pygame

_TOKEN_RE = re.compile(
    r'[MmLlCcQqHhVvZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?'
)


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


def _parse_path(d, sx, sy):
    """
    Parse an SVG path 'd' string and return a list of scaled polygon point
    lists (one list per sub-path, ready to pass to pygame.draw.polygon).

    Bezier curves are approximated with 16-step line segments.
    """
    tokens = _TOKEN_RE.findall(d.replace(',', ' '))

    subpaths = []
    pts      = []
    cx = cy  = 0.0   # current pen position
    x0 = y0  = 0.0   # start of current sub-path (for Z)
    cmd      = 'M'
    i        = 0

    def add(x, y):
        pts.append((x * sx, y * sy))

    def cbez(x1, y1, x2, y2, x3, y3):
        nonlocal cx, cy
        ox, oy = cx, cy
        for n in range(1, 17):
            t = n / 16
            u = 1 - t
            add(u**3*ox + 3*u**2*t*x1 + 3*u*t**2*x2 + t**3*x3,
                u**3*oy + 3*u**2*t*y1 + 3*u*t**2*y2 + t**3*y3)
        cx, cy = x3, y3

    def qbez(x1, y1, x2, y2):
        nonlocal cx, cy
        ox, oy = cx, cy
        for n in range(1, 11):
            t = n / 10
            u = 1 - t
            add(u**2*ox + 2*u*t*x1 + t**2*x2,
                u**2*oy + 2*u*t*y1 + t**2*y2)
        cx, cy = x2, y2

    def close():
        nonlocal cx, cy
        if pts:
            subpaths.append(pts[:])
            pts.clear()
        cx, cy = x0, y0

    while i < len(tokens):
        tok = tokens[i]
        if tok in 'MmLlCcQqHhVvZz':
            cmd = tok
            i += 1
            if cmd in ('Z', 'z'):
                close()
            continue

        # Collect all consecutive numbers for this command
        nums = []
        while i < len(tokens) and tokens[i] not in 'MmLlCcQqHhVvZz':
            nums.append(float(tokens[i]))
            i += 1

        j = 0
        while j < len(nums):
            if cmd == 'M':
                if pts: subpaths.append(pts[:]); pts.clear()
                cx, cy = nums[j], nums[j+1]; j += 2
                x0, y0 = cx, cy; add(cx, cy); cmd = 'L'
            elif cmd == 'm':
                if pts: subpaths.append(pts[:]); pts.clear()
                cx, cy = cx+nums[j], cy+nums[j+1]; j += 2
                x0, y0 = cx, cy; add(cx, cy); cmd = 'l'
            elif cmd == 'L':
                cx, cy = nums[j], nums[j+1]; j += 2; add(cx, cy)
            elif cmd == 'l':
                cx, cy = cx+nums[j], cy+nums[j+1]; j += 2; add(cx, cy)
            elif cmd == 'H':
                cx = nums[j]; j += 1; add(cx, cy)
            elif cmd == 'h':
                cx += nums[j]; j += 1; add(cx, cy)
            elif cmd == 'V':
                cy = nums[j]; j += 1; add(cx, cy)
            elif cmd == 'v':
                cy += nums[j]; j += 1; add(cx, cy)
            elif cmd == 'C':
                cbez(nums[j],nums[j+1], nums[j+2],nums[j+3], nums[j+4],nums[j+5])
                j += 6
            elif cmd == 'c':
                cbez(cx+nums[j],cy+nums[j+1], cx+nums[j+2],cy+nums[j+3],
                     cx+nums[j+4],cy+nums[j+5])
                j += 6
            elif cmd == 'Q':
                qbez(nums[j],nums[j+1], nums[j+2],nums[j+3]); j += 4
            elif cmd == 'q':
                qbez(cx+nums[j],cy+nums[j+1], cx+nums[j+2],cy+nums[j+3]); j += 4
            else:
                j += 1

    if pts:
        subpaths.append(pts)

    return subpaths


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
            x_r = float(elem.get('x',      0))
            y_r = float(elem.get('y',      0))
            w_r = float(elem.get('width',  0))
            h_r = float(elem.get('height', 0))
            x  = round(x_r * sx)
            y  = round(y_r * sy)
            # Derive w/h from rounded end-coords so adjacent rects tile with no gaps
            w  = round((x_r + w_r) * sx) - x
            h  = round((y_r + h_r) * sy) - y
            rx = round(float(elem.get('rx', 0)) * sx)
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

        elif tag == 'path':
            for subpath in _parse_path(elem.get('d', ''), sx, sy):
                if len(subpath) >= 3:
                    pts = [(round(x), round(y)) for x, y in subpath]
                    if fill:   pygame.draw.polygon(surface, fill,   pts)
                    if stroke: pygame.draw.polygon(surface, stroke, pts, sw)

    return surface
