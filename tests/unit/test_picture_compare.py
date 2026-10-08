"""Two pictures are compared as a person would see them, not byte for byte (tests/support/pictures.py)."""

import pytest
from pictures import SAME_TO_THE_EYE, a_png, furthest_apart, look_the_same, rows_of

GREY = (213, 213, 213)
PAGE = [[GREY, GREY, GREY, GREY], [GREY, (255, 255, 255), (255, 255, 255), GREY], [GREY, GREY, GREY, GREY]]


def with_pixel(pixel: tuple[int, int, int]) -> list[list[tuple[int, int, int]]]:
    changed = [list(row) for row in PAGE]
    changed[0][3] = pixel
    return changed


def test_a_picture_is_read_back_as_the_pixels_it_was_made_of() -> None:
    rows, channels = rows_of(a_png(PAGE))
    assert channels == 3 and len(rows) == 3
    assert rows[1] == bytes([213, 213, 213, 255, 255, 255, 255, 255, 255, 213, 213, 213])


def test_the_same_picture_is_no_distance_from_itself() -> None:
    assert furthest_apart(a_png(PAGE), a_png(PAGE)) == 0
    assert look_the_same(a_png(PAGE), a_png(PAGE))


def test_a_corner_drawn_one_shade_darker_is_the_same_picture_to_a_person() -> None:
    """What a browser on another machine did: one pixel of a rounded corner, 213 to 212."""
    redrawn = a_png(with_pixel((212, 212, 212)))
    assert redrawn != a_png(PAGE), "the bytes are not the same"
    assert furthest_apart(a_png(PAGE), redrawn) == 1
    assert look_the_same(a_png(PAGE), redrawn)


def test_a_label_left_on_the_page_is_not_the_same_picture() -> None:
    """A label is drawn in a strong red. One pixel of it is far from the page under it."""
    labelled = a_png(with_pixel((179, 38, 30)))
    assert furthest_apart(a_png(PAGE), labelled) == 183
    assert not look_the_same(a_png(PAGE), labelled)


def test_the_edge_of_what_a_person_can_see() -> None:
    at_the_edge = a_png(with_pixel((213 - SAME_TO_THE_EYE, 213, 213)))
    past_it = a_png(with_pixel((213 - SAME_TO_THE_EYE - 1, 213, 213)))
    assert look_the_same(a_png(PAGE), at_the_edge) and not look_the_same(a_png(PAGE), past_it)


def test_pictures_of_two_sizes_are_not_compared() -> None:
    with pytest.raises(ValueError, match="not of one size"):
        furthest_apart(a_png(PAGE), a_png(PAGE[:2]))
    with pytest.raises(ValueError, match="not a PNG"):
        rows_of(b"GIF89a")
