"""The in-process daily scheduler (D-151..D-154 / PLAT-06).

One module owns the scheduler object; the app lifespan is the only start/stop
site, and both are idempotent and never raise (D-08) — a scheduler that cannot
start degrades the feature and the app still serves.

Five non-negotiable mechanics, verified against the pinned APScheduler 3.11.3
source (do not re-derive):

1. ``AsyncIOScheduler``, not the threaded ``Background`` scheduler. A thread-pool
   executor calls the target synchronously, so an ``async def`` target returns a
   coroutine that is never awaited: the job reports success and runs nothing.
2. The job target is module-level, argument-free and ``async def``. APScheduler
   serialises the callable as a module-qualified text reference and pickles
   ``args``/``kwargs``; a lambda, a closure, a bound method or a non-picklable
   argument fails at ``add_job``, which under the boot contract degrades the
   scheduler to unavailable and the feature silently does nothing.
3. Create-if-absent at boot, never unconditional replace. Re-registering a
   persisted job recomputes its next fire time to the next *future* one and
   overwrites the stored state, which makes the missed-run event unreachable and
   silently kills D-154's "its absence IS surfaced".
4. The in-flight guard is a database read, not ``max_instances``.
   ``max_instances=1`` counts only APScheduler's own submissions, so it cannot see
   a run started by the manual ``POST /runs`` route.
5. ``start()`` must be called from inside the running loop (the lifespan is), and
   ``shutdown()`` is synchronous and raises when the scheduler is not running, so
   the idempotency guard is required.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import structlog
from apscheduler.events import (
    EVENT_JOB_ERROR,
    EVENT_JOB_MAX_INSTANCES,
    EVENT_JOB_MISSED,
)
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import create_engine, event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import settings
from app.db.models import Run
from app.db.repositories import operations_config_repo, run_repo
from app.db.session import apply_sqlite_pragmas, get_session_factory
from app.pipeline.run import TERMINAL_STATUSES, run_pipeline

log = structlog.get_logger(__name__)

#: The one job id. An explicit id is what makes create-if-absent possible and
#: stops a duplicate from being registered (a conflicting id raises).
SCHEDULED_JOB_ID = "shortlist-daily-run"

#: The module singleton. Tests install their own instance here and `get_scheduler`
#: returns it, so the settings route and the tests reach the same object.
_scheduler: AsyncIOScheduler | None = None

#: Strong references to in-flight skip-notice writes. They are fire-and-forget
#: tasks dispatched from a synchronous listener, so without this set the event loop
#: could garbage-collect one mid-flight (the `app/api/runs.py` `_BACKGROUND_TASKS`
#: pattern).
_SKIP_TASKS: set[asyncio.Task] = set()


def _jobstore_engine():
    """The jobstore's own **sync** engine over ``settings.database_url_sync``.

    ``build_engine`` is async-only, so this applies the same four SQLite PRAGMAs
    through its own connect listener rather than importing that one.
    """
    engine = create_engine(settings.database_url_sync)
    event.listens_for(engine, "connect")(apply_sqlite_pragmas)
    return engine


def _on_scheduler_event(event) -> None:  # noqa: ANN001 — an APScheduler event
    """Record the two D-154 skip reasons durably. Never raises into APScheduler.

    APScheduler dispatches both events synchronously on the running event loop, so
    the durable write is scheduled as a task (held in `_SKIP_TASKS`). A listener must
    never propagate: an exception here would be logged by APScheduler and the skip
    silently lost.
    """
    try:
        if event.code == EVENT_JOB_MISSED:
            # JobExecutionEvent carries `scheduled_run_time`.
            _queue_skip_notice(reason="missed", when=getattr(event, "scheduled_run_time", None))
        elif event.code == EVENT_JOB_MAX_INSTANCES:
            # JobSubmissionEvent carries `scheduled_run_times` (a list).
            run_times = getattr(event, "scheduled_run_times", None) or []
            _queue_skip_notice(reason="in_flight", when=run_times[0] if run_times else None)
        else:  # EVENT_JOB_ERROR
            log.warning(
                "scheduler.job_error",
                error=type(getattr(event, "exception", None)).__name__,
            )
    except Exception as exc:  # noqa: BLE001 — a listener must never propagate
        log.warning("scheduler.listener_failed", error=type(exc).__name__)


async def _record_skip(
    *, reason: str, when: datetime | None = None, run_id: int | None = None
) -> None:
    """Write one D-154 skip notice on the operations row. Never a `runs` row.

    The status vocabulary has no value for a skip and adding one would need a batch
    recreation of `runs`; the reason, the fire time and an optional in-flight run id
    live on the singleton operations row instead.
    """
    factory = get_session_factory()
    async with factory() as session:
        await operations_config_repo.write_skip_notice(
            session, reason=reason, when=when, run_id=run_id
        )
        await session.commit()


def _queue_skip_notice(
    *, reason: str, when: datetime | None = None, run_id: int | None = None
) -> None:
    """Schedule the durable skip write on the running loop. Never raises."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No loop to write on (e.g. a listener invoked outside the app loop): drop
        # the notice rather than raise into APScheduler.
        log.warning("scheduler.skip_notice_dropped", reason=reason)
        return
    task = loop.create_task(_record_skip(reason=reason, when=when, run_id=run_id))
    _SKIP_TASKS.add(task)
    task.add_done_callback(_SKIP_TASKS.discard)


def get_scheduler() -> AsyncIOScheduler:
    """The module singleton, built lazily and returned at call time.

    Returned at call time (not captured) so a test can install its own instance and
    the route picks it up.
    """
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            jobstores={"default": SQLAlchemyJobStore(engine=_jobstore_engine())},
            timezone=ZoneInfo(settings.schedule_timezone),
        )
        _scheduler.add_listener(
            _on_scheduler_event,
            EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES | EVENT_JOB_ERROR,
        )
    return _scheduler


async def run_scheduled_pipeline() -> int | None:
    """The scheduled entry point. Module-level, argument-free, ``async def``.

    APScheduler pickles a job's arguments and stores the callable as a
    module-qualified reference, so the target takes none and resolves the session
    factory itself. It never lets an exception escape into APScheduler.

    The overlap guard is a DATABASE read, not ``max_instances``: ``max_instances=1``
    counts only APScheduler's own submissions, so it cannot see a run started by the
    manual ``POST /runs`` route. A trigger that fires while any run is in flight is
    skipped and the skip is recorded with the in-flight run id (D-154) — never
    overlapped. With no run in flight it hands straight to the one pipeline entry
    point, which creates its own `runs` row (trigger `schedule`, null search id).
    """
    try:
        factory = get_session_factory()
        async with factory() as session:
            in_flight = await run_repo.running_run_id(session)
        if in_flight is not None:
            await _record_skip(reason="in_flight", run_id=int(in_flight))
            log.info("scheduler.skipped", reason="in_flight", run_id=int(in_flight))
            return None
        return await run_pipeline("schedule", None, factory)
    except Exception as exc:  # noqa: BLE001 — a raise must not reach APScheduler
        log.warning("scheduler.target_failed", error=type(exc).__name__)
        return None


async def reconcile_stale_runs(
    session_factory: async_sessionmaker[AsyncSession],
) -> int:
    """Mark leftover non-terminal runs from a previous process as `partial`.

    A run cancelled by container shutdown is caught by `except Exception` nowhere
    (a `CancelledError` is a `BaseException`), so its row stays `running` forever —
    which blocks both the reset guard and every future scheduled run. At boot the
    process that owned any non-terminal row is gone by definition, so the honest
    outcome is the terminal literal `partial` (not `done`, not `failed`: the result
    is unknown) with the reason recorded in the row's existing error storage. Adds no
    column and no status value.
    """
    async with session_factory() as session:
        rows = (
            (await session.execute(select(Run).where(Run.status.not_in(tuple(TERMINAL_STATUSES)))))
            .scalars()
            .all()
        )
        for run in rows:
            run.status = "partial"
            run.finished_at = datetime.now(UTC)
            # Append rather than replace: a row that was mid-flight when a previous
            # build persisted its own errors must not lose them (the docstring's
            # "recorded in the row's existing error storage"). In practice
            # `errors_json` is written only at `_finish`, so this is defensive.
            run.errors_json = [
                *list(run.errors_json or []),
                {
                    "source": "*",
                    "error": (
                        "reconciled to partial at boot: the process that owned this run is gone"
                    ),
                },
            ]
        await session.commit()
    return len(rows)


async def reconcile(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker[AsyncSession],
) -> str:
    """Create the job only when absent; reschedule only on trigger drift (Pattern 2).

    Returns a short status for the caller's log. Leave an existing job with a
    matching trigger completely alone — its persisted next fire time may be past
    due, and that is exactly the state the misfire machinery needs.
    """
    async with session_factory() as session:
        schedule = await operations_config_repo.read_schedule(session)

    existing = scheduler.get_job(SCHEDULED_JOB_ID)
    if not schedule.enabled:
        if existing is not None:
            scheduler.remove_job(SCHEDULED_JOB_ID)
        return "disabled"

    trigger = CronTrigger(
        hour=schedule.hour,
        minute=schedule.minute,
        timezone=ZoneInfo(schedule.timezone),
    )
    if existing is None:
        scheduler.add_job(
            run_scheduled_pipeline,
            trigger,
            id=SCHEDULED_JOB_ID,
            replace_existing=False,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=settings.schedule_misfire_grace_seconds,
        )
        return "registered"
    if not isinstance(existing.trigger, CronTrigger) or (
        existing.trigger.fields,
        str(existing.trigger.timezone),
    ) != (trigger.fields, str(trigger.timezone)):
        # The user changed the time or the timezone while the app was down, or the
        # config drifted. Compare the trigger's OWN identity (its field values plus
        # its timezone), never `str(trigger)`: `CronTrigger.__str__` omits the
        # timezone, so a timezone-only change stringifies identically and a
        # `str()` comparison would silently keep firing at the old absolute time.
        scheduler.reschedule_job(SCHEDULED_JOB_ID, trigger=trigger)
        return "rescheduled"
    # Leave the job untouched. Re-registering would recompute its next fire time to
    # the next future one and overwrite the persisted past-due value, which makes
    # the missed-run event unreachable and silently disables D-154's surfacing.
    return "unchanged"


async def start_scheduler() -> str:
    """Start the scheduler and reconcile the stored schedule. Never raises (D-08).

    ``AsyncIOScheduler.start()`` must run inside the event loop (the lifespan is
    one). Reconciliation runs **after** start so the persisted job is visible: a
    stopped scheduler's ``get_job`` only consults pending jobs, so a job stored by
    a previous process would look absent and a duplicate ``add_job`` would raise
    ``ConflictingIdError`` out of ``start()``.
    """
    try:
        scheduler = get_scheduler()
        # Reconcile stale run rows BEFORE the scheduler starts processing, so no
        # scheduled trigger can observe a non-terminal row left by a dead process
        # and skip itself.
        stale = await reconcile_stale_runs(get_session_factory())
        if stale:
            log.warning("scheduler.stale_runs_reconciled", count=stale)
        if not scheduler.running:
            scheduler.start()
        status = await reconcile(scheduler, get_session_factory())
        return f"started:{status}"
    except Exception as exc:  # noqa: BLE001 — boot must not depend on the scheduler
        log.warning("scheduler.start_failed", error=type(exc).__name__)
        return "unavailable"


async def stop_scheduler() -> None:
    """Stop the scheduler if it is running. Idempotent and never raises.

    ``shutdown()`` is synchronous and raises when the scheduler is not running, so
    the guard is required. It is never awaited.
    """
    scheduler = _scheduler
    if scheduler is None or not scheduler.running:
        return
    try:
        scheduler.shutdown(wait=False)
    except Exception as exc:  # noqa: BLE001 — stopping must never take boot down
        log.warning("scheduler.stop_failed", error=type(exc).__name__)


def next_run_at() -> datetime | None:
    """The scheduled job's next fire time, or ``None``. Total — never raises.

    ``None`` is an honest state (scheduler unavailable, no job, or a paused job);
    the reader must render it as "no run scheduled", never compute a countdown.
    """
    try:
        job = get_scheduler().get_job(SCHEDULED_JOB_ID)
    except Exception as exc:  # noqa: BLE001 — a scheduler that failed to start degrades the line
        log.warning("scheduler.next_run_failed", error=type(exc).__name__)
        return None
    return job.next_run_time if job is not None else None


__all__ = [
    "SCHEDULED_JOB_ID",
    "get_scheduler",
    "next_run_at",
    "reconcile",
    "reconcile_stale_runs",
    "run_scheduled_pipeline",
    "start_scheduler",
    "stop_scheduler",
]
