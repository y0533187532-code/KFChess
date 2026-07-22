"""Re-export shared OpenCV text helpers used by the client shell."""

from ..graphics.text_display import contains_hebrew, prepare_opencv_display_text

__all__ = ["contains_hebrew", "prepare_opencv_display_text"]
