from tests.process._flow_v2_historical_cutover import assert_historical_cutover

def test_retired_execution_contract_cannot_regrow() -> None:
    assert_historical_cutover(__file__)
