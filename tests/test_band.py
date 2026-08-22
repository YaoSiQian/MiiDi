from miidi.musicutil.band import band, norm_entropy


def test_plateau_is_one():
    assert band(5, 0, 2, 8, 10) == 1.0


def test_ramps():
    assert band(0, 0, 2, 8, 10) == 0.0
    assert band(1, 0, 2, 8, 10) == 0.5
    assert band(10, 0, 2, 8, 10) == 0.0
    assert band(9, 0, 2, 8, 10) == 0.5


def test_floor_parameter():
    assert band(10, 0, 2, 8, 10, floor=0.4) == 0.4
    assert band(-1, 0, 2, 8, 10, floor=0.4) == 0.4


def test_entropy():
    assert norm_entropy([5]) == 0.0
    assert norm_entropy([]) == 0.0
    assert abs(norm_entropy([1, 1]) - 1.0) < 1e-9
    assert 0.0 < norm_entropy([3, 1]) < 1.0
