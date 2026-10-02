from tools.control_transaction import TRANSACTION_KINDS
from tools.execution_action_contract import (
    ACTION_TRANSACTION_KIND,
    EXECUTABLE_ACTION_KINDS,
    OBSERVATION_ACTION_KINDS,
)


def test_every_executable_action_is_either_atomic_transaction_or_observation():
    assert set(ACTION_TRANSACTION_KIND) | set(OBSERVATION_ACTION_KINDS) == set(EXECUTABLE_ACTION_KINDS)
    assert set(ACTION_TRANSACTION_KIND).isdisjoint(OBSERVATION_ACTION_KINDS)


def test_all_action_bound_transactions_exist_in_atomic_engine():
    assert set(ACTION_TRANSACTION_KIND.values()).issubset(TRANSACTION_KINDS)


def test_wait_only_actions_are_exact_canonical_vocabulary():
    assert OBSERVATION_ACTION_KINDS == {"POLL_QA", "WAIT_EXTERNAL"}


def test_internal_block_transition_is_transaction_only_not_next_action():
    assert "BLOCK" in TRANSACTION_KINDS
    assert "BLOCK" not in EXECUTABLE_ACTION_KINDS
