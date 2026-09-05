"""Legacy helper retained as documentation only.

The integrated FastAPI adapter is maintained directly under ``api/``. This
file intentionally does not regenerate API files because doing so could
overwrite the validated adapter with an older fixture-only implementation.
"""


def main() -> None:
    print("API adapter is maintained in backend/api; no files were regenerated.")


if __name__ == "__main__":
    main()
