"""Horizontal overflow: one measurement, and proof that it can fail.

Cross-engine runs disagreed about this. Chromium reported -10 on every page,
Firefox and WebKit reported 0, and a headed Firefox run once reported 8. None
of those numbers was a layout: ``html`` reserves a ``scrollbar-gutter`` and
``scrollbar-width: thin`` makes that gutter 10px in Chromium, while
``window.innerWidth`` counts a classic 8px scrollbar that ``scrollWidth`` does
not. Measured against ``documentElement.clientWidth`` — the box the content
actually has to fit inside — all three engines agree, and the 8px stops being
a number to tolerate and becomes a number that explains itself.

So this file pins two things:

1. the invariant, on every public page at every width worth supporting;
2. that the invariant can fail.

The second matters more. The shell sets ``overflow-x: hidden``, so a page can
spill sideways and the user simply never gets a scrollbar to notice it with —
and a formula that silently absorbed the scrollbar width made the assertions
agree with the spill. A probe that cannot report a fault is worse than no
probe. Each page therefore injects a deliberate 40px overflow and requires the
probe to report it before the page is allowed to pass.
"""
import pytest

pytestmark = pytest.mark.e2e

# Public surfaces: everything reachable without a session, which is also
# everything a first-time visitor can land on.
PUBLIC_PAGES = [
    ("/", "landing"),
    ("/static/pages/login.html", "login"),
    ("/static/pages/register.html", "register"),
    ("/static/pages/forgot_password.html", "forgot-password"),
    ("/static/pages/about.html", "about"),
]

# Phone to desktop. 320 is the narrowest screen still sold, 1920 the widest
# common one; the gaps are covered by the resume-preview width sweep.
WIDTHS = [360, 414, 768, 1024, 1280, 1920]

MEASURE = """() => {
  const de = document.documentElement;
  const kids = Array.from(document.body.querySelectorAll(':scope > *'));
  return {
    // What the content overflows the content box by. Both terms exclude the
    // scrollbar, so this reads the same on every engine.
    overflow: Math.max(0, de.scrollWidth - de.clientWidth),
    // The widest thing the body actually places, as a cross-check: scrollWidth
    // can lie when a descendant is positioned, this cannot.
    widestRight: kids.length
      ? Math.max(...kids.map((k) => k.getBoundingClientRect().right))
      : 0,
    clientW: de.clientWidth,
    scrollW: de.scrollWidth,
    innerW: window.innerWidth,
  };
}"""

# Deliberately 40px too wide, appended last so it is the newest body child.
INJECT = """() => {
  const d = document.createElement('div');
  d.id = 'overflow-probe';
  d.style.cssText = 'height:2px;width:calc(100% + 40px)';
  document.body.appendChild(d);
}"""

REMOVE = "() => { const d = document.getElementById('overflow-probe'); if (d) d.remove(); }"


def open_at(page, base_url, path, width):
    page.set_viewport_size({"width": width, "height": 900})
    page.goto(f"{base_url}{path}")
    page.wait_for_load_state("load")
    # Layout settles after webfonts land; measuring before that reports the
    # fallback metrics, which are wider and would be a false alarm.
    page.wait_for_function("() => document.fonts.status === 'loaded'", timeout=20000)


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("path,label", PUBLIC_PAGES)
def test_page_fits_its_viewport(page, base_url, path, label, width):
    """Nothing may push the document wider than the window it is drawn in."""
    open_at(page, base_url, path, width)
    m = page.evaluate(MEASURE)

    assert m["overflow"] <= 1, (
        f"{label} overflows sideways by {m['overflow']}px at {width}px "
        f"(scrollWidth {m['scrollW']} > clientWidth {m['clientW']})"
    )
    assert m["widestRight"] <= m["clientW"] + 1, (
        f"{label} places an element {m['widestRight'] - m['clientW']:.0f}px past "
        f"the content box at {width}px"
    )


@pytest.mark.parametrize("path,label", PUBLIC_PAGES)
def test_the_probe_reports_an_overflow_that_is_there(page, base_url, path, label):
    """The invariant above is only worth having if it can go red.

    ``overflow-x: hidden`` on the shell means a spill produces no scrollbar, so
    nothing about the page itself would reveal that the measurement had stopped
    working. A synthetic 40px overflow does.
    """
    open_at(page, base_url, path, 1280)
    baseline = page.evaluate(MEASURE)
    assert baseline["overflow"] <= 1, (
        f"{label} is already {baseline['overflow']}px over before the probe"
    )

    page.evaluate(INJECT)
    injected = page.evaluate(MEASURE)
    page.evaluate(REMOVE)

    # The injected element is 40px wider than the body, and scrollWidth must grow
    # by exactly that. It then reads as less than 40 past clientWidth in an
    # engine that reserves a scrollbar gutter, which is fine: the point is that
    # the reading stops being 0 and the invariant above would go red.
    added = injected["scrollW"] - baseline["scrollW"]
    assert added >= 39, (
        f"{label}: the injected element was 40px too wide but scrollWidth grew "
        f"by only {added}px, so this page's overflow assertions cannot fail"
    )
    assert injected["overflow"] > 1, (
        f"{label}: a {added}px overflow still read as "
        f"{injected['overflow']}px, so the invariant would pass a real spill "
        f"(scrollWidth {injected['scrollW']}, clientWidth {injected['clientW']})"
    )

    # Removing it must restore the baseline, or the probe is measuring
    # something that accumulates rather than the page.
    assert page.evaluate(MEASURE)["overflow"] <= 1, (
        f"{label} still reports overflow after the injected element was removed"
    )


def test_classic_scrollbar_accounts_for_the_engine_difference(page, base_url):
    """Pin the arithmetic behind the old 8px, so it cannot resurface as one.

    ``innerWidth - clientWidth`` is the width a classic scrollbar takes from
    the content box: 0 where scrollbars overlay (all three engines headless),
    ~17 on a headed Windows Chrome, 8 on a headed Windows Firefox. Because that
    number is small and positive, a spill narrower than the scrollbar is
    invisible to the ``scrollWidth - innerWidth`` form — which is how an 8px
    overflow could be observed once and then never reproduced.
    """
    open_at(page, base_url, "/static/pages/about.html", 1280)
    m = page.evaluate(MEASURE)
    scrollbar = m["innerW"] - m["clientW"]
    assert 0 <= scrollbar <= 24, (
        f"window.innerWidth - documentElement.clientWidth is {scrollbar}px, "
        f"which is not a scrollbar width; innerWidth {m['innerW']}, "
        f"clientWidth {m['clientW']}"
    )

    # The clientWidth form is the one the invariant uses, and it must still see
    # an overflow that a scrollbar's width would have swallowed.
    page.evaluate(INJECT)
    injected = page.evaluate(MEASURE)
    page.evaluate(REMOVE)
    assert injected["scrollW"] - injected["clientW"] > 1, (
        "the clientWidth form read nothing for a deliberately overflowing "
        f"element: scrollWidth {injected['scrollW']}, "
        f"clientWidth {injected['clientW']}"
    )

