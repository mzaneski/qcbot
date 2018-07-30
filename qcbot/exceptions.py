class CommandError(Exception):
    """Errors from invalid user input."""
    pass

class MatchError(Exception):
    """Errors due to invalid PUG
    operations (e.g. trying to join
    a lobby that is full).
    """
    pass