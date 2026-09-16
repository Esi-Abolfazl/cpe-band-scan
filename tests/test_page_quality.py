"""The page rulings from docs/design/2026-09-16-page-redesign.md that a regex can hold. What a
regex cannot hold (the look at 375px and 1440px, light and dark, with a scan running) is
checked by eye on the demo server."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src" / "cpe_band_scan" / "web"
CSS = (WEB / "style.css").read_text(encoding="utf-8")
JS = (WEB / "app.js").read_text(encoding="utf-8")
HTML = (WEB / "index.html").read_text(encoding="utf-8")


def block(selector: str) -> str:
    start = CSS.index(selector)
    return CSS[start:CSS.index("}", start)]


def test_spacing_comes_from_one_scale_through_gap_not_stacked_margins():
    for token in ("--s1", "--s2", "--s3", "--s4", "--s6", "--s8"):
        assert f"{token}:" in CSS
    assert "margin: 0" in block(".card {")
    assert "gap: var(--s" in block(".card {")
    assert "gap: var(--s" in block(".actions {")
    assert "gap: var(--s" in block(".form-row {")


def test_the_page_uses_the_width_it_is_given():
    assert "max-width: 100rem" in block("#app {")
    assert "grid-template-columns: repeat(2" in block(".grid {")


def test_shape_lock_cards_12_controls_8_badges_pill():
    assert "--r-card: 12px" in CSS and "--r-control: 8px" in CSS
    assert "border-radius: var(--r-card)" in block(".card {")
    assert "border-radius: var(--r-control)" in block("button {")
    assert "border-radius: 999px" in block(".badge {")
    stray = [m for m in re.findall(r"border-radius:\s*([^;]+);", CSS)
             if m not in ("var(--r-card)", "var(--r-control)", "999px")]
    assert not stray, f"radii outside the scale: {stray}"


def test_one_accent_and_no_question_marks():
    assert '"?"' not in JS
    assert "popover" not in JS and "popover" not in HTML
    assert "gradient" not in CSS


def test_numbers_are_tabular_and_go_through_one_helper():
    assert "font-variant-numeric: tabular-nums" in block(".num {")
    assert "function num(" in JS
    assert "num(row.floor)" in JS and "num(row.rsrp)" in JS


def test_the_logs_are_built_once_and_appended_to():
    """Rebuilding the log on every poll is what made the old page unreadable."""
    assert '"data-log"' in JS
    poll = re.search(r"async function poll\(\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert "applyEvent(event)" in poll
    assert "render()" not in poll.split("if (state.running) setTimeout")[0].split("else")[0].replace("return render()", "")


def test_follow_switches_off_when_the_reader_scrolls_up_or_the_side_finishes():
    panel = re.search(r"function logPanel\(side\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert 'addEventListener("scroll"' in panel and "follow.checked = false" in panel
    assert "live.logs[side].stop()" in JS
    assert "followLabel.hidden = true" in JS, "a finished log has nothing to follow"
    assert "state.live.stop.hidden = true" in JS, "a finished run has nothing to stop"


def test_both_sides_are_always_shown_with_their_own_eta():
    assert "copy.NOTES.side_waiting" in JS and "copy.NOTES.side_running" in JS
    assert "event.plan" in JS


def test_apply_disables_every_apply_button_and_marks_the_row_the_router_reports():
    cell = re.search(r"function applyCell\([^)]*\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert "Boolean(state.applying)" in cell
    assert "copy.NOTES.applying" in cell
    assert "inUse(side, record, name)" in cell
    use = re.search(r"function inUse\([^)]*\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert "state.status.lock[side]" in use, "in use comes from the router's lock reading, not from the click"


def test_in_use_has_the_apply_buttons_box():
    assert "button.apply, .badge.in-use {" in CSS


def test_the_test_form_offers_a_target_and_a_duration():
    for key in ("test_target", "test_minutes"):
        assert f'"{key}"' in JS
    assert 'action("stop_test"' in JS and 'action("test"' in JS


def test_every_control_meets_the_44px_target_and_focus_stays_visible():
    assert "--target: 2.75rem" in CSS
    for selector in ("button {", "input[type=text], input[type=password], select {", ".choice {"):
        assert "min-height: var(--target)" in block(selector), f"{selector} is shorter than 44px"
    assert ":focus-visible" in CSS
    assert "outline: none" not in CSS and "outline: 0" not in CSS


def test_motion_is_colour_only_and_can_be_switched_off():
    assert "prefers-reduced-motion" in CSS
    assert not re.search(r"transition:[^;]*(width|height|top|left|transform)", CSS)


def test_the_error_banner_is_announced_and_delete_is_marked_destructive():
    assert re.search(r'<div id="banner" role="alert"', HTML)
    assert re.search(r'class:\s*"quiet danger"', JS) and ".danger" in CSS


def test_connect_shows_it_is_working_without_losing_what_was_typed():
    connect = re.search(r"async function onConnect\([^)]*\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert 'getElementById("connect")' in connect and ".disabled = true" in connect
    assert "render()" not in connect.split("finally")[0]


def test_the_main_view_never_hands_null_to_replace_children():
    main = re.search(r"function renderMain\(\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert ".filter(Boolean)" in main


def test_the_design_rulings_are_written_down():
    doc = (ROOT / "docs" / "design" / "2026-09-16-page-redesign.md").read_text(encoding="utf-8")
    for word in ("One accent", "Shape lock", "Spacing scale", "Logs are live DOM", "hover"):
        assert word in doc, word


def test_picking_a_test_target_never_rebuilds_the_page():
    """A full render() on a radio change tears the view down and the scroll position with it."""
    card = re.search(r"function testCard\(\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert not re.search(r"onchange:[^}]*render\(\)", card)


def test_the_test_lets_you_pick_a_4g_and_a_5g_band_together():
    assert 'sidePicker("lte"' in JS or '["lte", "nr"].map((side) => sidePicker(side' in JS
    assert "body.scell" in JS


def test_the_page_never_opens_a_browser_dialog():
    """window.prompt and window.confirm are blocked in embedded browsers and look nothing like
    the page; rename is inline and delete needs a second press instead."""
    assert "window.prompt" not in JS and "window.confirm" not in JS
    assert "confirmDelete" in JS and "state.editing" in JS


def test_log_lines_do_not_repeat_the_progress_bar_and_colour_the_verdict():
    """The bar already says "9 of 11 · about 3 min left"; a log line is the band and its verdict."""
    describe = re.search(r"function describe\(event\)\s*\{(.*?)\n\}", JS, re.S).group(1)
    assert "words.set_start" not in describe and "words.log_measuring" in describe
    assert "grade-${event.result.grade}" in describe and '"bad-text"' in describe
