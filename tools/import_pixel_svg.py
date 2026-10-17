"""Offline import of static integer-grid artwork. Never imported by the game."""
import xml.etree.ElementTree as ET
import pyxel

COLORS = {'#152b24': 0, '#456849': 1, '#8ead62': 2, '#dbe8a6': 3}


def import_sheet(path, width, height):
    root = ET.parse(path).getroot()
    symbols = {node.get('id'): node for node in root.iter() if node.get('id')}
    sheet = pyxel.Image(width, height)
    def render(node, x=0, y=0):
        tag = node.tag.rsplit('}', 1)[-1]
        if tag == 'defs': return
        if tag == 'use':
            render(symbols[node.get('href')[1:]], x + int(node.get('x', 0)), y + int(node.get('y', 0)))
            return
        if tag in ('svg', 'g'):
            for child in node: render(child, x, y)
            return
        fill, stroke = node.get('fill', 'none'), node.get('stroke')
        color = COLORS[fill] if fill != 'none' else None
        edge = COLORS[stroke] if stroke else None
        if tag == 'rect':
            sheet.rect(x + int(node.get('x')), y + int(node.get('y')),
                       int(node.get('width')), int(node.get('height')), color)
        elif tag == 'line':
            sheet.line(x + int(node.get('x1')), y + int(node.get('y1')),
                       x + int(node.get('x2')), y + int(node.get('y2')), edge)
        elif tag in ('polygon', 'polyline'):
            points = [tuple(map(int, p.split(','))) for p in node.get('points').split()]
            if color is not None:
                for sy in range(min(p[1] for p in points), max(p[1] for p in points) + 1):
                    crossings = []
                    for (ax, ay), (bx, by) in zip(points, points[1:] + points[:1]):
                        if min(ay, by) <= sy < max(ay, by):
                            crossings.append(ax + (sy - ay) * (bx - ax) / (by - ay))
                    crossings.sort()
                    for a, b in zip(crossings[::2], crossings[1::2]):
                        sheet.line(x + round(a), y + sy, x + round(b), y + sy, color)
                for a, b in zip(points, points[1:] + points[:1]):
                    sheet.line(x + a[0], y + a[1], x + b[0], y + b[1], color)
            if edge is not None:
                following = points[1:] + points[:1] if tag == 'polygon' else points[1:]
                for a, b in zip(points, following):
                    sheet.line(x + a[0], y + a[1], x + b[0], y + b[1], edge)
        else:
            raise ValueError('Unsupported static artwork element: ' + tag)
    render(root)
    return sheet
