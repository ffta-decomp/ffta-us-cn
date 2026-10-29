"""Compatibility import for the locked Info plugin build entry."""
from plugin_projects import load_entry

_implementation = load_entry('info')
globals().update({name: value for name, value in vars(_implementation).items() if not name.startswith('_')})
