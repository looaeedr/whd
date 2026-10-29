# -*- coding: utf-8 -*-
"""#2378: optional Door frame-edge evidence requires a wire *minor* version."""
import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, ValidationError

ROOT=Path(__file__).resolve().parents[1]/"integration_cli"/"schemas"


def _validator(name):
    obj=json.loads((ROOT/name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(obj)
    return Draft202012Validator(obj)


def _request():
    return {
        "protocol_version":"1.1.0",
        "client_installation_id":"CAD-owned-01",
        "request_id":"wire-1",
        "job_id":"job-1",
        "request_digest":"a"*64,
        "operation":"prepare",
        "coordinate_contract_revision":"1",
        "items":[{
            "item_id":"門片一",
            "source_document_sha256":"f"*64,
            "part":{
                "kind":"door",
                "cabinet_family":"金庫型",
                "source_part_ref":"SRC-1",
                "dimension_semantics":"cabinet_outer",
                "dimensions_mm":{"width":500,"height":600,"thickness":2},
                "frame_edges":{"left":True,"right":True,"top":True,"bottom":True},
            },
        }],
    }


def test_minor_version_keeps_wire_v1_original_contract_unchanged():
    old=_validator("request_v1.schema.json")
    new=_validator("request_v1_1.schema.json")
    request=_request()
    new.validate(request)
    with pytest.raises(ValidationError):
        old.validate(request)
    v1=deepcopy(request)
    v1["protocol_version"]="1.0.0"
    del v1["items"][0]["part"]["frame_edges"]
    old.validate(v1)
    with pytest.raises(ValidationError):
        new.validate(v1)
    v1["items"][0]["part"]["frame_edges"]={"left":True,"right":True,"top":True,"bottom":True}
    with pytest.raises(ValidationError):
        old.validate(v1)


def test_new_schema_checks_edges_but_requires_whd_runtime_provenance():
    new=_validator("request_v1_1.schema.json")
    invalid=_request()
    invalid["items"][0]["part"]["frame_edges"]["left"]="yes"
    with pytest.raises(ValidationError):
        new.validate(invalid)
    optional=_request()
    del optional["items"][0]["part"]["frame_edges"]
    new.validate(optional)  # v1.1 is additive; W-03 runtime must reject ambiguity


def test_minor_response_and_disabled_public_cli_remain_separate():
    old=_validator("response_v1.schema.json")
    new=_validator("response_v1_1.schema.json")
    from integration_cli.cadsplit_worker import PROTOCOL_VERSION
    assert PROTOCOL_VERSION=="1.0.0"
    assert old.schema["properties"]["protocol_version"]["const"]=="1.0.0"
    assert new.schema["properties"]["protocol_version"]["const"]=="1.1.0"
    assert new.schema["properties"]["protocol_version"]["const"]!=PROTOCOL_VERSION
