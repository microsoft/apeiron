"""Smoke / unit tests for sllm.const model-card definitions.

These tests are network- and credential-free: they only exercise the pure
in-memory model-card registry and cost/lookup helpers.
"""
import pytest

from sllm import const


def test_model_cards_registered():
    # A few canonical cards must self-register on import.
    for name in ['gpt-4.1', 'o4-mini', 'gpt-4.1-mini', 'gpt-5']:
        assert name in const.MODEL_CARDS
        assert isinstance(const.MODEL_CARDS[name], const.ModelCard)


def test_find_model_card_by_name():
    card = const.find_model_card('gpt-4.1')
    assert card.name == 'gpt-4.1'
    assert card.provider == const.Providers.OPENAI


def test_find_model_card_by_snapshot():
    # Snapshot name should resolve back to its parent card.
    card = const.find_model_card('gpt-4.1')
    snapshot_name = card.latest_snapshot.name
    assert const.find_model_card(snapshot_name).name == card.name


def test_find_model_card_unknown_raises():
    with pytest.raises(ValueError):
        const.find_model_card('does-not-exist-model')


def test_computer_use_endpoint_not_hardcoded():
    # Regression guard: the CUA endpoint must come from the environment,
    # never a baked-in personal/tenant URL.
    card = const.MODEL_CARDS['computer-use-preview']
    assert card.endpoint is None or 'ankitsriv' not in (card.endpoint or '')


def test_copilot_claude_card_registered():
    # Claude-via-Copilot card must register with the COPILOT provider.
    card = const.find_model_card('claude-sonnet-4.5')
    assert card.provider == const.Providers.COPILOT


def test_check_args_accepts_copilot_args():
    # The Agent calls check_args on construction; COPILOT models must accept
    # the args the Copilot path consumes (timeout / copilot_provider).
    card = const.find_model_card('claude-sonnet-4.5')
    card.check_args({'timeout': 60})
    card.check_args({'copilot_provider': 'anthropic'})
    with pytest.raises(ValueError):
        card.check_args({'temperature': 0.5})  # not supported on the Copilot path


def test_cost_computation():
    card = const.find_model_card('gpt-4.1')
    usage = {
        'prompt_tokens': 1_000_000,
        'completion_tokens': 1_000_000,
        'prompt_tokens_details': {'cached_tokens': 0},
    }
    result = card.cost(usage)
    # input_price (2) + output_price (8) per 1M tokens => 10 USD
    assert result.cost == pytest.approx(10.0)
    assert result.prompt_tokens == 1_000_000
