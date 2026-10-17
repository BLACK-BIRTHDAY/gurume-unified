from __future__ import annotations

import os
from typing import Any, Dict, List, Optional
import httpx

HOTPEPPER_ENDPOINT = "http://webservice.recruit.co.jp/hotpepper/gourmet/v1/"


class HotPepperClient:
    """Client for Recruit Hot Pepper Gourmet API (Web Service)."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("HOTPEPPER_API_KEY")

    def _ensure_api_key(self) -> str:
        if not self.api_key:
            raise ValueError(
                "HOTPEPPER_API_KEY is not set. Please set the HOTPEPPER_API_KEY environment "
                "variable or pass api_key to HotPepperClient. You can get a free API key at "
                "https://webservice.recruit.co.jp/register/"
            )
        return self.api_key

    async def search(
        self,
        keyword: Optional[str] = None,
        area: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        range_level: int = 3,
        free_drink: Optional[bool] = None,
        free_food: Optional[bool] = None,
        private_room: Optional[bool] = None,
        non_smoking: Optional[bool] = None,
        parking: Optional[bool] = None,
        count: int = 10,
        page: int = 1,
    ) -> Dict[str, Any]:
        """Search restaurants via Hot Pepper Gourmet API."""
        key = self._ensure_api_key()
        count = max(1, min(count, 50))
        start = max(1, (page - 1) * count + 1)

        search_keyword = keyword or ""
        if area:
            search_keyword = f"{area} {search_keyword}".strip()

        params: Dict[str, Any] = {
            "key": key,
            "format": "json",
            "count": count,
            "start": start,
        }

        if search_keyword:
            params["keyword"] = search_keyword
        if lat is not None and lng is not None:
            params["lat"] = lat
            params["lng"] = lng
            params["range"] = range_level

        if free_drink:
            params["free_drink"] = 1
        if free_food:
            params["free_food"] = 1
        if private_room:
            params["private_room"] = 1
        if non_smoking:
            params["non_smoking"] = 1
        if parking:
            params["parking"] = 1

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(HOTPEPPER_ENDPOINT, params=params)
            resp.raise_for_status()
            data = resp.json().get("results", {})

        total_available = int(data.get("results_available", 0))
        raw_shops = data.get("shop", [])

        shops: List[Dict[str, Any]] = []
        for s in raw_shops:
            photo = s.get("photo", {})
            pc_photo = photo.get("pc", {})
            urls = s.get("urls", {})
            genre = s.get("genre", {})
            budget = s.get("budget", {})

            shops.append({
                "id": s.get("id"),
                "name": s.get("name"),
                "name_kana": s.get("name_kana"),
                "genre": genre.get("name"),
                "genre_catch": genre.get("catch"),
                "catch": s.get("catch"),
                "address": s.get("address"),
                "access": s.get("access"),
                "station_name": s.get("station_name"),
                "open_hours": s.get("open"),
                "close_days": s.get("close"),
                "budget": budget.get("name"),
                "budget_average": budget.get("average"),
                "image_url": pc_photo.get("l") or pc_photo.get("m"),
                "url": urls.get("pc"),
                "has_private_room": s.get("private_room") == "あり",
                "has_free_drink": s.get("free_drink") == "あり",
                "has_free_food": s.get("free_food") == "あり",
                "has_parking": s.get("parking") == "あり",
                "is_non_smoking": "全面禁煙" in str(s.get("non_smoking")),
                "course": s.get("course"),
            })

        has_next = (start + len(shops) - 1) < total_available

        return {
            "status": "success",
            "source": "hotpepper",
            "total_count": total_available,
            "page": page,
            "limit": count,
            "has_next_page": has_next,
            "items": shops,
        }

    async def get_details(self, shop_id: str) -> Dict[str, Any]:
        """Fetch detailed info for a single shop by its Hot Pepper ID."""
        key = self._ensure_api_key()
        params = {
            "key": key,
            "id": shop_id,
            "format": "json",
        }
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(HOTPEPPER_ENDPOINT, params=params)
            resp.raise_for_status()
            data = resp.json().get("results", {})

        raw_shops = data.get("shop", [])
        if not raw_shops:
            return {
                "status": "error",
                "message": f"Shop with ID '{shop_id}' not found.",
            }

        s = raw_shops[0]
        photo = s.get("photo", {})
        pc_photo = photo.get("pc", {})
        urls = s.get("urls", {})
        coupon_urls = s.get("coupon_urls", {})

        return {
            "status": "success",
            "source": "hotpepper",
            "shop": {
                "id": s.get("id"),
                "name": s.get("name"),
                "name_kana": s.get("name_kana"),
                "logo_image": s.get("logo_image"),
                "address": s.get("address"),
                "station_name": s.get("station_name"),
                "access": s.get("access"),
                "genre": s.get("genre", {}).get("name"),
                "sub_genre": s.get("sub_genre", {}).get("name"),
                "budget": s.get("budget", {}).get("name"),
                "budget_average": s.get("budget", {}).get("average"),
                "catch": s.get("catch"),
                "open_hours": s.get("open"),
                "close_days": s.get("close"),
                "capacity": s.get("capacity"),
                "has_private_room": s.get("private_room"),
                "has_free_drink": s.get("free_drink"),
                "has_free_food": s.get("free_food"),
                "non_smoking": s.get("non_smoking"),
                "parking": s.get("parking"),
                "card_payment": s.get("card"),
                "wifi": s.get("wifi"),
                "photos": {
                    "large": pc_photo.get("l"),
                    "medium": pc_photo.get("m"),
                    "small": pc_photo.get("s"),
                },
                "pc_url": urls.get("pc"),
                "sp_url": urls.get("sp"),
                "coupon_url": coupon_urls.get("pc") or coupon_urls.get("sp"),
            },
        }
