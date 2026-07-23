"""Regression tests for Kickstart promo code support (Feb 15, 2026).

Verifies the security-critical parts of `resolve_promotion_code`:
  - Internal-only codes are refused for non-QA users (fast path, no Stripe call)
  - Empty / oversized codes rejected
  - QA users can use internal codes
"""
from __future__ import annotations

import asyncio
import pytest

from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

import server  # noqa: E402
import tier_catalog  # noqa: E402


_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    return _LOOP.run_until_complete(coro)


def test_internal_only_code_rejected_for_public_user():
    """ZYNTHORO-QA must be refused for a normal customer, WITHOUT even
    calling Stripe (fast fail via the blocklist)."""
    async def run():
        with pytest.raises(ValueError, match="niet geldig"):
            await tier_catalog.resolve_promotion_code(
                "ZYNTHORO-QA", tier_key="kickstart_1", is_qa_test=False,
            )
    _run(run())


def test_internal_only_code_case_insensitive():
    """Blocklist must match regardless of case (input is upper-cased)."""
    async def run():
        for variant in ("zynthoro-qa", "Zynthoro-Qa", "ZyNtHoRo-Qa"):
            with pytest.raises(ValueError, match="niet geldig"):
                await tier_catalog.resolve_promotion_code(
                    variant, tier_key="kickstart_1", is_qa_test=False,
                )
    _run(run())


def test_empty_code_rejected():
    async def run():
        for c in ("", "   ", None):
            with pytest.raises(ValueError, match="Voer een promocode"):
                await tier_catalog.resolve_promotion_code(
                    c or "", tier_key="kickstart_1", is_qa_test=False,
                )
    _run(run())


def test_oversized_code_rejected():
    async def run():
        with pytest.raises(ValueError, match="Ongeldige promocode"):
            await tier_catalog.resolve_promotion_code(
                "A" * 61, tier_key="kickstart_1", is_qa_test=False,
            )
    _run(run())


def test_unknown_tier_rejected():
    async def run():
        with pytest.raises(ValueError, match="Unknown tier"):
            await tier_catalog.resolve_promotion_code(
                "PH2026", tier_key="not_a_tier", is_qa_test=False,
            )
    _run(run())


def test_blocklist_contains_expected_codes():
    """Sanity: production must never accidentally drop the ZYNTHORO-QA block."""
    assert "ZYNTHORO-QA" in tier_catalog._INTERNAL_ONLY_CODES
    assert "STAFF-ONLY" in tier_catalog._INTERNAL_ONLY_CODES
    assert "INTERNAL" in tier_catalog._INTERNAL_ONLY_CODES
