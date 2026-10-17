from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

from .hotpepper import HotPepperClient
from .search import SearchRequest, SortType


class UnifiedSearchEngine:
    """Unified dual-source restaurant search engine across Tabelog and Hot Pepper."""

    def __init__(self, hotpepper_key: Optional[str] = None):
        self.hotpepper_client = HotPepperClient(api_key=hotpepper_key)

    async def search(
        self,
        keyword: str,
        area: Optional[str] = None,
        sources: Optional[List[str]] = None,
        private_room: bool = False,
        free_drink: bool = False,
        free_food: bool = False,
        non_smoking: bool = False,
        limit_per_source: int = 5,
    ) -> Dict[str, Any]:
        """Concurrently search both Tabelog and Hot Pepper, returning normalized results."""
        target_sources = [s.lower() for s in (sources or ["tabelog", "hotpepper"])]
        tasks = []
        task_names = []

        # 1. Tabelog search
        if "tabelog" in target_sources:
            tabelog_kw = f"{area or ''} {keyword}".strip() if area else keyword
            tasks.append(self._search_tabelog(keyword=tabelog_kw, limit=limit_per_source))
            task_names.append("tabelog")

        # 2. Hot Pepper search
        if "hotpepper" in target_sources:
            tasks.append(
                self.hotpepper_client.search(
                    keyword=keyword,
                    area=area,
                    private_room=private_room or None,
                    free_drink=free_drink or None,
                    free_food=free_food or None,
                    non_smoking=non_smoking or None,
                    count=limit_per_source,
                )
            )
            task_names.append("hotpepper")

        results = await asyncio.gather(*tasks, return_exceptions=True)

        unified_items: List[Dict[str, Any]] = []
        sources_status: Dict[str, Any] = {}

        for name, res in zip(task_names, results):
            if isinstance(res, Exception):
                sources_status[name] = {"status": "error", "message": str(res)}
                continue

            if name == "tabelog":
                tabelog_shops = self._normalize_tabelog(res)
                sources_status["tabelog"] = {
                    "status": "success",
                    "count": len(tabelog_shops),
                }
                unified_items.extend(tabelog_shops)

            elif name == "hotpepper":
                hp_shops = self._normalize_hotpepper(res)
                sources_status["hotpepper"] = {
                    "status": "success",
                    "total_available": res.get("total_count", len(hp_shops)),
                    "count": len(hp_shops),
                }
                unified_items.extend(hp_shops)

        return {
            "status": "success",
            "mode": "unified",
            "query": {
                "keyword": keyword,
                "area": area,
                "sources": target_sources,
            },
            "sources_status": sources_status,
            "total_returned": len(unified_items),
            "restaurants": unified_items,
        }

    async def _search_tabelog(self, keyword: str, limit: int) -> Any:
        req = SearchRequest(keyword=keyword, sort_type=SortType.RANKING, max_pages=1)
        resp = await req.search()
        return resp.restaurants[:limit]

    def _normalize_tabelog(self, restaurants: List[Any]) -> List[Dict[str, Any]]:
        normalized = []
        for r in restaurants:
            budget_parts = []
            if getattr(r, "dinner_price", None):
                budget_parts.append(f"夜: {r.dinner_price}")
            if getattr(r, "lunch_price", None):
                budget_parts.append(f"昼: {r.lunch_price}")
            budget_str = " | ".join(budget_parts) if budget_parts else "未设定"

            img_urls = getattr(r, "image_urls", []) or []
            main_img = img_urls[0] if img_urls else None

            highlights = []
            if getattr(r, "rating", None):
                highlights.append(f"★ 食べログ {r.rating}")
            if getattr(r, "review_count", None):
                highlights.append(f"{r.review_count}条评价")
            if getattr(r, "has_reservation", False):
                highlights.append("可网上预约")

            normalized.append({
                "source": "tabelog",
                "source_title": "食べログ (Tabelog)",
                "name": r.name,
                "rating": r.rating,
                "review_count": r.review_count,
                "genre": ", ".join(r.genres) if r.genres else "料理",
                "address": r.address or r.area or "",
                "access": r.station or r.area or "",
                "budget": budget_str,
                "url": r.url,
                "image_url": main_img,
                "highlights": highlights,
                "description": r.description or "",
            })
        return normalized

    def _normalize_hotpepper(self, hp_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        normalized = []
        for s in hp_data.get("items", []):
            highlights = ["Hot Pepper 认证"]
            if s.get("has_private_room"):
                highlights.append("個室あり (有包厢)")
            if s.get("has_free_drink"):
                highlights.append("飲み放題あり (有畅饮)")
            if s.get("has_free_food"):
                highlights.append("食べ放題あり (有放题)")
            if s.get("is_non_smoking"):
                highlights.append("禁煙席あり (禁烟)")
            if s.get("has_parking"):
                highlights.append("駐車場あり (有停车位)")

            normalized.append({
                "source": "hotpepper",
                "source_title": "ホットペッパー グルメ (Hot Pepper)",
                "name": s.get("name"),
                "rating": None,
                "review_count": None,
                "genre": s.get("genre") or "居酒屋/料理",
                "address": s.get("address") or "",
                "access": s.get("access") or s.get("station_name") or "",
                "budget": s.get("budget") or "未设定",
                "url": s.get("url"),
                "image_url": s.get("image_url"),
                "highlights": highlights,
                "description": s.get("catch") or s.get("genre_catch") or "",
            })
        return normalized
