TOKEN_COLOR_INDEX = 0
TOKEN_PIECE_TYPE_INDEX = 1


def piece_token_to_asset_name(token: str) -> str:
    """Convert logical tokens such as 'wK' into asset names such as 'KW'."""
    color = token[TOKEN_COLOR_INDEX].upper()
    piece_type = token[TOKEN_PIECE_TYPE_INDEX].upper()
    return f"{piece_type}{color}"