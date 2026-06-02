import pytest


@pytest.fixture(scope="function")
def browser_context_args(browser_context_args):
    return {**browser_context_args, "ignore_https_errors": True}
