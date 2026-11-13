"""Wyjście na konsolę w UTF-8 niezależnie od strony kodowej systemu.

Na Windows konsola bywa w cp1250, cp1252 albo cp852; komunikaty z polskimi literami albo ze znakami takimi jak „→”
kończyły wtedy skrypt błędem UnicodeEncodeError (zwykły Python, poza Blenderem). Wystarczy zaimportować ten moduł.
"""
import sys


def utf8():
    for strumien in (sys.stdout, sys.stderr):
        try:
            strumien.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


utf8()
