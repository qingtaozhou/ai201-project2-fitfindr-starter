import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import tools
from tools import create_fit_card, search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe


def test_search_listings_returns_matching_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)

    assert isinstance(results, list)
    assert results
    assert all(isinstance(item, dict) for item in results)
    assert results[0]["id"] == "lst_002"


def test_search_listings_returns_empty_list_when_no_listing_matches():
    results = search_listings("designer ballgown", size="XXS", max_price=5)

    assert results == []


def test_search_listings_filters_by_max_price():
    results = search_listings("jacket", size=None, max_price=40)

    assert results
    assert all(item["price"] <= 40 for item in results)


def test_search_listings_filters_by_size_case_insensitively():
    results = search_listings("90s track jacket", size="m", max_price=None)

    assert results
    assert all("m" in item["size"].lower() for item in results)


def test_search_listings_allows_partial_size_matches():
    results = search_listings("baby tee", size="M", max_price=None)

    assert results
    assert any(item["size"] == "S/M" for item in results)


def test_search_listings_blank_description_returns_empty_list():
    assert search_listings("", size=None, max_price=None) == []
    assert search_listings("   ", size=None, max_price=None) == []


def test_suggest_outfit_uses_groq_prompt_with_wardrobe_items(monkeypatch):
    calls = []

    def fake_chat(prompt, temperature=0.7):
        calls.append({"prompt": prompt, "temperature": temperature})
        return "Wear it with Baggy straight-leg jeans, dark wash."

    monkeypatch.setattr(tools, "_chat", fake_chat)
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    outfit = suggest_outfit(item, get_example_wardrobe())

    assert outfit == "Wear it with Baggy straight-leg jeans, dark wash."
    assert calls
    assert calls[0]["temperature"] == 0.7
    assert "Baggy straight-leg jeans, dark wash" in calls[0]["prompt"]
    assert "Do not invent wardrobe items" in calls[0]["prompt"]


def test_suggest_outfit_handles_empty_wardrobe_without_crashing(monkeypatch):
    def fake_chat(prompt, temperature=0.7):
        return "Try relaxed denim, simple shoes, and minimal accessories."

    monkeypatch.setattr(tools, "_chat", fake_chat)
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    outfit = suggest_outfit(item, get_empty_wardrobe())

    assert isinstance(outfit, str)
    assert outfit
    assert "relaxed denim" in outfit


def test_suggest_outfit_returns_helpful_error_for_missing_item():
    outfit = suggest_outfit({}, get_example_wardrobe())

    assert "selected listing" in outfit.lower()


def test_suggest_outfit_falls_back_if_llm_call_fails(monkeypatch):
    def fake_chat(prompt, temperature=0.7):
        raise RuntimeError("no live LLM in tests")

    monkeypatch.setattr(tools, "_chat", fake_chat)
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    outfit = suggest_outfit(item, get_example_wardrobe())

    assert isinstance(outfit, str)
    assert outfit
    assert "Baggy straight-leg jeans, dark wash" in outfit


def test_create_fit_card_returns_error_for_empty_outfit():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    fit_card = create_fit_card("", item)

    assert "outfit suggestion was missing" in fit_card.lower()


def test_create_fit_card_returns_error_for_missing_listing_details():
    fit_card = create_fit_card("Wear it with jeans and sneakers.", {"title": "Tee"})

    assert "title, price, or platform" in fit_card.lower()


def test_create_fit_card_calls_llm_with_high_temperature(monkeypatch):
    calls = []

    def fake_chat(prompt, temperature=0.7):
        calls.append({"prompt": prompt, "temperature": temperature})
        return "Found the Y2K Baby Tee on depop for $18.00. The look feels playful and casual."

    monkeypatch.setattr(tools, "_chat", fake_chat)
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    fit_card = create_fit_card("Wear it with jeans and chunky sneakers.", item)

    assert "Y2K Baby Tee" in fit_card
    assert calls
    assert calls[0]["temperature"] >= 1.0
    assert "Outfit suggestion" in calls[0]["prompt"]
    assert "social-media-ready" in calls[0]["prompt"]


def test_create_fit_card_outputs_can_vary_for_same_input(monkeypatch):
    responses = iter(
        [
            "Caption one: playful baby tee energy with denim.",
            "Caption two: same tee, different thrift-card wording.",
        ]
    )

    def fake_chat(prompt, temperature=0.7):
        return next(responses)

    monkeypatch.setattr(tools, "_chat", fake_chat)
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    outfit = "Wear it with jeans and chunky sneakers."

    first = create_fit_card(outfit, item)
    second = create_fit_card(outfit, item)

    assert first != second


def test_create_fit_card_fallback_outputs_can_vary(monkeypatch):
    def fake_chat(prompt, temperature=0.7):
        raise RuntimeError("no live LLM in tests")

    monkeypatch.setattr(tools, "_chat", fake_chat)
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    outfit = "Wear it with jeans and chunky sneakers."

    outputs = {create_fit_card(outfit, item) for _ in range(3)}

    assert len(outputs) > 1
