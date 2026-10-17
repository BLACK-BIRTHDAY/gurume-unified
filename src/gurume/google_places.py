from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import httpx

PLACES_SEARCH_TEXT_URL = "https://places.googleapis.com/v1/places:searchText"


class GooglePlacesClient:
    """Client for Google Maps Platform Places API (New)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GOOGLE_MAPS_API_KEY")

    def _ensure_api_key(self) -> str:
        if not self.api_key:
            raise ValueError(
                "GOOGLE_MAPS_API_KEY is not set. Please set the GOOGLE_MAPS_API_KEY environment "
                "variable or pass api_key to GooglePlacesClient."
            )
        return self.api_key

    async def search_restaurants(
        self,
        query: str,
        area: Optional[str] = None,
        language_code: str = "zh-CN",
        page_size: int = 5,
    ) -> Dict[str, Any]:
        """Search restaurants using Google Places API (New) Text Search."""
        key = self._ensure_api_key()
        full_query = f"{area or ''} {query}".strip() if area else query

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": key,
            "X-Goog-FieldMask": (
                "places.id,places.displayName,places.formattedAddress,places.rating,"
                "places.userRatingCount,places.priceLevel,places.googleMapsUri,"
                "places.websiteUri,places.primaryTypeDisplayName,places.currentOpeningHours.openNow"
            ),
        }

        body = {
            "textQuery": full_query,
            "includedType": "restaurant",
            "languageCode": language_code,
            "pageSize": max(1, min(page_size, 20)),
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(PLACES_SEARCH_TEXT_URL, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        raw_places = data.get("places", [])
        places: List[Dict[str, Any]] = []

        for p in raw_places:
            display_name = p.get("displayName", {}).get("text", "")
            primary_type = p.get("primaryTypeDisplayName", {}).get("text", "")
            opening_hours = p.get("currentOpeningHours", {})
            open_now = opening_hours.get("openNow")

            places.append({
                "id": p.get("id"),
                "name": display_name,
                "rating": p.get("rating"),
                "user_ratings_total": p.get("userRatingCount"),
                "primary_type": primary_type,
                "address": p.get("formattedAddress"),
                "price_level": p.get("priceLevel"),
                "google_maps_url": p.get("googleMapsUri"),
                "website_url": p.get("websiteUri"),
                "is_open_now": open_now,
            })

        return {
            "status": "success",
            "source": "google_places",
            "query": full_query,
            "count": len(places),
            "items": places,
        }
