from __future__ import annotations

import functools
import importlib
import logging

logger = logging.getLogger(__name__)

_PATCH_APPLIED = False
# Set to True to disable the patch (for debugging)
_PATCH_DISABLED = False


def apply_gmaps_patch() -> None:
    """
    Apply a runtime patch to ``ghunt.helpers.gmaps.get_reviews`` to make it
    resilient to the known ``data[24]`` IndexError/TypeError issue.

    The underlying GHunt helper accesses ``data[24]`` without a length check.
    When the response has fewer entries, this raises and breaks our email
    lookup flow. We can't easily modify the third‑party library on disk, so
    we monkey‑patch the function at import time and safely degrade to an
    "empty" result instead of crashing.
    """
    global _PATCH_APPLIED, _PATCH_DISABLED

    if _PATCH_DISABLED:
        logger.info("GHunt gmaps patch is disabled (for debugging)")
        return

    if _PATCH_APPLIED:
        return

    try:
        gmaps_module = importlib.import_module("ghunt.helpers.gmaps")

        original_get_reviews = getattr(gmaps_module, "get_reviews", None)
        if original_get_reviews is None:
            logger.warning(
                "GHunt gmaps patch: 'get_reviews' not found in 'ghunt.helpers.gmaps'"
            )
            return

        # Avoid double‑patching
        if getattr(original_get_reviews, "_ghunt_patched", False):
            _PATCH_APPLIED = True
            logger.debug("GHunt gmaps patch: 'get_reviews' already patched")
            return

        @functools.wraps(original_get_reviews)
        async def patched_get_reviews(client, gaia_id, *args, **kwargs):
            """
            Wrapper around the original ``get_reviews`` that catches the
            specific IndexError/TypeError caused by unsafe ``data[24]`` access
            and returns an "empty" result instead of raising.

            Return format mirrors GHunt's:
                (error_status, stats, reviews, photos)
            """
            logger.debug(
                f"GHunt gmaps patch: Calling original_get_reviews for gaia_id={gaia_id}"
            )
            try:
                result = await original_get_reviews(client, gaia_id, *args, **kwargs)
                logger.debug(
                    f"GHunt gmaps patch: original_get_reviews succeeded for gaia_id={gaia_id}, "
                    f"result type={type(result)}, error_status={result[0] if isinstance(result, tuple) and len(result) > 0 else 'N/A'}"
                )
                return result
            except IndexError as e:
                # This is the failure you're seeing from the library.
                # Check if it's likely the data[24] issue by inspecting the error
                import traceback

                tb_str = "".join(traceback.format_exc())

                error_str = str(e)
                error_msg_lower = error_str.lower()

                # Check if it's an index out of range error (likely data[24])
                # Also check the traceback for "gmaps" or "helpers" to confirm it's from the right place
                is_likely_data24_error = (
                    "index out of range" in error_msg_lower
                    or "list index" in error_msg_lower
                ) and ("gmaps" in tb_str.lower() or "helpers" in tb_str.lower())

                if is_likely_data24_error:
                    logger.warning(
                        "GHunt gmaps IndexError (likely data[24] issue) while fetching reviews "
                        "for gaia_id=%s: %s. Returning empty result instead.\nTraceback:\n%s",
                        gaia_id,
                        e,
                        tb_str,
                    )
                    return ("empty", {}, [], [])
                else:
                    # Re-raise if it's a different IndexError
                    logger.error(
                        "GHunt gmaps IndexError (unexpected) for gaia_id=%s: %s\nTraceback:\n%s",
                        gaia_id,
                        e,
                        tb_str,
                        exc_info=True,
                    )
                    raise
            except TypeError as e:
                # Defensive: in case library code treats missing entries as None
                msg = str(e).lower()
                if "none" in msg or "subscriptable" in msg:
                    logger.warning(
                        "GHunt gmaps TypeError while fetching reviews for gaia_id=%s: %s. "
                        "Returning empty result instead.",
                        gaia_id,
                        e,
                    )
                    return ("empty", {}, [], [])
                logger.error(
                    "GHunt gmaps TypeError (unexpected) for gaia_id=%s: %s",
                    gaia_id,
                    e,
                    exc_info=True,
                )
                raise
            except Exception as e:
                # Log any other unexpected exceptions
                logger.error(
                    "GHunt gmaps unexpected exception for gaia_id=%s: %s",
                    gaia_id,
                    e,
                    exc_info=True,
                )
                raise

        # Mark wrapper so we don't wrap twice
        patched_get_reviews._ghunt_patched = True  # type: ignore[attr-defined]

        gmaps_module.get_reviews = patched_get_reviews

        _PATCH_APPLIED = True
        logger.info(
            "GHunt gmaps patch applied successfully. "
            f"Original function: {original_get_reviews}, "
            f"Patched function: {patched_get_reviews}"
        )

        # Verify the patch was applied
        current_get_reviews = getattr(gmaps_module, "get_reviews", None)
        if current_get_reviews is not patched_get_reviews:
            logger.error(
                "GHunt gmaps patch verification failed! "
                f"Expected {patched_get_reviews}, got {current_get_reviews}"
            )
        else:
            logger.debug("GHunt gmaps patch verification successful")

    except Exception as e:  # pragma: no cover - defensive logging
        logger.error("Failed to apply GHunt gmaps patch: %s", e, exc_info=True)


# Apply on import so any later "from ghunt.helpers.gmaps import get_reviews"
# will receive the patched version.
apply_gmaps_patch()
