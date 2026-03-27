#!/usr/bin/env python3
"""
增强版地理处理器。

负责将 geo_extractor 的粗粒度结果进一步归一化为可直接入库的结构化地理实体。
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from news_crawler.utils.geo_dictionary_loader import GeoDictionaryLoader, get_loader


class EnhancedGeoProcessor:
    """Normalize extracted geo entities into a stable dictionary-backed structure."""

    _ASCII_STOPWORDS = {
        "the", "and", "for", "with", "from", "into", "about", "after", "before",
        "news", "video", "live", "update", "breaking", "report", "reports",
        "over", "under", "near", "amid", "amidst", "against", "said", "says",
        # Common suffix fragments from hyphenated proper nouns (e.g. Mar-a-Lago -> Lago)
        "lago",
    }

    # Company / org / person names that happen to be alternate city names in GeoNames.
    # These must NEVER be fed into city/admin1 lookup.
    _KNOWN_NON_GEO: set[str] = {
        # Tech companies
        "google", "meta", "apple", "amazon", "microsoft", "netflix", "tesla",
        "facebook", "twitter", "uber", "airbnb", "spotify", "adobe", "oracle",
        "nvidia", "intel", "samsung", "palantir", "anduril", "openai", "anthropic",
        "openreach", "spacex", "starlink", "broadcom", "qualcomm", "snapchat",
        # Media
        "reuters", "bloomberg", "cnbc", "msnbc", "huffpost", "buzzfeed",
        # Finance / institutions
        "nasdaq", "nyse", "ftse", "ares", "merck", "pfizer", "novartis",
        # Known false-positive single-word triggers
        "trump", "biden", "vance", "rubio", "hegseth", "putin", "netanyahu",
        "nato", "opec", "swift",
    }

    def __init__(self, loader: Optional[GeoDictionaryLoader] = None):
        self._loader = loader or get_loader()

    def normalize_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not entities:
            return []

        normalized_entities: List[Dict[str, Any]] = []
        seen_geo_keys: set[str] = set()
        country_hint: Optional[str] = None

        for entity in entities:
            normalized = self.normalize_entity(entity, country_hint=country_hint)
            if not normalized:
                continue

            geo_key = (normalized.get("geo_key") or "").strip()
            if not geo_key or geo_key in seen_geo_keys:
                continue
            seen_geo_keys.add(geo_key)

            normalized_entities.append(normalized)
            if normalized.get("country_code") and not country_hint:
                country_hint = normalized["country_code"]

        return normalized_entities

    def extract_candidates_from_text(
        self,
        text: str,
        *,
        country_hint: Optional[str] = None,
        max_entities: int = 10,
    ) -> List[Dict[str, Any]]:
        if not text:
            return []

        out: List[Dict[str, Any]] = []
        seen_geo_keys: set[str] = set()
        effective_country_hint = country_hint

        for candidate in self._iter_text_candidates(text):
            inferred_type = self._infer_candidate_type(candidate)
            matched = self._resolve_record(
                name=candidate,
                extracted_type=inferred_type,
                country_hint=effective_country_hint,
            )
            if matched is None:
                continue

            normalized = self._build_record_payload(
                name=candidate,
                extracted_type=inferred_type,
                match_type=matched["match_type"],
                record=matched["record"],
                confidence=self._confidence_for_match(inferred_type, matched["match_type"]),
                geo_key_hint="",
                country_hint=effective_country_hint,
            )
            normalized["matched_text"] = candidate
            geo_key = (normalized.get("geo_key") or "").strip()
            if not geo_key or geo_key in seen_geo_keys:
                continue
            seen_geo_keys.add(geo_key)
            out.append(normalized)
            if normalized.get("country_code") and not effective_country_hint:
                effective_country_hint = normalized["country_code"]
            if len(out) >= max_entities:
                break

        return out

    def merge_entities(self, *groups: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        ordered_keys: List[str] = []
        for group in groups:
            for entity in group or []:
                geo_key = (entity.get("geo_key") or "").strip()
                if not geo_key:
                    continue
                if geo_key not in merged:
                    merged[geo_key] = dict(entity)
                    ordered_keys.append(geo_key)
                    continue
                existing = merged[geo_key]
                if float(entity.get("confidence") or 0.0) > float(existing.get("confidence") or 0.0):
                    merged[geo_key] = {**existing, **entity}
                else:
                    for key, value in entity.items():
                        if existing.get(key) in (None, "", []):
                            existing[key] = value
        return [merged[key] for key in ordered_keys]

    def normalize_entity(
        self,
        entity: Dict[str, Any],
        *,
        country_hint: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        name = (entity.get("name") or "").strip()
        extracted_type = self._normalize_extracted_type(entity.get("type"))
        geo_key_hint = (entity.get("geo_key") or "").strip().upper()
        confidence = float(entity.get("confidence") or 1.0)
        if not name:
            return None

        extracted_country_hint = self._extract_country_hint(geo_key_hint)
        effective_country_hint = country_hint or extracted_country_hint
        matched = self._resolve_record(
            name=name,
            extracted_type=extracted_type,
            country_hint=effective_country_hint,
        )

        if matched is None:
            return self._build_fallback_payload(
                name=name,
                extracted_type=extracted_type,
                geo_key_hint=geo_key_hint,
                confidence=confidence,
                country_hint=effective_country_hint,
            )

        match_type = matched["match_type"]
        record = matched["record"]
        return self._build_record_payload(
            name=name,
            extracted_type=extracted_type,
            match_type=match_type,
            record=record,
            confidence=confidence,
            geo_key_hint=geo_key_hint,
            country_hint=effective_country_hint,
        )

    def _resolve_record(
        self,
        *,
        name: str,
        extracted_type: str,
        country_hint: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        candidates = self._resolve_candidates(name=name, country_hint=country_hint)
        if not candidates:
            stripped = self._strip_inline_location_suffix(name)
            if stripped != name:
                candidates = self._resolve_candidates(name=stripped, country_hint=country_hint)
        if not candidates:
            return None

        ranked = sorted(
            candidates,
            key=lambda item: self._candidate_score(
                match_type=item["match_type"],
                record=item["record"],
                extracted_type=extracted_type,
                country_hint=country_hint,
            ),
            reverse=True,
        )
        return ranked[0]

    def _resolve_candidates(self, *, name: str, country_hint: Optional[str]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        city_matches = self._loader.find_city_all(name, country_code=country_hint)
        if not city_matches and country_hint:
            city_matches = [
                record for record in self._loader.find_city_all(name)
                if self._allow_global_city_fallback(name, record)
            ]
        for record in city_matches:
            out.append({"match_type": "city", "record": record})
        admin1_matches = self._loader.find_admin1_all(name, country_code=country_hint)
        if not admin1_matches and country_hint:
            admin1_matches = self._loader.find_admin1_all(name)
        for record in admin1_matches:
            out.append({"match_type": "admin1", "record": record})
        for record in self._loader.find_country_all(name):
            out.append({"match_type": "country", "record": record})
        return out

    def _allow_global_city_fallback(self, name: str, record: Dict[str, Any]) -> bool:
        population = int(record.get("population") or 0)
        if population >= 500_000:
            return True
        if bool(record.get("is_capital")):
            return True
        stripped = name.strip()
        if re.search(r"[\u4e00-\u9fff]", stripped):
            return True
        if " " in stripped or "-" in stripped or "'" in stripped:
            return True
        return False

    def _candidate_score(
        self,
        *,
        match_type: str,
        record: Dict[str, Any],
        extracted_type: str,
        country_hint: Optional[str],
    ) -> float:
        score = 0.0
        type_priority = {"city": 0.62, "admin1": 0.58, "country": 0.52}
        score += type_priority.get(match_type, 0.5)

        if extracted_type == match_type:
            score += 0.22
        elif extracted_type == "admin1" and match_type == "city":
            score -= 0.08
        elif extracted_type == "city" and match_type == "admin1":
            score -= 0.05

        record_country = (record.get("country_code") or "").upper()
        if country_hint and record_country == country_hint.upper():
            score += 0.18

        if match_type == "city":
            population = int(record.get("population") or 0)
            if population >= 5_000_000:
                score += 0.10
            elif population >= 1_000_000:
                score += 0.07
            elif population >= 200_000:
                score += 0.04

        if match_type == "country":
            score += 0.02
        return score

    def _build_record_payload(
        self,
        *,
        name: str,
        extracted_type: str,
        match_type: str,
        record: Dict[str, Any],
        confidence: float,
        geo_key_hint: str,
        country_hint: Optional[str],
    ) -> Dict[str, Any]:
        country_code = (record.get("country_code") or country_hint or self._extract_country_hint(geo_key_hint) or "UNKNOWN")[:10]
        if match_type == "country":
            return {
                "name": record.get("country_name_zh") or record.get("country_name") or name,
                "geo_key": (record.get("country_code") or geo_key_hint or country_code)[:20],
                "type": "country",
                "confidence": confidence,
                "country_code": country_code,
                "country_name": record.get("country_name_zh") or record.get("country_name") or name,
                "admin1_code": None,
                "admin1_name": None,
                "city_name": None,
                "precision_level": "COUNTRY",
                "display_mode": "POLYGON",
                "geojson_key": record.get("geojson_key") or record.get("country_code") or country_code,
                "lat": record.get("lat"),
                "lng": record.get("lng"),
            }

        if match_type == "admin1":
            admin1_code = (record.get("admin1_code") or "")[:10]
            geo_key = record.get("geojson_key") or self._compose_admin1_geo_key(country_code, admin1_code, geo_key_hint)
            return {
                "name": record.get("admin1_name_zh") or record.get("admin1_name") or name,
                "geo_key": geo_key[:20],
                "type": "province",
                "confidence": confidence,
                "country_code": country_code,
                "country_name": record.get("country_name"),
                "admin1_code": admin1_code or None,
                "admin1_name": record.get("admin1_name_zh") or record.get("admin1_name") or name,
                "city_name": None,
                "precision_level": "ADMIN1",
                "display_mode": "POLYGON",
                "geojson_key": record.get("geojson_key") or geo_key,
                "lat": record.get("lat"),
                "lng": record.get("lng"),
            }

        source_id = str(record.get("source_id") or "").strip()
        city_geo_key = self._compose_city_geo_key(country_code, source_id, geo_key_hint, name)
        return {
            "name": record.get("city_name_zh") or record.get("city_name") or name,
            "geo_key": city_geo_key[:20],
            "type": "city",
            "confidence": confidence,
            "country_code": country_code,
            "country_name": record.get("country_name"),
            "admin1_code": (record.get("admin1_code") or "")[:10] or None,
            "admin1_name": record.get("admin1_name"),
            "city_name": record.get("city_name_zh") or record.get("city_name") or name,
            "precision_level": "CITY",
            "display_mode": "POINT",
            "geojson_key": record.get("geojson_key") or city_geo_key,
            "lat": record.get("lat"),
            "lng": record.get("lng"),
        }

    def _build_fallback_payload(
        self,
        *,
        name: str,
        extracted_type: str,
        geo_key_hint: str,
        confidence: float,
        country_hint: Optional[str],
    ) -> Dict[str, Any]:
        country_code = (self._extract_country_hint(geo_key_hint) or country_hint or "UNKNOWN")[:10]
        if extracted_type == "admin1":
            return {
                "name": name,
                "geo_key": self._fallback_geo_key(country_code, name, prefix="A1")[:20],
                "type": "province",
                "confidence": confidence,
                "country_code": country_code,
                "country_name": None,
                "admin1_code": None,
                "admin1_name": name,
                "city_name": None,
                "precision_level": "ADMIN1",
                "display_mode": "POLYGON",
                "geojson_key": geo_key_hint or self._fallback_geo_key(country_code, name, prefix="A1"),
                "lat": None,
                "lng": None,
            }

        if extracted_type == "city":
            return {
                "name": name,
                "geo_key": self._fallback_geo_key(country_code, name, prefix="CT")[:20],
                "type": "city",
                "confidence": confidence,
                "country_code": country_code,
                "country_name": None,
                "admin1_code": None,
                "admin1_name": None,
                "city_name": name,
                "precision_level": "CITY",
                "display_mode": "POINT",
                "geojson_key": geo_key_hint or self._fallback_geo_key(country_code, name, prefix="CT"),
                "lat": None,
                "lng": None,
            }

        return {
            "name": name,
            "geo_key": (geo_key_hint or country_code or "UNKNOWN")[:20],
            "type": "country",
            "confidence": confidence,
            "country_code": country_code,
            "country_name": name,
            "admin1_code": None,
            "admin1_name": None,
            "city_name": None,
            "precision_level": "COUNTRY",
            "display_mode": "POLYGON",
            "geojson_key": geo_key_hint or country_code,
            "lat": None,
            "lng": None,
        }

    def _iter_text_candidates(self, text: str) -> List[str]:
        seen: set[str] = set()
        candidates: List[str] = []

        zh_chunks = re.findall(r"[\u4e00-\u9fff]{2,12}", text)
        for chunk in zh_chunks:
            for value in (chunk, self._strip_inline_location_suffix(chunk), self._loader._strip_suffixes(chunk)):
                cleaned = value.strip()
                if len(cleaned) < 2 or cleaned in seen:
                    continue
                seen.add(cleaned)
                candidates.append(cleaned)

        # Use * (not ?) so all hyphen segments of a compound like "Mar-a-Lago"
        # stay as one token instead of splitting "Lago" into a standalone candidate.
        ascii_matches = list(re.finditer(r"[A-Za-z]+(?:[\-'][A-Za-z]+)*", text))
        normalized_tokens = [match.group() for match in ascii_matches if len(match.group()) >= 3]
        for size in (3, 2, 1):
            for idx in range(0, len(normalized_tokens) - size + 1):
                phrase = " ".join(normalized_tokens[idx: idx + size]).strip()
                if not phrase:
                    continue
                phrase_lower = phrase.lower()
                if size == 1 and phrase_lower in self._ASCII_STOPWORDS:
                    continue
                if size == 1 and phrase_lower in self._KNOWN_NON_GEO:
                    continue
                # Skip phrases whose first token is a known non-geo word
                if normalized_tokens[idx].lower() in self._KNOWN_NON_GEO:
                    continue
                if size == 1 and not self._allow_ascii_single_token_candidate(phrase):
                    continue
                if size == 1 and self._is_ascii_person_name_fragment(normalized_tokens, idx):
                    continue
                if phrase_lower in seen:
                    continue
                seen.add(phrase_lower)
                candidates.append(phrase)

        return candidates

    @staticmethod
    def _allow_ascii_single_token_candidate(token: str) -> bool:
        stripped = token.strip()
        if len(stripped) < 4:
            return False
        if stripped.islower():
            return False
        return True

    @staticmethod
    def _is_ascii_person_name_fragment(tokens: List[str], idx: int) -> bool:
        token = tokens[idx].strip()
        if not token or not token[:1].isupper():
            return False

        prev_token = tokens[idx - 1].strip() if idx > 0 else ""
        next_token = tokens[idx + 1].strip() if idx + 1 < len(tokens) else ""

        prev_title = bool(prev_token) and prev_token[:1].isupper() and prev_token[1:].islower()
        next_title = bool(next_token) and next_token[:1].isupper() and next_token[1:].islower()
        current_title = token[:1].isupper() and token[1:].islower()

        return current_title and prev_title and next_title

    def _infer_candidate_type(self, name: str) -> str:
        lowered = name.lower().strip()
        if any(name.endswith(suffix) for suffix in ("省", "州", "自治区", "特别行政区")):
            return "admin1"
        if any(name.endswith(suffix) for suffix in ("市", "县", "区")):
            return "city"
        if lowered.endswith((" province", " state", " prefecture", " region", " territory")):
            return "admin1"
        if lowered.endswith((" city", " county", " district")):
            return "city"
        return "city"

    @staticmethod
    def _confidence_for_match(extracted_type: str, match_type: str) -> float:
        if extracted_type == match_type:
            return 0.88
        if match_type == "city":
            return 0.82
        if match_type == "admin1":
            return 0.84
        return 0.8

    @staticmethod
    def _normalize_extracted_type(value: Any) -> str:
        geo_type = str(value or "").strip().lower()
        if geo_type in {"province", "state", "region", "admin1"}:
            return "admin1"
        if geo_type in {"city", "district", "point"}:
            return "city"
        return "country"

    @staticmethod
    def _extract_country_hint(geo_key_hint: str) -> Optional[str]:
        if not geo_key_hint:
            return None
        if "." in geo_key_hint:
            prefix = geo_key_hint.split(".", 1)[0].strip().upper()
            return prefix[:10] if prefix else None
        if "_" in geo_key_hint:
            prefix = geo_key_hint.split("_", 1)[0].strip().upper()
            return prefix[:10] if prefix else None
        if ":" in geo_key_hint:
            prefix = geo_key_hint.split(":", 1)[0].strip().upper()
            return prefix[:10] if prefix else None
        if len(geo_key_hint) in {2, 3} and geo_key_hint.isalpha():
            return geo_key_hint.upper()[:10]
        return None

    @staticmethod
    def _compose_admin1_geo_key(country_code: str, admin1_code: str, geo_key_hint: str) -> str:
        if country_code and admin1_code:
            return f"{country_code}.{admin1_code}"
        return geo_key_hint or country_code or "UNKNOWN"

    @staticmethod
    def _compose_city_geo_key(country_code: str, source_id: str, geo_key_hint: str, name: str) -> str:
        if country_code and source_id:
            return f"{country_code}:{source_id}"
        if geo_key_hint:
            return geo_key_hint
        return EnhancedGeoProcessor._fallback_geo_key(country_code, name, prefix="CT")

    @staticmethod
    def _fallback_geo_key(country_code: str, name: str, *, prefix: str) -> str:
        normalized_name = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "", name).strip()
        short_name = normalized_name[:12] if normalized_name else "UNKNOWN"
        cc = (country_code or "XX")[:4]
        return f"{prefix}:{cc}:{short_name}"

    @staticmethod
    def _strip_inline_location_suffix(name: str) -> str:
        return re.sub(r"[（(].*?[)）]$", "", name).strip()
