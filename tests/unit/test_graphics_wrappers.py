def test_piece_assets_wrapper_exports_asset_helpers():
    from kongfu_chess.graphics.piece_assets import (
        TOKEN_COLOR_INDEX,
        TOKEN_PIECE_TYPE_INDEX,
        piece_token_to_asset_name,
    )

    assert TOKEN_COLOR_INDEX == 0
    assert TOKEN_PIECE_TYPE_INDEX == 1
    assert piece_token_to_asset_name("wK") == "KW"


def test_graphics_wrapper_modules_export_classes():
    from kongfu_chess.graphics.img import Img
    from kongfu_chess.graphics.move_log import MoveLog
    from kongfu_chess.graphics.piece_animation_manager import PieceAnimationManager
    from kongfu_chess.graphics.piece_animator import PieceAnimator
    from kongfu_chess.graphics.piece_positioner import PiecePositioner
    from kongfu_chess.graphics.player_panel import PlayerPanel

    assert Img.__name__ == "Img"
    assert MoveLog.__name__ == "MoveLog"
    assert PieceAnimationManager.__name__ == "PieceAnimationManager"
    assert PieceAnimator.__name__ == "PieceAnimator"
    assert PiecePositioner.__name__ == "PiecePositioner"
    assert PlayerPanel.__name__ == "PlayerPanel"
