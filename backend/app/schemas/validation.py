"""Shared string-trimming helpers for the Pydantic schemas.

Two helpers, and the difference between them is the whole point of this module:

- `strip_text` — for **required** fields. Trims, and rejects anything that trims
  to nothing.
- `strip_optional` — for **optional** fields. Trims, and allows blank/`None`,
  because omitting a field and clearing it are different intents on a PATCH.

**Why the strict one is needed.** Pydantic checks `min_length` *before* an
`after`-mode `field_validator` runs. A field declared
`name: str = Field(min_length=1)` therefore accepts `"   "`: the length check sees
three characters and passes, then the validator trims it to `""` and stores that.
The column is `NOT NULL`, not non-empty, so the empty string lands in the database
and the row is only discoverable by querying for it. `strip_text` closes that gap;
`min_length` alone cannot.

`EmailStr` fields need neither helper — Pydantic's own email validation already
rejects whitespace-only input.
"""

from __future__ import annotations


def strip_text(value: str | None) -> str | None:
    """Trim surrounding whitespace and reject a value that trims to nothing.

    Raises:
        ValueError: if `value` is a string that is empty or all whitespace.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be blank")
    return stripped


def strip_optional(value: str | None) -> str | None:
    """Trim surrounding whitespace, allowing `None` and an empty result.

    Used for optional text (`description`, `rules`, `notes`, and the nullable
    fields on the `*_api` update schemas), where a client may legitimately send
    `""` to clear a value.
    """
    return value.strip() if value else value
