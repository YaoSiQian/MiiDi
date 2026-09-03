"""Shared utilities for MIDI analysis tools."""
import os


def find_midi_files(root: str) -> list[str]:
    """Recursively find all .mid files under root."""
    files = []
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            if f.lower().endswith(".mid"):
                files.append(os.path.join(dirpath, f))
    return sorted(files)
