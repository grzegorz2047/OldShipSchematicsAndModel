"""Shared helpers: system font lookup and the few words drawn into pictures."""
import os, sys
from PIL import ImageFont

# Fonts are taken from the operating system; none are shipped with the repository.
_CANDIDATES = {
    'regular': ['segoeui.ttf', 'DejaVuSans.ttf', 'NotoSans-Regular.ttf', 'Arial.ttf', 'arial.ttf',
                'LiberationSans-Regular.ttf', 'Helvetica.ttc'],
    'bold': ['segoeuib.ttf', 'DejaVuSans-Bold.ttf', 'NotoSans-Bold.ttf', 'Arial Bold.ttf', 'arialbd.ttf',
             'LiberationSans-Bold.ttf', 'Helvetica.ttc'],
    'italic': ['segoeuii.ttf', 'DejaVuSans-Oblique.ttf', 'NotoSans-Italic.ttf', 'Arial Italic.ttf', 'ariali.ttf',
               'LiberationSans-Italic.ttf'],
    'title': ['georgiab.ttf', 'DejaVuSerif-Bold.ttf', 'NotoSerif-Bold.ttf', 'Georgia Bold.ttf',
              'LiberationSerif-Bold.ttf', 'segoeuib.ttf', 'DejaVuSans-Bold.ttf'],
    'serif': ['georgia.ttf', 'DejaVuSerif.ttf', 'NotoSerif-Regular.ttf', 'Georgia.ttf',
              'LiberationSerif-Regular.ttf', 'segoeui.ttf', 'DejaVuSans.ttf'],
}

def _font_dirs():
    dirs = []
    win = os.environ.get('WINDIR')
    if win:
        dirs.append(os.path.join(win, 'Fonts'))
    local = os.environ.get('LOCALAPPDATA')
    if local:
        dirs.append(os.path.join(local, 'Microsoft', 'Windows', 'Fonts'))
    home = os.path.expanduser('~')
    dirs += ['/usr/share/fonts', '/usr/local/share/fonts', os.path.join(home, '.fonts'),
             os.path.join(home, '.local', 'share', 'fonts'), '/System/Library/Fonts',
             '/System/Library/Fonts/Supplemental', '/Library/Fonts', os.path.join(home, 'Library', 'Fonts')]
    return [d for d in dirs if os.path.isdir(d)]

_cache = {}
def _find_file(name):
    if name in _cache:
        return _cache[name]
    for d in _font_dirs():
        for root, _, files in os.walk(d):
            if name in files:
                _cache[name] = os.path.join(root, name)
                return _cache[name]
    _cache[name] = None
    return None

def find_font(size, bold=False, style=None):
    style = style or ('bold' if bold else 'regular')
    for name in _CANDIDATES[style]:
        p = _find_file(name)
        if p:
            return ImageFont.truetype(p, size)
    sys.stderr.write('warning: no TrueType font found for %s, using the PIL default\n' % style)
    return ImageFont.load_default(size)

LABELS = {
    'en': {'horizon': 'horizon = your eye level', 'waterline': 'waterline', 'vp': 'VP'},
    'pl': {'horizon': 'horyzont = wysokość twoich oczu', 'waterline': 'linia wody', 'vp': 'PZ'},
}
