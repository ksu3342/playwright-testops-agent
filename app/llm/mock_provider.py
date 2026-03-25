import re
from typing import Iterable

from app.llm.base import BaseLLMProvider, LLMResponse


class MockLLMProvider(BaseLLMProvider):
    """Deterministic normalizer used for tests and offline demos."""

    @staticmethod
    def _extract_raw_notes(prompt: str) -> str:
        match = re.search(
            r"<<<RAW_REQUIREMENT_NOTES>>>\s*(.*?)\s*<<<END_RAW_REQUIREMENT_NOTES>>>",
            prompt,
            re.DOTALL,
        )
        if match:
            return match.group(1).strip()
        return prompt.strip()

    @staticmethod
    def _clean_fragment(text: str) -> str:
        cleaned = text.strip().strip("-*")
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip(" .")

    @classmethod
    def _dedupe(cls, items: Iterable[str]) -> list[str]:
        seen: set[str] = set()
        results: list[str] = []
        for item in items:
            cleaned = cls._clean_fragment(item)
            if not cleaned:
                continue
            key = cleaned.lower()
            if key in seen:
                continue
            seen.add(key)
            results.append(cleaned)
        return results

    @staticmethod
    def _split_candidates(raw_text: str) -> list[str]:
        normalized = raw_text.replace("\r\n", "\n")
        chunks = re.split(r"\n+|[;]", normalized)
        return [chunk.strip() for chunk in chunks if chunk.strip()]

    @classmethod
    def _extract_after_markers(cls, raw_text: str, markers: list[str]) -> list[str]:
        results: list[str] = []
        chunks = cls._split_candidates(raw_text)
        for chunk in chunks:
            lowered = chunk.lower()
            for marker in markers:
                marker_with_colon = f"{marker}:"
                if marker_with_colon in lowered:
                    start = lowered.index(marker_with_colon) + len(marker_with_colon)
                    payload = chunk[start:].strip()
                    if payload:
                        results.extend(re.split(r";|,|\bthen\b|->", payload))
                    break
        return cls._dedupe(results)

    @classmethod
    def _guess_title(cls, raw_text: str) -> str:
        for line in raw_text.splitlines():
            candidate = cls._clean_fragment(line)
            if candidate:
                return candidate
        return "Untitled Requirement Notes"

    @classmethod
    def _guess_feature_name(cls, raw_text: str, title: str) -> str:
        lowered = raw_text.lower()
        if "login" in lowered:
            return "User Login"
        if "search" in lowered:
            return "Keyword Search"
        return title

    @staticmethod
    def _guess_page_url(raw_text: str) -> str:
        match = re.search(r"(?<![A-Za-z0-9])(/[A-Za-z0-9][A-Za-z0-9/_-]*)", raw_text)
        if not match:
            return ""
        return match.group(1)

    @classmethod
    def _guess_preconditions(cls, raw_text: str) -> list[str]:
        items = cls._extract_after_markers(
            raw_text,
            markers=["preconditions", "precondition", "before testing", "before test", "before running"],
        )
        for fragment in cls._split_candidates(raw_text):
            lowered = fragment.lower()
            if any(token in lowered for token in ["should already", "already have", "able to reach", "can access", "can open"]):
                items.append(fragment)
        return cls._dedupe(items)

    @classmethod
    def _guess_user_actions(cls, raw_text: str) -> list[str]:
        items = cls._extract_after_markers(
            raw_text,
            markers=["user actions", "actions", "main flow", "typical flow", "flow"],
        )
        action_markers = ["enter ", "click ", "review ", "select ", "choose "]
        for fragment in cls._split_candidates(raw_text):
            lowered = fragment.lower()
            if ":" in fragment and any(marker in lowered for marker in ["flow:", "expected:", "before testing:"]):
                continue
            if any(marker in lowered for marker in action_markers):
                items.append(fragment)
        return cls._dedupe(items)

    @classmethod
    def _guess_expected_results(cls, raw_text: str) -> list[str]:
        items = cls._extract_after_markers(
            raw_text,
            markers=["expected results", "expected result", "expected", "results"],
        )
        for fragment in cls._split_candidates(raw_text):
            cleaned_fragment = fragment.split(":", 1)[1].strip() if fragment.lower().startswith("expected") and ":" in fragment else fragment
            lowered = cleaned_fragment.lower()
            if any(
                marker in lowered
                for marker in [
                    "redirect",
                    "displayed",
                    "empty state",
                    "no result",
                    "no matching",
                    "submitted successfully",
                    "validation error",
                    "successful",
                ]
            ):
                items.append(cleaned_fragment)
        return cls._dedupe(items)

    @staticmethod
    def _format_list_section(items: list[str], ordered: bool) -> str:
        if not items:
            return ""
        if ordered:
            return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))
        return "\n".join(f"- {item}" for item in items)

    @classmethod
    def _build_markdown(cls, raw_text: str) -> str:
        title = cls._guess_title(raw_text)
        feature_name = cls._guess_feature_name(raw_text, title)
        page_url = cls._guess_page_url(raw_text)
        preconditions = cls._guess_preconditions(raw_text)
        user_actions = cls._guess_user_actions(raw_text)
        expected_results = cls._guess_expected_results(raw_text)

        sections = [
            "# Title",
            title,
            "",
            "## Feature Name",
            feature_name,
            "",
            "## Page URL",
            page_url,
            "",
            "## Preconditions",
            cls._format_list_section(preconditions, ordered=False),
            "",
            "## User Actions",
            cls._format_list_section(user_actions, ordered=True),
            "",
            "## Expected Results",
            cls._format_list_section(expected_results, ordered=False),
            "",
        ]
        return "\n".join(sections).rstrip() + "\n"

    def generate(self, prompt: str) -> LLMResponse:
        raw_notes = self._extract_raw_notes(prompt)
        return LLMResponse(content=self._build_markdown(raw_notes))