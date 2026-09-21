"""Application settings.

One `pydantic-settings` `Settings` class holds every knob so PLAT-04
("limits/thresholds/engine are config, not constants") is satisfied by
inspection: no threshold literal lives outside this module.
"""

from __future__ import annotations

from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

#: Models evidenced to be UNABLE to satisfy the schema-constrained call this
#: phase exists to make. A structured call forces the tool choice to `required`
#: (opencode implements `format` structured output through the tool it injects
#: into the session), and the provider rejects a forced tool call from a
#: reasoning-mode model with HTTP 400
#: `invalid_request_error: Thinking mode does not support this tool_choice` —
#: uniformly across agents, variants and permission shapes. The provider's whole
#: model set is reasoning-capable, so "pick a non-reasoning model" is not a
#: mitigation; the only remedy is a model that honours the forced tool call.
#: `tests/test_config.py` fails if the shipped default is reverted to one of
#: these, or if this set is emptied so the guard passes vacuously.
KNOWN_FORCED_TOOL_CHOICE_INCOMPATIBLE_MODELS: frozenset[str] = frozenset(
    {"deepseek-v4.1-flash"}
)


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
    #: The model a schema-constrained call resolves when the caller omits `model`.
    #: **It must accept a forced tool call**: opencode implements `format`
    #: structured output through a tool it injects into the session and forces
    #: `toolChoice: "required"` on every such call, so an incapable model makes
    #: every structured call fail at the provider. The previously shipped default
    #: was rejected upstream with HTTP 400
    #: `invalid_request_error: Thinking mode does not support this tool_choice`;
    #: `minimax-m3` is the live-evidenced default that returns `structured` with
    #: `status=ok`. See `docs/runbook-opencode-contract.md`.
    opencode_model: str = "minimax-m3"
    opencode_server_password: str = ""
    #: Bounded timeout for the health/discovery calls (T-01-32): a hung request
    #: must not pin the single worker. Configuration, not a constant (PLAT-04).
    #: Stays scoped to health/discovery — a completion is a different order of
    #: magnitude (Pitfall P4), so it gets its own ceiling below.
    opencode_timeout_seconds: float = 5.0
    #: Bounded timeout for ONE structured completion (PLAT-04). A real call takes
    #: whole seconds to tens of seconds, so reusing the 5-second health timeout
    #: would abort every completion. Configuration, not a constant.
    opencode_completion_timeout_seconds: float = 120.0
    #: How many times the client resends a completion that failed at the transport
    #: layer. The server-side schema retry count is `opencode_structured_retry_count`.
    opencode_max_retries: int = 2
    #: Sent as `format.retryCount`: how many times the SERVER re-asks the model when
    #: its output fails the JSON Schema. Optional on the wire, pinned here.
    opencode_structured_retry_count: int = 2

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
    #: Human-readable location term for the default Phase-1 query. Kept here, not
    #: as a literal in `app/pipeline`, so the search location is adjustable without
    #: a code change (PLAT-04).
    probe_query_location: str = "Ireland"
    probe_cache_ttl_seconds: int = 300

    # --- Survival signal thresholds (S2/S3/S4) -------------------------------
    probe_fill_rate_warn_drop_points: int = 10
    probe_fill_rate_fail_drop_points: int = 25
    probe_count_warn_drop_pct: int = 25
    probe_count_fail_drop_pct: int = 50
    probe_count_trailing_runs: int = 5
    probe_freshness_fail_runs: int = 3
    #: Arming rule for S3: below this many prior runs a count delta is noise, not a
    #: signal (RESEARCH §S3 — "require ≥2 prior runs before the signal is armed").
    probe_min_runs_before_arming: int = 2

    # --- Adzuna promotion condition (D-04 / P-1..P-5) -------------------------
    # Every boundary the verdict document cites lives here, so Phase 8 can
    # re-evaluate the condition by code instead of re-reading prose.
    probe_promotion_window_runs: int = 5
    probe_promotion_blocked_runs: int = 3
    probe_promotion_consecutive_runs: int = 2

    # --- Phase 2 queue + dedup envelope (D-31 / D-40 / D-42) ------------------
    # Tier-2 fuzzy-match θ (D-31): a 0-100 starting value with a tuning task
    # against the first real corpus. STATE.md records that it is untunable
    # without one, so this is a setting, never a frozen constant.
    dedup_fuzzy_threshold: int = 88
    # The candidate blocking window for Tier-2 dedup, so two roles at one company
    # a year apart are never compared.
    dedup_posted_window_days: int = 90
    # QUEUE-07 staleness boundary (D-40): a listing whose last_seen_at is older
    # than this is stale (or is_active is false).
    stale_after_days: int = 14
    # The queue read model's page size (D-42 "Load more" paging).
    queue_page_size: int = 25

    # --- LaTeX engine (CV-05 / PLAT-04 / D-76) --------------------------------
    # Every engine ceiling is configuration, not a constant. The selector picks
    # exactly ONE engine and `get_latex_engine()` never falls back to the other
    # (D-75): a silent fallback would make LATEX_ENGINE stop describing what ran.
    latex_engine: Literal["tectonic", "texlive"] = "tectonic"
    #: The pinned Tectonic binary; D-73 installs it to this exact path.
    tectonic_binary: str = "/usr/local/bin/tectonic"
    #: Explicit and HOME-independent. Tectonic otherwise creates `~/.cache/Tectonic`,
    #: and with no home directory it attempts that with permissive permissions
    #: (T-04-09). Must equal the image ENV and compose.yml's default.
    tectonic_cache_dir: str = "/opt/tectonic-cache"
    #: The single compile ceiling for BOTH engines (say so, so a later reader does
    #: not "fix" the shared ceiling into two fields): a hung engine must not pin the
    #: single worker (T-04-08).
    tectonic_timeout_seconds: int = 60
    #: D-75's cached-only mode as configuration, so a build-time prime run can differ
    #: from a runtime render run. When true the argv passes `--only-cached`.
    tectonic_offline: bool = True
    #: The TeX Live fallback engine — `xelatex`, never `pdflatex` (Pitfall 10:
    #: pdflatex cannot load fontspec, so it would be available in name only).
    latex_xelatex_binary: str = "/usr/bin/xelatex"
    #: The fact-store volume root (D-58); mounted `./cv:/cv` in compose.yml.
    cv_dir: str = "/cv"
    #: The artefact volume root (D-58); mounted `./artifacts:/artifacts`.
    artifacts_dir: str = "/artifacts"
    #: The D-59 importer's bounds: a line cap and a nesting-depth cap, so a
    #: pathological document cannot make the parser unbounded.
    tex_import_max_lines: int = 20000
    tex_import_max_depth: int = 12
    # NOTE: `meta.max_pages` (CV-R3) is deliberately NOT duplicated here. That page
    # budget lives in the fact store as DATA (D-65); a settings twin would create
    # two sources for one limit. This block is the PLAT-04 surface for the engine,
    # not for the page budget.


settings = Settings()
