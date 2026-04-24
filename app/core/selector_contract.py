import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


MODULE_DIR = Path(__file__).resolve().parent
APP_DIR = MODULE_DIR.parent
REPO_ROOT = APP_DIR.parent
DEFAULT_SELECTOR_CONTRACT_PATH = REPO_ROOT / "data" / "contracts" / "demo_app_selectors.json"
SELECTOR_CONTRACT_MISSING_MARKER = "SELECTOR_CONTRACT_MISSING"


class SelectorContractError(ValueError):
    pass


@dataclass(frozen=True)
class SelectorDefinition:
    semantic_key: str
    strategy: str
    value: str
    playwright: Optional[str]

    def locator_expression(self) -> str:
        if self.playwright:
            return self.playwright
        if self.strategy == "test_id":
            return f'page.get_by_test_id("{self.value}")'
        if self.strategy == "css":
            return f'page.locator("{self.value}")'
        if self.strategy == "text":
            return f'page.get_by_text("{self.value}")'
        raise SelectorContractError(
            f"Selector {self.semantic_key} requires an explicit playwright locator for strategy {self.strategy}."
        )

    def source_comment(self) -> str:
        return f"# selector-contract: {self.semantic_key} -> {self.value}"


@dataclass(frozen=True)
class SelectorContract:
    version: int
    app: str
    base_url: str
    selectors: dict[str, SelectorDefinition]

    def get(self, semantic_key: str) -> Optional[SelectorDefinition]:
        return self.selectors.get(semantic_key)


def _load_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise SelectorContractError(f"Selector contract file not found: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SelectorContractError(f"Selector contract is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise SelectorContractError("Selector contract root must be a JSON object.")
    return payload


def _build_selector_definition(semantic_key: str, value: object) -> SelectorDefinition:
    if not isinstance(value, dict):
        raise SelectorContractError(f"Selector entry must be an object: {semantic_key}")

    actual_semantic_key = value.get("semantic_key")
    strategy = value.get("strategy")
    selector_value = value.get("value")
    playwright = value.get("playwright")

    if actual_semantic_key != semantic_key:
        raise SelectorContractError(f"Selector semantic_key mismatch for {semantic_key}.")
    if not all(isinstance(item, str) and item for item in [strategy, selector_value]):
        raise SelectorContractError(f"Selector entry is missing required fields: {semantic_key}")
    if playwright is not None and (not isinstance(playwright, str) or not playwright):
        raise SelectorContractError(f"Selector entry playwright field must be a non-empty string when provided: {semantic_key}")

    definition = SelectorDefinition(
        semantic_key=semantic_key,
        strategy=strategy,
        value=selector_value,
        playwright=playwright,
    )
    definition.locator_expression()
    return definition


def load_selector_contract(path: Optional[Path] = None) -> SelectorContract:
    contract_path = path or DEFAULT_SELECTOR_CONTRACT_PATH
    payload = _load_json(contract_path)
    selectors_payload = payload.get("selectors")
    if not isinstance(selectors_payload, dict):
        raise SelectorContractError("Selector contract must contain a selectors object.")

    selectors = {
        semantic_key: _build_selector_definition(semantic_key, selector_data)
        for semantic_key, selector_data in selectors_payload.items()
    }

    version = payload.get("version")
    app_name = payload.get("app")
    base_url = payload.get("base_url")
    if not isinstance(version, int):
        raise SelectorContractError("Selector contract version must be an integer.")
    if not isinstance(app_name, str) or not app_name:
        raise SelectorContractError("Selector contract app must be a non-empty string.")
    if not isinstance(base_url, str) or not base_url:
        raise SelectorContractError("Selector contract base_url must be a non-empty string.")

    return SelectorContract(
        version=version,
        app=app_name,
        base_url=base_url,
        selectors=selectors,
    )
