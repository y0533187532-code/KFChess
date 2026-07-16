import cv2
import numpy as np
import pytest

from kongfu_chess.graphics.img import Img


def _write_image(path, array):
    assert cv2.imwrite(str(path), array)


def test_read_resizes_exact_size(tmp_path):
    image_path = tmp_path / "sample.png"
    source = np.zeros((10, 20, 4), dtype=np.uint8)
    _write_image(image_path, source)

    image = Img().read(image_path, size=(8, 6))

    assert image.img.shape[:2] == (6, 8)


def test_read_keep_aspect_scales_longer_side(tmp_path):
    image_path = tmp_path / "sample.png"
    source = np.zeros((10, 20, 4), dtype=np.uint8)
    _write_image(image_path, source)

    image = Img().read(image_path, size=(8, 8), keep_aspect=True)

    assert image.img.shape[:2] == (4, 8)


def test_read_missing_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        Img().read("missing-file.png")


def test_draw_on_alpha_blends_into_target():
    background = Img()
    background.img = np.zeros((4, 4, 4), dtype=np.uint8)

    foreground = Img()
    foreground.img = np.zeros((2, 2, 4), dtype=np.uint8)
    foreground.img[..., 2] = 200
    foreground.img[..., 3] = 255

    foreground.draw_on(background, 1, 1)

    assert np.array_equal(background.img[1:3, 1:3, 2], np.full((2, 2), 200, dtype=np.uint8))


def test_draw_on_converts_channel_count_when_needed():
    background = Img()
    background.img = np.zeros((4, 4, 4), dtype=np.uint8)

    foreground = Img()
    foreground.img = np.zeros((2, 2, 3), dtype=np.uint8)
    foreground.img[..., 1] = 150

    foreground.draw_on(background, 0, 0)

    assert foreground.img.shape[2] == 4
    assert np.array_equal(background.img[0:2, 0:2, 1], np.full((2, 2), 150, dtype=np.uint8))


def test_draw_on_raises_when_sprite_does_not_fit():
    background = Img()
    background.img = np.zeros((2, 2, 4), dtype=np.uint8)

    foreground = Img()
    foreground.img = np.zeros((2, 2, 4), dtype=np.uint8)

    with pytest.raises(ValueError):
        foreground.draw_on(background, 1, 1)


def test_draw_on_clips_when_sprite_starts_above_target():
    background = Img()
    background.img = np.zeros((4, 4, 4), dtype=np.uint8)

    foreground = Img()
    foreground.img = np.zeros((4, 2, 4), dtype=np.uint8)
    foreground.img[..., 1] = 180
    foreground.img[..., 3] = 255

    foreground.draw_on(background, 1, -2)

    assert np.array_equal(background.img[0:2, 1:3, 1], np.full((2, 2), 180, dtype=np.uint8))
    assert np.count_nonzero(background.img[2:, :, 1]) == 0


def test_draw_on_clips_when_sprite_starts_left_of_target():
    background = Img()
    background.img = np.zeros((4, 4, 4), dtype=np.uint8)

    foreground = Img()
    foreground.img = np.zeros((2, 4, 4), dtype=np.uint8)
    foreground.img[..., 0] = 120
    foreground.img[..., 3] = 255

    foreground.draw_on(background, -2, 1)

    assert np.array_equal(background.img[1:3, 0:2, 0], np.full((2, 2), 120, dtype=np.uint8))
    assert np.count_nonzero(background.img[:, 2:, 0]) == 0


def test_draw_on_returns_when_sprite_is_fully_above_target():
    background = Img()
    background.img = np.zeros((4, 4, 4), dtype=np.uint8)

    foreground = Img()
    foreground.img = np.ones((2, 2, 4), dtype=np.uint8) * 255

    foreground.draw_on(background, 1, -5)

    assert np.count_nonzero(background.img) == 0


def test_draw_on_requires_loaded_images():
    with pytest.raises(ValueError):
        Img().draw_on(Img(), 0, 0)


def test_show_requires_loaded_image():
    with pytest.raises(ValueError):
        Img().show()


def test_show_frame_requires_loaded_image():
    with pytest.raises(ValueError):
        Img().show_frame()


def test_put_text_requires_loaded_image():
    with pytest.raises(ValueError):
        Img().put_text("score", 0, 0, 1.0)


def test_put_text_changes_loaded_image():
    image = Img()
    image.img = np.zeros((40, 80, 4), dtype=np.uint8)

    image.put_text("A", 5, 20, 0.5)

    assert np.count_nonzero(image.img) > 0


def test_blank_creates_solid_color_image():
    image = Img().blank(width=5, height=3, color=(1, 2, 3, 4))

    assert image.img.shape == (3, 5, 4)
    assert np.array_equal(image.img[0, 0], np.array([1, 2, 3, 4], dtype=np.uint8))
    assert np.array_equal(image.img[-1, -1], np.array([1, 2, 3, 4], dtype=np.uint8))
