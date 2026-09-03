import pytest

from miidi.musicutil.gm import (
    CLOSED_HAT,
    CRASH,
    KICK,
    OPEN_HAT,
    RIDE,
    SNARE,
    assign_channels,
    play_comf,
)


def test_drum_constants():
    assert (KICK, SNARE, CLOSED_HAT, OPEN_HAT, RIDE, CRASH) == (36, 38, 42, 46, 51, 49)


def test_all_128_covered_and_nested():
    for p in range(128):
        play, comf = play_comf(p)
        assert 0 <= play[0] < play[1] <= 127
        assert play[0] <= comf[0] and comf[1] <= play[1]


def test_known_values():
    assert play_comf(40)[0] == (55, 100)
    assert play_comf(0)[0] == (21, 108)
    assert play_comf(73)[0] == (59, 96)


def test_assign_channels_skips_9():
    chans = assign_channels([False] * 12)
    assert 9 not in chans and len(set(chans)) == 12


def test_drums_pin_to_nine():
    assert assign_channels([False, True, False]) == [0, 9, 1]


def test_too_many_melodic_tracks_raises():
    with pytest.raises(ValueError):
        assign_channels([False] * 16)
