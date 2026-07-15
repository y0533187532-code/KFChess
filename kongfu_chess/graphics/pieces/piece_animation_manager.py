from .piece_assets import piece_token_to_asset_name
from .piece_animator import PieceAnimator


class PieceAnimationManager:
    def __init__(self) -> None:
        self._animators_by_piece_id: dict[int, PieceAnimator] = {}

    @property
    def animators_by_piece_id(self) -> dict[int, PieceAnimator]:
        return self._animators_by_piece_id

    def animator_for(
        self,
        piece_id: int,
        piece_token: str,
        state: str,
    ) -> PieceAnimator:
        piece_name = piece_token_to_asset_name(piece_token)
        animator = self._animators_by_piece_id.get(piece_id)

        if animator is None:
            animator = PieceAnimator(piece_name, state)
            self._animators_by_piece_id[piece_id] = animator
            return animator

        if animator.piece_name != piece_name:
            animator = PieceAnimator(piece_name, state)
            self._animators_by_piece_id[piece_id] = animator
            return animator

        if animator.state_name != state:
            animator.change_state(state)

        return animator

    def frame_for(
        self,
        piece_id: int,
        piece_token: str,
        state: str,
    ):
        animator = self.animator_for(piece_id, piece_token, state)
        return animator.frame_at()
