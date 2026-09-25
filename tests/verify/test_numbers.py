"""D-113 / A2 / A3 — the metric tokeniser and the region segmentation.

Every documented edge case from the `must_haves` truth is pinned here: an affix, a
range, a percent, a thousands separator, a decimal, a magnitude suffix, a date
core, and a page-number line. The region cases pin both a found org and an absent
one, so the "an absent org is an entity failure, not a metric failure" rule is
enforced rather than assumed.
"""

from __future__ import annotations

import pytest

from app.domain.cv import (
    Bullet,
    RenderPlan,
    RenderedEntry,
    RenderedSection,
    Skill,
)
from app.domain.tex import squash
from app.verify.numbers import (
    date_like_cores_for_entry,
    digit_cores,
    is_page_number_line,
    region_token_report,
)
from app.verify.text_checks import check_metric_containment
from tests.verify.fixtures import (
    VERIFY_FIXTURES,
    build_fixture,
    load_standin_facts,
    with_digit_location,
    with_digit_skill,
)

# --- digit cores ---------------------------------------------------------------


def test_the_acceptance_literal_yields_the_documented_cores() -> None:
    text = "5+ and 5-10 and 40% and 1,200 and 0.5 and 50k"

    assert digit_cores(text) == ["5", "5", "10", "40", "1200", "0.5", "50"]


def test_a_plus_affix_does_not_create_a_new_token() -> None:
    assert digit_cores("5+") == ["5"]


def test_a_range_yields_two_cores() -> None:
    assert digit_cores("5-10") == ["5", "10"]


def test_a_percent_affix_does_not_create_a_new_token() -> None:
    assert digit_cores("40%") == ["40"]


def test_a_thousands_separator_is_removed() -> None:
    assert digit_cores("1,200") == ["1200"]


def test_a_decimal_point_is_preserved() -> None:
    assert digit_cores("0.5") == ["0.5"]


def test_a_decimal_comma_is_normalised_to_a_point() -> None:
    assert digit_cores("0,5") == ["0.5"]


def test_a_magnitude_suffix_is_dropped() -> None:
    assert digit_cores("50k") == ["50"]


def test_an_ordinal_yields_its_integer_core() -> None:
    assert digit_cores("3rd") == ["3"]


def test_the_tokeniser_is_total() -> None:
    assert digit_cores("") == []


# --- date-like cores -----------------------------------------------------------


def test_date_like_cores_are_the_year_and_month_cores() -> None:
    entry = build_fixture().plan.sections[0].entries[0]

    assert date_like_cores_for_entry(entry) == {"2021", "03", "2024", "09"}


# --- page-number lines ---------------------------------------------------------


def test_a_lone_integer_within_the_page_count_is_a_page_number() -> None:
    assert is_page_number_line("2", page_count=3) is True
    assert is_page_number_line("  1  ", page_count=3) is True


def test_zero_is_not_a_page_number() -> None:
    assert is_page_number_line("0", page_count=3) is False


def test_an_integer_above_the_page_count_is_not_a_page_number() -> None:
    assert is_page_number_line("4", page_count=3) is False
    assert is_page_number_line("12", page_count=3) is False


def test_a_prose_line_is_not_a_page_number() -> None:
    assert is_page_number_line("Experience", page_count=3) is False


# --- region segmentation -------------------------------------------------------


def test_the_region_carries_only_its_grounded_tokens() -> None:
    fixture = build_fixture()

    reports = region_token_report(fixture.plan, fixture.text, page_count=1)

    assert len(reports) == 1
    report = reports[0]
    assert report.entry_id == "exp/northwind-labs-2021"
    assert report.found is True
    # The date cores are excluded; only the two metric tokens survive.
    assert report.candidates == ["99", "40"]
    assert set(report.candidates) <= set(report.allowed)


def test_a_date_core_is_never_a_candidate() -> None:
    fixture = build_fixture()

    report = region_token_report(fixture.plan, fixture.text, page_count=1)[0]

    assert "2021" not in set(report.candidates)
    assert "03" not in set(report.candidates)


def test_a_page_number_line_is_never_a_candidate() -> None:
    fixture = build_fixture(extract_name="three_page_extract.txt", page_count=3)

    report = region_token_report(fixture.plan, fixture.text, page_count=3)[0]

    assert "1" not in set(report.candidates)
    assert report.candidates == ["99", "40"]


def test_an_absent_org_is_reported_not_found() -> None:
    fixture = build_fixture(extract_name="missing_entity_extract.txt")

    report = region_token_report(fixture.plan, fixture.text, page_count=1)[0]

    assert report.found is False
    assert report.candidates == []


def test_a_digit_bearing_location_is_not_a_surplus_candidate() -> None:
    """CR-01: the entry's location digit core is grounded in its own region's allowed set.

    The fold adds the location to ``allowed`` ONLY (never to ``excluded``), so the
    digit remains a region candidate and is excused by membership in ``allowed``.
    """
    entry = RenderedEntry(
        id="exp/acme-2020",
        org="Acme",
        title="Engineer",
        dates="2020-01 -- 2021-01",
        location="Dublin 2",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry],
            )
        ]
    )
    text = "Acme --- Engineer\n2020-01 -- 2021-01\nDublin 2\n"

    report = region_token_report(plan, text, page_count=1)[0]

    assert report.found is True
    assert "2" in report.allowed
    assert set(report.candidates) <= set(report.allowed)
    # The far end of the check-4 predicate the blocked preview/download depends on.
    assert check_metric_containment(plan, text, page_count=1).status == "pass"


# --- GAP 1 / WR-03: region-local exclusion -------------------------------------


def test_a_foreign_date_core_is_not_excluded_in_another_region() -> None:
    """WR-03: entry B's year must NOT excuse that token inside entry A's region."""
    entry_a = RenderedEntry(
        id="exp/alpha-2019",
        org="Alpha Corp",
        title="Engineer",
        dates="2019-01 -- 2020-12",
        bullets=[Bullet(id="bul/alpha-2019/1", text="Launched the 2022 campaign")],
    )
    entry_b = RenderedEntry(
        id="exp/beta-2022",
        org="Beta Inc",
        title="Analyst",
        dates="2022-05 -- present",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry_a, entry_b],
            )
        ]
    )
    text = (
        "Alpha Corp --- Engineer\n"
        "2019-01 -- 2020-12\n"
        "Launched the 2022 campaign\n"
        "Beta Inc --- Analyst\n"
        "2022-05 -- present\n"
    )

    reports = region_token_report(plan, text, page_count=1)

    # The token is a candidate in A's region (A does not carry the year 2022) ...
    assert "2022" in reports[0].candidates
    # ... and B's own date still excuses it inside B's region.
    assert "2022" not in reports[1].candidates


def test_a_digit_in_a_skill_label_appearing_in_the_region_is_not_a_candidate() -> None:
    """CR-01: a digit-bearing skill label rendered in the region is grounded, not surplus."""
    entry = RenderedEntry(
        id="exp/acme-2020",
        org="Acme",
        title="Dev",
        dates="2020-01 -- 2021-01",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry],
                skills=[Skill(id="skill.aws", label="AWS S3", group="infrastructure")],
            )
        ]
    )
    text = (
        "Acme --- Dev\n"
        "2020-01 -- 2021-01\n"
        "Did things\n"
        "infrastructure AWS S3\n"
    )

    report = region_token_report(plan, text, page_count=1)[0]

    assert "3" not in set(report.candidates)
    assert "3" in report.allowed


def test_the_committed_digit_skill_extract_has_no_surplus_candidate() -> None:
    """CR-01 end-to-end at the region level over the committed digit-skill extraction."""
    facts = with_digit_skill(load_standin_facts())
    fixture = build_fixture(facts=facts, extract_name="digit_skill_extract.txt")

    report = region_token_report(fixture.plan, fixture.text, page_count=1)[0]

    # The only surviving metric tokens are the bullets' own; the "3" in "AWS S3" is not.
    assert report.candidates == ["99", "40"]
    assert set(report.candidates) <= set(report.allowed)


def test_a_bullet_naming_a_later_employer_does_not_bleed_into_its_region() -> None:
    """CR-02: a bullet naming a later entry's employer must not start that region."""
    entry_a = RenderedEntry(
        id="exp/acme-2018",
        org="Acme",
        title="Engineer",
        dates="2018-01 -- 2018-12",
        bullets=[Bullet(id="bul/acme-2018/1", text="Rebuilt Acme's 5 service mesh")],
    )
    entry_b = RenderedEntry(
        id="exp/acme-2019",
        org="Acme",
        title="Analyst",
        dates="2019-01 -- 2019-12",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry_a, entry_b],
            )
        ]
    )
    text = (
        "Acme --- Engineer\n"
        "2018-01 -- 2018-12\n"
        "Rebuilt Acme's 5 service mesh\n"
        "Acme --- Analyst\n"
        "2019-01 -- 2019-12\n"
    )

    reports = region_token_report(plan, text, page_count=1)

    assert reports[0].found is True
    assert reports[1].found is True
    # A's bullet digit stays in A's own region and is grounded there ...
    assert "5" in reports[0].allowed
    # ... and does not bleed into B's region (the old fail [exp/acme-2019:5]).
    assert "5" not in reports[1].candidates


def test_the_committed_digit_location_extract_has_no_surplus_candidate() -> None:
    """CR-01 end-to-end at the region level over the committed location extraction."""
    facts = with_digit_location(load_standin_facts())
    fixture = build_fixture(facts=facts, extract_name="digit_location_extract.txt")

    report = region_token_report(fixture.plan, fixture.text, page_count=1)[0]

    assert set(report.candidates) <= set(report.allowed)
    assert "2" in report.allowed


def test_a_split_header_entry_is_reported_not_found_not_mislocated() -> None:
    """The strict org-AND-title anchor's deliberate trade-off, pinned.

    The template emits org and title on one header line (``cv.tex.jinja:58``); when
    extraction splits them onto separate lines no line carries both needles, so the
    region is reported ``found=False`` (check 4 skips it) rather than mis-located at
    a bullet — the safer direction, chosen over the pre-fix substring mis-location.
    """
    entry = RenderedEntry(
        id="exp/acme-2020",
        org="Acme",
        title="Engineer",
        dates="2018-01 -- 2018-12",
        bullets=[Bullet(id="bul/acme-2020/1", text="Rebuilt the 5 service mesh")],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry],
            )
        ]
    )
    text = (
        "Acme\n"
        "Engineer\n"
        "2018-01 -- 2018-12\n"
        "Rebuilt the 5 service mesh\n"
    )

    report = region_token_report(plan, text, page_count=1)[0]

    assert report.found is False


# --- ESC-06-A / CR-01: a bullet carrying a later entry's org AND title ----------


def test_a_bullet_embedding_a_later_entrys_org_and_title_does_not_bleed_into_its_region() -> None:
    """The literal repro: a bullet naming a later entry's org AND title must not hijack it.

    The content-only anchor matched ``Partnered with Acme's Senior Engineer team to
    cut 5 incidents`` as entry B's header, pulled A's ``5`` into B's region, and
    hard-failed ``['exp/acme-2019:5']``. The structural date-range-adjacency
    discriminator is what prevents the hijack.
    """
    entry_a = RenderedEntry(
        id="exp/globex-2018",
        org="Globex Inc",
        title="Engineer",
        dates="2018-01 -- 2018-12",
        bullets=[
            Bullet(
                id="bul/globex-2018/1",
                text="Partnered with Acme's Senior Engineer team to cut 5 incidents",
            ),
            Bullet(
                id="bul/globex-2018/2",
                text="Liaised with the Globex Inc Manager on 5 projects",
            ),
        ],
    )
    entry_b = RenderedEntry(
        id="exp/acme-2019",
        org="Acme",
        title="Senior Engineer",
        dates="2019-01 -- 2019-12",
        bullets=[Bullet(id="bul/acme-2019/1", text="Led 7 people")],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry_a, entry_b],
            )
        ]
    )
    text = (VERIFY_FIXTURES / "org_title_collision_extract.txt").read_text(encoding="utf-8")

    reports = region_token_report(plan, text, page_count=1)

    assert reports[0].found is True
    assert reports[1].found is True
    assert reports[1].entry_id == "exp/acme-2019"
    assert "5" not in reports[1].candidates
    assert check_metric_containment(plan, text, page_count=1).status == "pass"

    # The failure class, proven: the bullet line carries BOTH the later org and its
    # title, so a content-only anchor WOULD match it. The discriminator is the fix.
    first_bullet_line = next(line for line in text.splitlines() if "cut 5 incidents" in line)
    squashed_bullet = squash(first_bullet_line)
    assert squash("Acme") in squashed_bullet
    assert squash("Senior Engineer") in squashed_bullet


def test_the_last_region_still_runs_to_end_of_text() -> None:
    """The last region still runs to end-of-text; the trailing Skills block stays in it."""
    fixture = build_fixture(extract_name="three_page_extract.txt", page_count=3)

    reports = region_token_report(fixture.plan, fixture.text, page_count=3)

    assert reports[0].found is True
    assert reports[0].candidates == ["99", "40"]


def test_a_non_adjacent_date_range_is_not_a_region_start() -> None:
    """Org+title alone is not a start: the date-range discriminator must be adjacent."""
    entry = RenderedEntry(
        id="exp/acme-2020",
        org="Acme",
        title="Engineer",
        dates="2018-01 -- 2018-12",
        bullets=[],
    )
    plan = RenderPlan(
        sections=[
            RenderedSection(id="sec.experience", title="Experience", entries=[entry])
        ]
    )
    text = (
        "Acme --- Engineer\n"
        "Some other line\n"
        "Another line\n"
        "2018-01 -- 2018-12\n"
    )

    report = region_token_report(plan, text, page_count=1)[0]

    assert report.found is False


_PHRASE_TEMPLATES = [
    "Liaised with {org} {title} on {n} projects",
    "Partnered with {org}'s {title} team to cut {n} incidents",
    "Mentored the {org} {title} team of {n} people",
]

_DISTINCT_EMPLOYER_CORPUS = [
    ("Acme", "Engineer", 41),
    ("Globex Inc", "Analyst", 52),
    ("Initech", "Manager", 63),
]

_SAME_EMPLOYER_CORPUS = [
    ("Acme", "Engineer", 41),
    ("Acme", "Analyst", 52),
    ("Acme", "Manager", 63),
]


def _collision_plan_and_text(
    corpus: list[tuple[str, str, int]], phrase: str
) -> tuple[RenderPlan, str]:
    """A 3-entry plan + extraction where each entry's bullet embeds the NEXT org+title."""
    entries: list[RenderedEntry] = []
    lines: list[str] = []
    for index, (org, title, marker) in enumerate(corpus):
        if index + 1 < len(corpus):
            next_org, next_title, _ = corpus[index + 1]
            bullet_text = phrase.format(org=next_org, title=next_title, n=marker)
        else:
            bullet_text = "Delivered the platform"
        year = 2019 + index
        entries.append(
            RenderedEntry(
                id=f"exp/collision-{year}",
                org=org,
                title=title,
                dates=f"{year}-01 -- {year}-12",
                bullets=[Bullet(id=f"bul/collision-{year}/1", text=bullet_text)],
            )
        )
        lines.append(f"{org} --- {title}")
        lines.append(f"{year}-01 -- {year}-12")
        lines.append(bullet_text)
    plan = RenderPlan(
        sections=[
            RenderedSection(id="sec.experience", title="Experience", entries=entries)
        ]
    )
    return plan, "\n".join(lines) + "\n"


@pytest.mark.parametrize("phrase", _PHRASE_TEMPLATES)
@pytest.mark.parametrize(
    "corpus", [_DISTINCT_EMPLOYER_CORPUS, _SAME_EMPLOYER_CORPUS]
)
def test_a_bullet_embedding_the_next_entrys_org_and_title_never_hijacks_a_region(
    phrase: str, corpus: list[tuple[str, str, int]]
) -> None:
    """The whole lexical-collision class, not one instance: every region anchors at its own header."""
    plan, text = _collision_plan_and_text(corpus, phrase)

    reports = region_token_report(plan, text, page_count=1)

    assert [report.found for report in reports] == [True, True, True]
    for index, report in enumerate(reports):
        for earlier in corpus[:index]:
            assert str(earlier[2]) not in set(report.candidates)
    assert check_metric_containment(plan, text, page_count=1).status == "pass"

    # The mutation really embeds the next entry's org AND title (the collision class).
    for index in range(len(corpus) - 1):
        next_org, next_title, _ = corpus[index + 1]
        mutated = phrase.format(org=next_org, title=next_title, n=corpus[index][2])
        squashed = squash(mutated)
        assert squash(next_org) in squashed
        assert squash(next_title) in squashed


# --- 06-11 / WR-02: the org-first boundary and the region-end leak guard --------


def _two_entry_plan(
    *,
    a_id: str,
    a_org: str,
    a_title: str,
    a_dates: str,
    a_bullets: list[Bullet],
    b_id: str,
    b_org: str,
    b_title: str,
    b_dates: str,
    b_bullets: list[Bullet] | None = None,
) -> RenderPlan:
    """A two-entry Experience plan, A first. The common fixture for the 06-11 shapes."""
    entry_a = RenderedEntry(
        id=a_id, org=a_org, title=a_title, dates=a_dates, bullets=a_bullets
    )
    entry_b = RenderedEntry(
        id=b_id, org=b_org, title=b_title, dates=b_dates, bullets=b_bullets or []
    )
    return RenderPlan(
        sections=[
            RenderedSection(
                id="sec.experience",
                title="Experience",
                entries=[entry_a, entry_b],
            )
        ]
    )


def test_a_bullet_carrying_the_next_entrys_org_title_and_dates_does_not_bleed_into_its_region() -> None:
    """Variant 1: a bullet co-locating the next org, title AND date-range is not a header.

    The content/title-plus-date anchor matched the earlier bullet as entry B's header,
    pulled A's ``5`` into B's region and hard-failed ``['exp/acme-2019:5']`` on a
    correct CV. The org-first position is what prevents the hijack.
    """
    plan = _two_entry_plan(
        a_id="exp/globex-2018",
        a_org="Globex Inc",
        a_title="Engineer",
        a_dates="2018-01 -- 2018-12",
        a_bullets=[
            Bullet(
                id="bul/globex-2018/1",
                text="Partnered with Acme Senior Engineer 2019-01 -- 2019-12 to cut 5 incidents",
            )
        ],
        b_id="exp/acme-2019",
        b_org="Acme",
        b_title="Senior Engineer",
        b_dates="2019-01 -- 2019-12",
        b_bullets=[Bullet(id="bul/acme-2019/1", text="Led 7 people")],
    )
    text = (VERIFY_FIXTURES / "org_title_dates_collision_extract.txt").read_text(
        encoding="utf-8"
    )

    reports = region_token_report(plan, text, page_count=1)

    assert reports[0].found is True
    assert reports[1].found is True
    assert reports[1].entry_id == "exp/acme-2019"
    assert "5" not in reports[1].candidates
    assert check_metric_containment(plan, text, page_count=1).status == "pass"

    # The failure class, proven: the earlier bullet line carries BOTH the later org
    # and title AND its date-range, so a content-only or title-plus-date-only anchor
    # WOULD match it. The org-first boundary is the fix.
    first_bullet_line = next(line for line in text.splitlines() if "cut 5 incidents" in line)
    squashed_bullet = squash(first_bullet_line)
    assert squash("Acme") in squashed_bullet
    assert squash("Senior Engineer") in squashed_bullet
    assert squash("2019-01 -- 2019-12") in squashed_bullet


def test_an_unanchored_entry_does_not_donate_its_digits_to_the_previous_region() -> None:
    """Variant 2: an extractor line-merge leaves B unanchored; A must not absorb B's digits.

    The pre-fix false-fail is ``fail ['exp/globex-2018:7']`` (or ``['exp/acme-2019:5']``):
    the preceding region cannot separate the merged neighbour, so the correct
    disposition is a visible ``warn`` naming B, not a block on A.
    """
    plan = _two_entry_plan(
        a_id="exp/globex-2018",
        a_org="Globex Inc",
        a_title="Engineer",
        a_dates="2018-01 -- 2018-12",
        a_bullets=[
            Bullet(
                id="bul/globex-2018/1",
                text="Liaised with the Globex Inc Manager on 5 projects",
            )
        ],
        b_id="exp/acme-2019",
        b_org="Acme",
        b_title="Senior Engineer",
        b_dates="2019-01 -- 2019-12",
        b_bullets=[Bullet(id="bul/acme-2019/1", text="Led 7 people")],
    )
    text = (VERIFY_FIXTURES / "org_title_dates_merge_extract.txt").read_text(
        encoding="utf-8"
    )

    reports = region_token_report(plan, text, page_count=1)
    check = check_metric_containment(plan, text, page_count=1)

    assert reports[0].found is True
    assert reports[1].found is False
    assert check.status == "warn"
    assert "exp/acme-2019" in check.offending
    assert not any(entry.startswith("exp/globex-2018:") for entry in check.offending)


_LEAK_SHAPES = [
    "dates_on_own_line",
    "merged_header_dates_on_successor",
    "merged_header_with_dates",
]


def _leak_shape_text(shape: str) -> str:
    lines = ["Globex Inc --- Engineer", "2018-01 -- 2018-12"]
    if shape == "dates_on_own_line":
        lines += [
            "Liaised with the Globex Inc Manager on 5 projects",
            "Acme --- Senior Engineer",
            "2019-01 -- 2019-12",
            "Led 7 people",
        ]
    elif shape == "merged_header_dates_on_successor":
        lines += [
            "Liaised with the Globex Inc Manager on 5 projects Acme Senior Engineer",
            "2019-01 -- 2019-12",
            "Led 7 people",
        ]
    else:  # merged_header_with_dates
        lines += [
            "Liaised with the Globex Inc Manager on 5 projects Acme Senior Engineer 2019-01 -- 2019-12",
            "Led 7 people",
        ]
    return "\n".join(lines) + "\n"


@pytest.mark.parametrize("shape", _LEAK_SHAPES)
def test_an_unanchored_entrys_date_cores_are_never_absorbed_by_the_previous_region(
    shape: str,
) -> None:
    """Every unanchored extraction shape leaves the preceding region free of B's dates.

    Shape ``merged_header_with_dates`` is the containment gate: an equality-only guard
    never fires and returns ``fail ['exp/globex-2018:2019','exp/globex-2018:7']``,
    while containment returns ``warn ['exp/acme-2019']``.
    """
    plan = _two_entry_plan(
        a_id="exp/globex-2018",
        a_org="Globex Inc",
        a_title="Engineer",
        a_dates="2018-01 -- 2018-12",
        a_bullets=[
            Bullet(
                id="bul/globex-2018/1",
                text="Liaised with the Globex Inc Manager on 5 projects",
            )
        ],
        b_id="exp/acme-2019",
        b_org="Acme",
        b_title="Senior Engineer",
        b_dates="2019-01 -- 2019-12",
        b_bullets=[Bullet(id="bul/acme-2019/1", text="Led 7 people")],
    )
    text = _leak_shape_text(shape)

    reports = region_token_report(plan, text, page_count=1)
    check = check_metric_containment(plan, text, page_count=1)

    assert reports[0].found is True
    if shape == "dates_on_own_line":
        assert reports[1].found is True
        assert check.status == "pass"
        return
    assert reports[1].found is False
    assert "2019" not in reports[0].candidates
    assert "01" not in reports[0].candidates
    assert "12" not in reports[0].candidates
    assert check.status == "warn"
    assert "exp/acme-2019" in check.offending
    assert not any(entry.startswith("exp/globex-2018:") for entry in check.offending)


_ROUND3_SHAPES = ["digit_bearing_header", "identical_dates"]


@pytest.mark.parametrize("shape", _ROUND3_SHAPES)
def test_a_digit_bearing_or_identical_date_neighbour_is_not_charged_to_the_preceding_region(
    shape: str,
) -> None:
    """Round-3 shapes: a digit-bearing header and a shared identical date-range.

    Pre-fix both false-failed the anchored entry (``['exp/acme-2018:3']`` /
    ``['exp/acme-2018:7']``). The bound matches the neighbour's org and title as well
    as its date-range and excludes the anchored entry's own date line BY POSITION, so
    a shared identical date-range no longer suppresses the bound.
    """
    if shape == "digit_bearing_header":
        plan = _two_entry_plan(
            a_id="exp/acme-2018",
            a_org="Acme",
            a_title="Engineer",
            a_dates="2018-01 -- 2018-12",
            a_bullets=[Bullet(id="bul/acme-2018/1", text="Delivered the platform")],
            b_id="exp/3m-2019",
            b_org="3M",
            b_title="Manager",
            b_dates="2019-01 -- 2019-12",
            b_bullets=[Bullet(id="bul/3m-2019/1", text="Led 7 people")],
        )
        extract_name = "digit_bearing_header_extract.txt"
        named = "exp/3m-2019"
    else:
        plan = _two_entry_plan(
            a_id="exp/acme-2018",
            a_org="Acme",
            a_title="Engineer",
            a_dates="2019-01 -- 2019-12",
            a_bullets=[Bullet(id="bul/acme-2018/1", text="Delivered the platform")],
            b_id="exp/globex-2019",
            b_org="Globex Inc",
            b_title="",
            b_dates="2019-01 -- 2019-12",
            b_bullets=[Bullet(id="bul/globex-2019/1", text="Led 7 people")],
        )
        extract_name = "identical_dates_extract.txt"
        named = "exp/globex-2019"
    text = (VERIFY_FIXTURES / extract_name).read_text(encoding="utf-8")

    reports = region_token_report(plan, text, page_count=1)
    check = check_metric_containment(plan, text, page_count=1)

    assert reports[0].found is True
    assert reports[1].found is False
    assert check.status == "warn"
    assert not any(entry.startswith("exp/acme-2018:") for entry in check.offending)
    assert named in check.offending

    # The failure class: the accept-side fix cannot have been bought by weakening the
    # block — a genuinely fabricated ``99`` in A's OWN region is still a hard fail.
    mutated = text.replace("Delivered the platform", "Delivered the 99 platform")
    fabricated = check_metric_containment(plan, mutated, page_count=1)
    assert fabricated.status == "fail"
    assert "exp/acme-2018:99" in fabricated.offending


_OWN_CONTENT_SHAPES = ["own_date_line_shared_range", "own_bullet_quotes_dates"]


@pytest.mark.parametrize("shape", _OWN_CONTENT_SHAPES)
def test_the_region_end_bound_never_shortens_an_anchored_region_at_its_own_content(
    shape: str,
) -> None:
    """The bound must not collapse an anchored region at its own date/bullet line.

    Under the uncorrected containment rule both shapes returned
    ``warn ['exp/globex-2019']`` with A's candidates empty — the false PASS this phase
    exists to prevent. The positional own-date exclusion and the own-bullet squash
    equality keep the fabricated ``99`` charged as ``fail ['exp/acme-2018:99']``.
    """
    if shape == "own_date_line_shared_range":
        plan = _two_entry_plan(
            a_id="exp/acme-2018",
            a_org="Acme",
            a_title="Engineer",
            a_dates="2019-01 -- 2019-12",
            a_bullets=[Bullet(id="bul/acme-2018/1", text="Delivered the platform")],
            b_id="exp/globex-2019",
            b_org="Globex Inc",
            b_title="",
            b_dates="2019-01 -- 2019-12",
        )
        text = (
            "Acme --- Engineer\n"
            "2019-01 -- 2019-12\n"
            "Delivered the 99 platform\n"
            "Globex Inc --- \n"
        )
    else:  # own_bullet_quotes_dates
        plan = _two_entry_plan(
            a_id="exp/acme-2018",
            a_org="Acme",
            a_title="Engineer",
            a_dates="2018-01 -- 2018-12",
            a_bullets=[
                Bullet(
                    id="bul/acme-2018/1",
                    text="Covered the 2019-01 -- 2019-12 period",
                ),
                Bullet(id="bul/acme-2018/2", text="Delivered the platform"),
            ],
            b_id="exp/globex-2019",
            b_org="Globex Inc",
            b_title="",
            b_dates="2019-01 -- 2019-12",
        )
        text = (
            "Acme --- Engineer\n"
            "2018-01 -- 2018-12\n"
            "Covered the 2019-01 -- 2019-12 period\n"
            "Delivered the 99 platform\n"
            "Globex Inc --- \n"
        )

    reports = region_token_report(plan, text, page_count=1)
    check = check_metric_containment(plan, text, page_count=1)

    assert reports[0].found is True
    assert reports[1].found is False
    assert check.status == "fail"
    assert "exp/acme-2018:99" in check.offending


_DATE_PHRASE_TEMPLATES = [
    "Liaised with {org} {title} {dates} on {n} projects",
    "Partnered with {org}'s {title} team from {dates} to cut {n} incidents",
    "Mentored the {org} {title} team ({dates}) of {n} people",
]


def _date_collision_plan_and_text(
    corpus: list[tuple[str, str, int]], phrase: str
) -> tuple[RenderPlan, str]:
    """A 3-entry plan + extraction where each bullet embeds the NEXT org, title AND dates."""
    entries: list[RenderedEntry] = []
    lines: list[str] = []
    for index, (org, title, marker) in enumerate(corpus):
        year = 2019 + index
        if index + 1 < len(corpus):
            next_org, next_title, _ = corpus[index + 1]
            next_dates = f"{year + 1}-01 -- {year + 1}-12"
            bullet_text = phrase.format(
                org=next_org, title=next_title, dates=next_dates, n=marker
            )
        else:
            bullet_text = "Delivered the platform"
        entries.append(
            RenderedEntry(
                id=f"exp/collision-{year}",
                org=org,
                title=title,
                dates=f"{year}-01 -- {year}-12",
                bullets=[Bullet(id=f"bul/collision-{year}/1", text=bullet_text)],
            )
        )
        lines.append(f"{org} --- {title}")
        lines.append(f"{year}-01 -- {year}-12")
        lines.append(bullet_text)
    plan = RenderPlan(
        sections=[
            RenderedSection(id="sec.experience", title="Experience", entries=entries)
        ]
    )
    return plan, "\n".join(lines) + "\n"


@pytest.mark.parametrize("phrase", _DATE_PHRASE_TEMPLATES)
@pytest.mark.parametrize("corpus", [_DISTINCT_EMPLOYER_CORPUS, _SAME_EMPLOYER_CORPUS])
def test_a_bullet_embedding_the_next_entrys_org_title_and_dates_never_hijacks_a_region(
    phrase: str, corpus: list[tuple[str, str, int]]
) -> None:
    """The date dimension of the collision class, not one instance: every region anchors."""
    plan, text = _date_collision_plan_and_text(corpus, phrase)

    reports = region_token_report(plan, text, page_count=1)

    assert [report.found for report in reports] == [True, True, True]
    for index, report in enumerate(reports):
        for earlier in corpus[:index]:
            assert str(earlier[2]) not in set(report.candidates)
    assert check_metric_containment(plan, text, page_count=1).status == "pass"

    # The mutation really embeds the next entry's org, title AND date-range (the
    # date dimension the discriminator depends on).
    for index in range(len(corpus) - 1):
        next_org, next_title, _ = corpus[index + 1]
        next_dates = f"{2019 + index + 1}-01 -- {2019 + index + 1}-12"
        mutated = phrase.format(
            org=next_org,
            title=next_title,
            dates=next_dates,
            n=corpus[index][2],
        )
        squashed = squash(mutated)
        assert squash(next_org) in squashed
        assert squash(next_title) in squashed
        assert squash(next_dates) in squashed


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__])
