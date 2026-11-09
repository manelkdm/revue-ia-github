"""Validation of environment variables supplied by the runtime."""
import os


def required(key: str) -> str:
    value = os.environ.get(key, "")
    if not value:
        raise ValueError(f"Variable obligatoire absente : {key}")
    return value
