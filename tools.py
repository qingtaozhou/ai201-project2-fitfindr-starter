"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os
import re
import itertools

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

_MODEL = "llama-3.3-70b-versatile"
_FIT_CARD_FALLBACK_TEMPLATES = itertools.cycle(
    [
        "Found {title} on {platform} for ${price}, and it pulls the whole look together. {outfit}",
        "This {platform} find was ${price}: {title}. The outfit keeps the vibe easy, styled, and wearable: {outfit}",
        "{title} for ${price} on {platform} feels like a strong thrift win. Styled this way, it lands casual but intentional: {outfit}",
    ]
)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "for",
    "i",
    "in",
    "of",
    "the",
    "to",
    "under",
    "with",
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


def _chat(prompt: str, temperature: float = 0.7) -> str:
    """Call Groq and return the assistant response text."""
    client = _get_groq_client()
    response = client.chat.completions.create(
        model=_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return response.choices[0].message.content.strip()


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def _search_tokens(text: str) -> set[str]:
    """Return lowercase searchable words, excluding common filler words."""
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in _STOPWORDS
    }


def _listing_text(listing: dict) -> str:
    """Combine listing fields that should count toward text relevance."""
    parts = [
        listing.get("title") or "",
        listing.get("description") or "",
        listing.get("category") or "",
        listing.get("condition") or "",
        listing.get("brand") or "",
        listing.get("platform") or "",
        " ".join(listing.get("style_tags") or []),
        " ".join(listing.get("colors") or []),
    ]
    return " ".join(parts).lower()


def _matches_size(listing_size: str, requested_size: str | None) -> bool:
    """Return whether a listing size matches the optional requested size."""
    if not requested_size:
        return True

    listing_tokens = set(re.findall(r"[a-z0-9]+", listing_size.lower()))
    requested = requested_size.lower().strip()
    requested_tokens = set(re.findall(r"[a-z0-9]+", requested))

    size_aliases = {
        "s": {"s", "small"},
        "m": {"m", "medium"},
        "l": {"l", "large"},
        "xl": {"xl", "xlarge", "extra", "large"},
    }
    acceptable_tokens = set(requested_tokens)
    for token in requested_tokens:
        acceptable_tokens.update(size_aliases.get(token, set()))

    return bool(listing_tokens & acceptable_tokens) or requested in listing_size.lower()


def _score_listing(listing: dict, description: str) -> int:
    """Score a listing by keyword and phrase overlap with the description."""
    query_tokens = _search_tokens(description)
    if not query_tokens:
        return 0

    title = (listing.get("title") or "").lower()
    listing_text = _listing_text(listing)
    listing_tokens = _search_tokens(listing_text)

    score = len(query_tokens & listing_tokens)
    for token in query_tokens:
        if token in title:
            score += 2

    query_phrase = " ".join(re.findall(r"[a-z0-9]+", description.lower()))
    if query_phrase and query_phrase in listing_text:
        score += 4

    return score


def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    if not description or not description.strip():
        return []

    scored_matches = []
    for listing in load_listings():
        if max_price is not None and listing.get("price", 0) > max_price:
            continue
        if not _matches_size(listing.get("size", ""), size):
            continue

        score = _score_listing(listing, description)
        if score > 0:
            scored_matches.append((score, listing.get("price", 0), listing))

    scored_matches.sort(key=lambda match: (-match[0], match[1]))
    return [listing for _, _, listing in scored_matches]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def _format_listing_for_prompt(listing: dict) -> str:
    """Format the selected listing fields for the styling prompt."""
    tags = ", ".join(listing.get("style_tags") or [])
    colors = ", ".join(listing.get("colors") or [])
    brand = listing.get("brand") or "unknown brand"
    return (
        f"Title: {listing.get('title')}\n"
        f"Category: {listing.get('category')}\n"
        f"Colors: {colors}\n"
        f"Style tags: {tags}\n"
        f"Size: {listing.get('size')}\n"
        f"Condition: {listing.get('condition')}\n"
        f"Price: ${listing.get('price')}\n"
        f"Brand: {brand}\n"
        f"Platform: {listing.get('platform')}\n"
        f"Description: {listing.get('description')}"
    )


def _format_wardrobe_for_prompt(wardrobe_items: list[dict]) -> str:
    """Format wardrobe item names and attributes for the styling prompt."""
    lines = []
    for item in wardrobe_items:
        colors = ", ".join(item.get("colors") or [])
        tags = ", ".join(item.get("style_tags") or [])
        notes = item.get("notes") or "no notes"
        lines.append(
            f"- {item.get('name')} ({item.get('category')}; "
            f"colors: {colors}; style tags: {tags}; notes: {notes})"
        )
    return "\n".join(lines)


def _fallback_outfit(new_item: dict, wardrobe_items: list[dict]) -> str:
    """Return a useful outfit suggestion if the LLM is unavailable."""
    title = new_item.get("title", "this thrifted item")
    tags = ", ".join(new_item.get("style_tags") or ["secondhand"])
    colors = ", ".join(new_item.get("colors") or ["neutral"])

    if not wardrobe_items:
        return (
            f"Style {title} with pieces that support its {tags} vibe. "
            f"Since the item includes {colors}, try simple denim or relaxed "
            "trousers, a clean base layer, and shoes that balance the shape. "
            "Keep accessories minimal if the listing is already bold, or add "
            "one textured accessory if the outfit needs more interest."
        )

    bottoms = [item for item in wardrobe_items if item.get("category") == "bottoms"]
    tops = [item for item in wardrobe_items if item.get("category") == "tops"]
    outerwear = [
        item for item in wardrobe_items if item.get("category") == "outerwear"
    ]
    shoes = [item for item in wardrobe_items if item.get("category") == "shoes"]
    accessories = [
        item for item in wardrobe_items if item.get("category") == "accessories"
    ]

    chosen = []
    for group in (tops, bottoms, outerwear, shoes, accessories):
        if group:
            chosen.append(group[0]["name"])

    return (
        f"Try {title} with {', '.join(chosen)}. These pieces keep the outfit "
        f"connected to the item's {tags} feel while balancing color, texture, "
        "and proportion with clothes already in the wardrobe."
    )


def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    if not isinstance(new_item, dict) or not new_item:
        return "I need a usable selected listing before I can suggest an outfit."

    wardrobe_items = []
    if isinstance(wardrobe, dict):
        wardrobe_items = wardrobe.get("items") or []

    listing_details = _format_listing_for_prompt(new_item)

    if wardrobe_items:
        prompt = (
            "You are FitFindr, a concise secondhand styling assistant.\n"
            "Suggest one or two complete outfits using the selected thrift "
            "listing and specific named pieces from the user's wardrobe. "
            "Explain briefly why the pieces work together. Do not invent "
            "wardrobe items that are not listed.\n\n"
            f"Selected listing:\n{listing_details}\n\n"
            f"User wardrobe:\n{_format_wardrobe_for_prompt(wardrobe_items)}"
        )
    else:
        prompt = (
            "You are FitFindr, a concise secondhand styling assistant.\n"
            "The user's wardrobe is empty. Suggest general item types, colors, "
            "proportions, and styling ideas that would pair well with the "
            "selected thrift listing. Do not pretend the user owns specific "
            "pieces.\n\n"
            f"Selected listing:\n{listing_details}"
        )

    try:
        response = _chat(prompt, temperature=0.7)
    except Exception:
        return _fallback_outfit(new_item, wardrobe_items)

    if response.strip():
        return response
    return _fallback_outfit(new_item, wardrobe_items)


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def _has_fit_card_details(new_item: dict) -> bool:
    """Return whether the listing has the key details needed for a fit card."""
    return all(new_item.get(field) is not None for field in ("title", "price", "platform"))


def _fallback_fit_card(outfit: str, new_item: dict) -> str:
    """Return a varied caption if the LLM is unavailable."""
    template = next(_FIT_CARD_FALLBACK_TEMPLATES)
    return template.format(
        title=new_item.get("title"),
        price=new_item.get("price"),
        platform=new_item.get("platform"),
        outfit=outfit,
    )

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not isinstance(outfit, str) or not outfit.strip():
        return "I couldn't create a fit card because the outfit suggestion was missing."
    if not isinstance(new_item, dict) or not new_item:
        return "I couldn't create a fit card because the selected listing was missing."
    if not _has_fit_card_details(new_item):
        return (
            "I couldn't create a fit card because the selected listing is missing "
            "its title, price, or platform."
        )

    listing_details = _format_listing_for_prompt(new_item)
    prompt = (
        "You are FitFindr. Write a casual, social-media-ready fit card caption "
        "in 2-4 sentences. Mention the selected item title, price, and platform "
        "naturally once each. Summarize the outfit vibe from the styling "
        "suggestion. Sound like a real OOTD post, not an ad.\n\n"
        f"Selected listing:\n{listing_details}\n\n"
        f"Outfit suggestion:\n{outfit}"
    )

    try:
        response = _chat(prompt, temperature=1.0)
    except Exception:
        return _fallback_fit_card(outfit, new_item)

    if response.strip():
        return response
    return _fallback_fit_card(outfit, new_item)
