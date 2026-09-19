#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def phase(row, key):
    value=row.get(key)
    return value.get("outcome") if isinstance(value, dict) else None

def summarize(report):
    outcomes={}; failed=set(); errors=set()
    for row in report.get("tests") or ():
        node=str(row.get("nodeid") or "")
        if not node:
            continue
        outcome=str(row.get("outcome") or "unknown")
        outcomes[node]=outcome
        if phase(row,"setup")=="failed" or phase(row,"teardown")=="failed":
            errors.add(node)
        elif phase(row,"call")=="failed" or outcome=="failed":
            failed.add(node)
    for row in report.get("collectors") or ():
        if str(row.get("outcome") or "")=="failed":
            errors.add("COLLECT::"+str(row.get("nodeid") or "<collection>"))
    return {"nodes":sorted(outcomes),"outcomes":outcomes,"failed":sorted(failed),"errors":sorted(errors)}

def compare_lane(name,b,c):
    b=summarize(b); c=summarize(c)
    bn=set(b["nodes"]); cn=set(c["nodes"])
    changed=sorted(n for n in bn&cn if b["outcomes"][n]!=c["outcomes"][n])
    return {
        "lane":name,
        "baseline":b,
        "candidate":c,
        "missing_nodes":sorted(bn-cn),
        "extra_nodes":sorted(cn-bn),
        "changed_outcomes":[{"node":n,"baseline":b["outcomes"][n],"candidate":c["outcomes"][n]} for n in changed],
        "new_failed":sorted(set(c["failed"])-set(b["failed"])),
        "new_errors":sorted(set(c["errors"])-set(b["errors"])),
        "exact_outcome_parity":not (bn-cn or cn-bn or changed),
    }

def digest(path):
    return Path(path).read_text(encoding="utf-8").strip()

def protected(prefix,args):
    bb=digest(getattr(args,f"baseline_{prefix}_protected_before"))
    ba=digest(getattr(args,f"baseline_{prefix}_protected_after"))
    cb=digest(getattr(args,f"candidate_{prefix}_protected_before"))
    ca=digest(getattr(args,f"candidate_{prefix}_protected_after"))
    return {
        "baseline_runtime_drift":bb!=ba,
        "candidate_runtime_drift":cb!=ca,
        "source_drift":bb!=cb,
    }

def main():
    p=argparse.ArgumentParser()
    for lane in ("headless","xvfb"):
        p.add_argument(f"--baseline-{lane}",required=True)
        p.add_argument(f"--candidate-{lane}",required=True)
        for side in ("baseline","candidate"):
            for when in ("before","after"):
                p.add_argument(f"--{side}-{lane}-protected-{when}",required=True)
    p.add_argument("--baseline-event-order",required=True)
    p.add_argument("--candidate-event-order",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()

    h=compare_lane("headless",load(a.baseline_headless),load(a.candidate_headless))
    x=compare_lane("xvfb",load(a.baseline_xvfb),load(a.candidate_xvfb))
    prot={"headless":protected("headless",a),"xvfb":protected("xvfb",a)}
    protected_drift=any(v for lane in prot.values() for v in lane.values())
    baseline_event=load(a.baseline_event_order)
    candidate_event=load(a.candidate_event_order)
    event_delta=(baseline_event!=candidate_event)
    outcome_delta=not(h["exact_outcome_parity"] and x["exact_outcome_parity"])
    classifier={
        "NEW_RELEVANT_HEADLESS":h["new_failed"],
        "NEW_RELEVANT_XVFB":x["new_failed"],
        "NEW_RELEVANT_ERRORS":sorted(set(h["new_errors"])|set(x["new_errors"])),
        "PROTECTED_DRIFT":1 if protected_drift else 0,
        "UNEXPLAINED_EVENT_ORDER_DELTA":1 if event_delta else 0,
        "UNEXPLAINED_TEST_OUTCOME_DELTA":1 if outcome_delta else 0,
    }
    decision="GREEN" if (
        not classifier["NEW_RELEVANT_HEADLESS"]
        and not classifier["NEW_RELEVANT_XVFB"]
        and not classifier["NEW_RELEVANT_ERRORS"]
        and classifier["PROTECTED_DRIFT"]==0
        and classifier["UNEXPLAINED_EVENT_ORDER_DELTA"]==0
        and classifier["UNEXPLAINED_TEST_OUTCOME_DELTA"]==0
    ) else "RED"
    payload={
        "schema":"WHD_ISSUE371_T7_AB_V1",
        "decision":decision,
        "headless":h,
        "xvfb":x,
        "protected":prot,
        "event_order":{"baseline":baseline_event,"candidate":candidate_event},
        "classifier":classifier,
    }
    out=Path(a.output); out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
        "decision":decision,
        "headless_nodes":len(h["baseline"]["nodes"]),
        "headless_failed_baseline":len(h["baseline"]["failed"]),
        "headless_failed_candidate":len(h["candidate"]["failed"]),
        "xvfb_nodes":len(x["baseline"]["nodes"]),
        "xvfb_failed_baseline":len(x["baseline"]["failed"]),
        "xvfb_failed_candidate":len(x["candidate"]["failed"]),
        "baseline_event_order":baseline_event,
        "candidate_event_order":candidate_event,
        **classifier,
    },ensure_ascii=False,indent=2,sort_keys=True))
    assert decision=="GREEN",classifier
    print("ISSUE371_T7_AB_DECISION=GREEN")

if __name__=="__main__":
    main()
