"""Tests for project signal detection and template matching."""

from pib.project.detection import detect_project, _match_template


class TestDetectProject:
    """Tests for detect_project()."""

    def test_piano_teacher_detected(self):
        """A multi-signal message about finding a piano teacher triggers detection."""
        result = detect_project("Help me find a piano teacher for Charlie, I want to compare options and prices")
        assert result is not None
        assert result["confidence"] >= 0.5
        assert len(result["signals"]) >= 2

    def test_adu_project_detected(self):
        """A construction project brief triggers detection."""
        result = detect_project("We need to build an ADU in the backyard. Get permits, find a contractor, get quotes.")
        assert result is not None
        assert result["confidence"] > 0.5
        assert "involves_physical_world" in result["signals"]

    def test_travel_detected(self):
        """Travel planning with research and timeline triggers detection."""
        result = detect_project("Plan a family vacation to Hawaii. Research hotels, compare flights, book by next month.")
        assert result is not None
        assert result["suggested_template"] == "book_travel"

    def test_emergency_detected(self):
        """Emergency repair scenarios trigger detection with correct template."""
        result = detect_project("Emergency! The pipe burst, need to find a plumber to repair it and get a cost estimate.")
        assert result is not None
        assert result["suggested_template"] == "emergency_repair"

    def test_enrollment_detected(self):
        """School enrollment with deadline triggers detection."""
        result = detect_project("We need to register Charlie for summer camp. Compare programs and sign up before the deadline.")
        assert result is not None
        assert result["suggested_template"] == "enrollment_deadline"

    def test_buy_milk_not_detected(self):
        """Simple one-step tasks should NOT be detected as projects."""
        result = detect_project("Buy milk")
        assert result is None

    def test_is_laura_free_not_detected(self):
        """Simple questions should NOT be detected as projects."""
        result = detect_project("Is Laura free tonight?")
        assert result is None

    def test_short_message_not_detected(self):
        """Very short messages should return None."""
        result = detect_project("hi")
        assert result is None

    def test_empty_message_not_detected(self):
        """Empty/None messages should return None."""
        assert detect_project("") is None
        assert detect_project("short") is None

    def test_single_signal_not_enough(self):
        """A message with only one signal should NOT trigger detection (needs 2+)."""
        result = detect_project("I want to find a good plumber")
        # This only matches involves_external_parties — need at least 2
        # Actually "find" matches both involves_external_parties and involves_research
        # Let's use something more targeted
        result = detect_project("The contractor did a good job yesterday")
        assert result is None

    def test_confidence_scales_with_signals(self):
        """More signals should yield higher confidence."""
        # 2 signals
        r2 = detect_project("Find a contractor and get quotes")
        # 3+ signals
        r3 = detect_project("Find a contractor, get quotes, schedule by next month, and compare reviews")
        assert r2 is not None
        assert r3 is not None
        assert r3["confidence"] >= r2["confidence"]


class TestMatchTemplate:
    """Tests for _match_template()."""

    def test_construction_keywords(self):
        result = _match_template(["involves_physical_world", "involves_money"], "Build an ADU in the backyard")
        assert result == "construction_project"

    def test_travel_keywords(self):
        result = _match_template(["involves_research", "involves_money"], "Book a vacation to Hawaii")
        assert result == "book_travel"

    def test_enrollment_keywords(self):
        result = _match_template(["involves_timeline", "involves_research"], "Enroll Charlie in summer camp")
        assert result == "enrollment_deadline"

    def test_emergency_keywords(self):
        result = _match_template(["involves_physical_world"], "Emergency! Pipe burst flooding the basement")
        assert result == "emergency_repair"

    def test_find_service_provider_fallback(self):
        """External parties + research without specific keywords → find_service_provider."""
        result = _match_template(
            ["involves_external_parties", "involves_research"],
            "Help me research and hire someone for this task"
        )
        assert result == "find_service_provider"

    def test_administrative_default(self):
        """No specific keywords → administrative_cleanup."""
        result = _match_template(["involves_money", "multi_step_language"], "Plan for budgeting the project")
        assert result == "administrative_cleanup"
