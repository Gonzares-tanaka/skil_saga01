"""Developer shortcuts require explicit startup; distribution builds lock them out."""
import sys

DEVELOPMENT_BUILD = True


def development_enabled(requested):
    return bool(requested) and DEVELOPMENT_BUILD and sys.platform != 'emscripten'
