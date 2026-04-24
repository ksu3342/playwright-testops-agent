from pathlib import Path

from app.core import generator as generator_module
from app.core.selector_contract import (
    DEFAULT_SELECTOR_CONTRACT_PATH,
    SelectorContract,
    SelectorDefinition,
    load_selector_contract,
)


def test_selector_contract_loads_expected_metadata() -> None:
    contract = load_selector_contract()

    assert isinstance(contract, SelectorContract)
    assert contract.version == 1
    assert contract.app == "demo_app"
    assert contract.base_url == "http://localhost:3000"

    email_selector = contract.get("login.email_input")
    assert isinstance(email_selector, SelectorDefinition)
    assert email_selector is not None
    assert email_selector.semantic_key == "login.email_input"
    assert email_selector.strategy == "test_id"
    assert email_selector.value == "login-email-input"
    assert email_selector.playwright == 'page.get_by_test_id("login-email-input")'
    assert email_selector.locator_expression() == 'page.get_by_test_id("login-email-input")'
    assert email_selector.source_comment() == "# selector-contract: login.email_input -> login-email-input"


def test_selector_contract_file_contains_required_demo_app_keys() -> None:
    contract = load_selector_contract(Path(DEFAULT_SELECTOR_CONTRACT_PATH))

    assert contract.get("login.password_input") is not None
    assert contract.get("login.submit_button") is not None
    assert contract.get("login.inline_error") is not None
    assert contract.get("dashboard.heading") is not None
    assert contract.get("dashboard.search_link") is not None
    assert contract.get("search.input") is not None
    assert contract.get("search.submit_button") is not None
    assert contract.get("search.results_list") is not None
    assert contract.get("search.result_item") is not None
    assert contract.get("search.empty_state") is not None


def test_login_test_data_contract_loads_expected_demo_credentials() -> None:
    contract = generator_module.load_test_data_contract()

    assert isinstance(contract, generator_module.TestDataContract)
    email_fixture = contract.get("login.valid_email")
    password_fixture = contract.get("login.valid_password")

    assert isinstance(email_fixture, generator_module.TestDataDefinition)
    assert isinstance(password_fixture, generator_module.TestDataDefinition)
    assert email_fixture is not None
    assert password_fixture is not None
    assert email_fixture.value == "demo@example.com"
    assert password_fixture.value == "password123"
