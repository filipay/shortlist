"""Application settings.

One `pydantic-settings` `Settings` class holds every knob so PLAT-04
("limits/thresholds/engine are config, not constants") is satisfied by
inspection: no threshold literal lives outside this module.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. Every field has a safe default."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Auth seam (D-21): no user_id columns in v1 ---------------------------
    local_user_id: str = "local"

    # --- Persistence (D-17): two URLs, two drivers, one file ------------------
    database_url_async: str = "sqlite+aiosqlite:////data/jobsearch.db"
    database_url_sync: str = "sqlite:////data/jobsearch.db"

    # --- opencode backend (D-05..D-10) ---------------------------------------
    # The server is user-managed and external; the app never owns or pins it.
    opencode_base_url: str = "http://host.docker.internal:4096"
    opencode_model: str = "deepseek-v4.1-flash"
    opencode_server_password: str = ""

    # --- Ingest sanitise policy (C2) -----------------------------------------
    description_max_chars: int = 20000

    # --- Probe envelope (D-02 / PLAT-04) -------------------------------------
    # Documented operating envelope: 1 search per board, <=50-100 results, once
    # per day, one IP, honest User-Agent. This is the ban-risk line and it is
    # adjustable without a code change.
    probe_enabled: bool = True
    probe_max_requests: int = 2
    probe_max_results: int = 50
    probe_max_detail_fetches: int = 0
    probe_deadline_seconds: int = 180
    probe_results_wanted: int = 50
    probe_country_indeed: str = "ireland"
    probe_cache_ttl_seconds: int = 300

    # --- Survival signal thresholds (S2/S3/S4) -------------------------------
    probe_fill_rate_warn_drop_points: int = 10
    probe_fill_rate_fail_drop_points: int = 25
    probe_count_warn_drop_pct: int = 25
    probe_count_fail_drop_pct: int = 50
    probe_count_trailing_runs: int = 5
    probe_freshness_fail_runs: int = 3


settings = Settings()
