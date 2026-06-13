import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import agent
from app import handle_query


def test_run_agent_passes_state_between_tools(monkeypatch):
    selected_item = {
        "id": "lst_test",
        "title": "Test Graphic Tee",
        "description": "A test listing.",
        "category": "tops",
        "style_tags": ["vintage", "graphic tee"],
        "size": "M",
        "condition": "good",
        "price": 20.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }
    outfit_text = "Wear it with baggy jeans and chunky sneakers."
    calls = {}

    def fake_search_listings(description, size=None, max_price=None):
        calls["search_args"] = {
            "description": description,
            "size": size,
            "max_price": max_price,
        }
        return [selected_item]

    def fake_suggest_outfit(new_item, wardrobe):
        calls["suggest_item"] = new_item
        calls["suggest_wardrobe"] = wardrobe
        return outfit_text

    def fake_create_fit_card(outfit, new_item):
        calls["fit_card_outfit"] = outfit
        calls["fit_card_item"] = new_item
        return "Fit card caption."

    monkeypatch.setattr(agent, "search_listings", fake_search_listings)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    wardrobe = {"items": [{"name": "Baggy jeans"}]}
    session = agent.run_agent("looking for a vintage graphic tee under $30", wardrobe)

    assert session["error"] is None
    assert session["parsed"] == {
        "description": "vintage graphic tee",
        "size": None,
        "max_price": 30.0,
    }
    assert session["selected_item"] is selected_item
    assert calls["suggest_item"] is session["selected_item"]
    assert calls["suggest_wardrobe"] is session["wardrobe"]
    assert session["outfit_suggestion"] == outfit_text
    assert calls["fit_card_outfit"] == session["outfit_suggestion"]
    assert calls["fit_card_item"] is session["selected_item"]
    assert session["fit_card"] == "Fit card caption."


def test_run_agent_stops_after_no_search_results(monkeypatch):
    calls = {"suggest": 0, "fit_card": 0}

    def fake_search_listings(description, size=None, max_price=None):
        return []

    def fake_suggest_outfit(new_item, wardrobe):
        calls["suggest"] += 1
        return "This should not be called."

    def fake_create_fit_card(outfit, new_item):
        calls["fit_card"] += 1
        return "This should not be called."

    monkeypatch.setattr(agent, "search_listings", fake_search_listings)
    monkeypatch.setattr(agent, "suggest_outfit", fake_suggest_outfit)
    monkeypatch.setattr(agent, "create_fit_card", fake_create_fit_card)

    session = agent.run_agent("designer ballgown size XXS under $5", {"items": []})

    assert session["error"]
    assert session["search_results"] == []
    assert session["selected_item"] is None
    assert session["outfit_suggestion"] is None
    assert session["fit_card"] is None
    assert calls == {"suggest": 0, "fit_card": 0}


def test_handle_query_maps_success_session_to_three_panels(monkeypatch):
    selected_item = {
        "title": "Test Jacket",
        "description": "A lightweight test jacket.",
        "style_tags": ["90s", "athletic"],
        "size": "M",
        "condition": "excellent",
        "price": 45.0,
        "colors": ["navy", "white"],
        "brand": "Champion",
        "platform": "poshmark",
    }

    def fake_run_agent(query, wardrobe):
        return {
            "selected_item": selected_item,
            "outfit_suggestion": "Wear it with jeans.",
            "fit_card": "A caption.",
            "error": None,
        }

    monkeypatch.setattr("app.run_agent", fake_run_agent)

    listing_text, outfit_text, fit_card_text = handle_query(
        "90s track jacket size M",
        "Example wardrobe",
    )

    assert "Test Jacket" in listing_text
    assert "Price: $45.0" in listing_text
    assert outfit_text == "Wear it with jeans."
    assert fit_card_text == "A caption."


def test_handle_query_maps_error_to_first_panel(monkeypatch):
    def fake_run_agent(query, wardrobe):
        return {"error": "No matching listings found."}

    monkeypatch.setattr("app.run_agent", fake_run_agent)

    listing_text, outfit_text, fit_card_text = handle_query(
        "designer ballgown size XXS under $5",
        "Example wardrobe",
    )

    assert listing_text == "No matching listings found."
    assert outfit_text == ""
    assert fit_card_text == ""
