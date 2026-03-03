"""
Model Cooldown Manager
======================
Tracks rate-limit cooldowns per model, supports user-preferred model,
and auto-resets at midnight (ModelScope daily quota boundary).

Usage:
    from core.model_state import cooldown_manager
    models = cooldown_manager.get_model_order()
"""

import time
from datetime import date
from core.config import (
    MODEL_NAME,
    FALLBACK_MODELS,
    COOLDOWN_HOURS,
    MODEL_DISPLAY_NAMES,
)


class ModelCooldownManager:
    """In-memory singleton managing model cooldown state."""

    def __init__(self):
        self._cooldowns: dict[str, float] = {}  # model -> cooldown_until (unix ts)
        self._preferred: str | None = None
        self._last_reset_date: date = date.today()

    # ── Cooldown ──

    def is_on_cooldown(self, model: str) -> bool:
        until = self._cooldowns.get(model)
        if until is None:
            return False
        if time.time() >= until:
            del self._cooldowns[model]
            return False
        return True

    def set_cooldown(self, model: str, hours: float | None = None):
        h = hours if hours is not None else COOLDOWN_HOURS
        self._cooldowns[model] = time.time() + h * 3600
        print(
            f"[cooldown] {model} 进入 {h}h 冷却 (至 {time.strftime('%H:%M', time.localtime(self._cooldowns[model]))})"
        )

    def reset_all(self):
        self._cooldowns.clear()
        print("[cooldown] 所有模型冷却已重置")

    # ── Preferred model ──

    def set_preferred(self, model: str | None):
        all_models = [MODEL_NAME] + list(FALLBACK_MODELS)
        if model and model not in all_models:
            return
        self._preferred = model

    def get_preferred(self) -> str | None:
        return self._preferred

    # ── Model ordering ──

    def _check_midnight_reset(self):
        today = date.today()
        if today != self._last_reset_date:
            self._cooldowns.clear()
            self._last_reset_date = today
            print(f"[cooldown] 午夜自动重置 ({today})")

    def get_model_order(self) -> list[str]:
        """Return ordered list of available (non-cooldown) models.

        Order: preferred model first (if set and available),
        then MODEL_NAME, then FALLBACK_MODELS.
        Cooldown models are skipped.
        """
        self._check_midnight_reset()

        all_models = [MODEL_NAME] + list(FALLBACK_MODELS)
        # Deduplicate while preserving order
        seen = set()
        ordered = []
        # Preferred first
        if self._preferred and self._preferred in all_models:
            ordered.append(self._preferred)
            seen.add(self._preferred)
        # Then rest in config order
        for m in all_models:
            if m not in seen:
                ordered.append(m)
                seen.add(m)
        # Filter out cooldown models
        return [m for m in ordered if not self.is_on_cooldown(m)]

    def get_all_models(self) -> list[str]:
        """Return complete model list regardless of cooldown."""
        return [MODEL_NAME] + list(FALLBACK_MODELS)

    # ── Status for UI ──

    def get_status(self) -> list[dict]:
        self._check_midnight_reset()
        all_models = [MODEL_NAME] + list(FALLBACK_MODELS)
        result = []
        for m in all_models:
            on_cd = self.is_on_cooldown(m)
            remaining = 0
            if on_cd:
                remaining = int(self._cooldowns[m] - time.time())
            result.append(
                {
                    "id": m,
                    "display_name": MODEL_DISPLAY_NAMES.get(m, m),
                    "in_cooldown": on_cd,
                    "cooldown_remaining_secs": max(remaining, 0),
                    "is_preferred": m == self._preferred,
                    "is_primary": m == MODEL_NAME,
                }
            )
        return result


# Module-level singleton
cooldown_manager = ModelCooldownManager()
