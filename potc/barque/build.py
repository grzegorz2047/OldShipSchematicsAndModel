#!/usr/bin/env python3
"""Build the researched family with scoped end-bearing assembly clearance."""
from pathlib import Path
import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
from v5_shipkit import build
import v5_decks as _decks


def _build_with_bearing_clearance():
    original_beams = _decks._beams

    def end_bearings(ctx, deck_id, a, b, baseline, *args, **kwargs):
        # The adjacent same-level cabin/hold soles share a floor seam. Keep
        # their separate 140mm beams and 130mm knees genuinely apart; the
        # forecastle end knees also stand clear of the 75mm breakwall. Only
        # bearing stations move 120mm inward: floors and door bounds stay put.
        if ctx.spec.get("id") == "barque" and deck_id in {"hold", "cabin_sole", "castle_1"}:
            inset = .12
            if b - a <= 2 * inset:
                raise ValueError("Insufficient room span for the authored end-bearing clearance")
            a, b = a + inset, b - inset
        return original_beams(ctx, deck_id, a, b, baseline, *args, **kwargs)

    _decks._beams = end_bearings
    try:
        return build(HERE / "spec.json", HERE)
    finally:
        _decks._beams = original_beams


if __name__ == "__main__":
    _build_with_bearing_clearance()
