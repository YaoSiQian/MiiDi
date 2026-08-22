import pytest

from miidi.schema.chords import ChordParseError, chord_root_degree, parse_chord


@pytest.mark.parametrize(
    "symbol,root,pcs",
    [
        ("C", 0, frozenset({0, 4, 7})),
        ("Am", 9, frozenset({9, 0, 4})),
        ("G7", 7, frozenset({7, 11, 2, 5})),
        ("Cmaj7", 0, frozenset({0, 4, 7, 11})),
        ("Dm7", 2, frozenset({2, 5, 9, 0})),
        ("Bdim", 11, frozenset({11, 2, 5})),
        ("Bm7b5", 11, frozenset({11, 2, 5, 9})),
        ("Cdim7", 0, frozenset({0, 3, 6, 9})),
        ("Caug", 0, frozenset({0, 4, 8})),
        ("Gsus4", 7, frozenset({7, 0, 2})),
        ("Asus2", 9, frozenset({9, 11, 4})),
        ("Cadd9", 0, frozenset({0, 2, 4, 7})),
        ("C6", 0, frozenset({0, 4, 7, 9})),
        ("Am6", 9, frozenset({9, 0, 4, 6})),
        ("F#m", 6, frozenset({6, 9, 1})),
        ("Bb", 10, frozenset({10, 2, 5})),
        ("Eb7", 3, frozenset({3, 7, 10, 1})),
        ("G5", 7, frozenset({7, 2})),
    ],
)
def test_parse_known_symbols(symbol, root, pcs):
    info = parse_chord(symbol)
    assert info.root_pc == root
    assert info.pcs == pcs


@pytest.mark.parametrize("symbol", ["H7", "xyz", "Cmaj9", "Fsus", "", "C##", "7"])
def test_invalid_symbols_raise(symbol):
    with pytest.raises(ChordParseError):
        parse_chord(symbol)


def test_case_insensitive_root():
    assert parse_chord("am").root_pc == 9


def test_root_degree():
    assert chord_root_degree(parse_chord("G"), 0) == 7
    assert chord_root_degree(parse_chord("F"), 0) == 5
    assert chord_root_degree(parse_chord("Em"), 9) == 7
