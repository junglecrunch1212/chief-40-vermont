"""Tests for prefix parser — command recognition from text input."""

import pytest
from pib.ingest import parse_prefix


class TestPrefixParser:
    def test_grocery_list(self):
        result = parse_prefix("grocery: milk, eggs, bread")
        assert result is not None
        assert result["shape"] == "lists"
        assert result["metadata"]["list_name"] == "grocery"
        assert "milk, eggs, bread" in result["content"]

    def test_costco_list(self):
        result = parse_prefix("costco: paper towels, water")
        assert result["shape"] == "lists"
        assert result["metadata"]["list_name"] == "costco"

    def test_target_list(self):
        result = parse_prefix("target: diapers, wipes")
        assert result["shape"] == "lists"
        assert result["metadata"]["list_name"] == "target"

    def test_hardware_list(self):
        result = parse_prefix("hardware: 2x4 boards, screws")
        assert result["shape"] == "lists"
        assert result["metadata"]["list_name"] == "hardware"

    def test_james_task(self):
        result = parse_prefix("james: call the plumber")
        assert result["shape"] == "tasks"
        assert result["metadata"]["assignee"] == "m-james"

    def test_laura_task(self):
        result = parse_prefix("laura: review insurance docs")
        assert result["shape"] == "tasks"
        assert result["metadata"]["assignee"] == "m-laura"

    def test_buy_prefix(self):
        result = parse_prefix("buy diapers")
        assert result["shape"] == "tasks"
        assert result["metadata"]["item_type"] == "purchase"

    def test_call_prefix(self):
        result = parse_prefix("call the dentist")
        assert result["shape"] == "tasks"
        assert result["metadata"]["requires"] == "phone"

    def test_remember_prefix(self):
        result = parse_prefix("remember Charlie's teacher is Mrs. Johnson")
        assert result["shape"] == "memory"
        assert result["metadata"]["action"] == "save_fact"

    def test_meds_taken(self):
        result = parse_prefix("meds taken")
        assert result["shape"] == "state"
        assert result["metadata"]["action"] == "medication_taken"

    def test_meds_alone(self):
        result = parse_prefix("meds")
        assert result["shape"] == "state"
        assert result["metadata"]["action"] == "medication_taken"

    def test_sleep_great(self):
        result = parse_prefix("sleep great")
        assert result["shape"] == "state"
        assert result["metadata"]["action"] == "sleep_report"

    def test_sleep_rough(self):
        result = parse_prefix("sleep rough")
        assert result["shape"] == "state"

    def test_no_match(self):
        result = parse_prefix("what should I do next?")
        assert result is None

    def test_case_insensitive(self):
        result = parse_prefix("GROCERY: milk")
        assert result is not None
        assert result["shape"] == "lists"

    def test_whitespace_handling(self):
        result = parse_prefix("  grocery:   milk, eggs  ")
        assert result is not None
