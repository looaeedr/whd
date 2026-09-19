#!/usr/bin/env python3
from __future__ import annotations
import argparse, json
from pathlib import Path

def load(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def phase(row, key):
    v=row.get(key)
    return v.get("outcome") if isinstance(v, dict) else None
def summarize(report):
    outcomes={}; failed=set(); errors=set()
    for row in report.get("tests") or ():
        node=str(row.get("nodeid") or "")
        if not node: continue
        outcome=str(row.get("outcome") or "unknown")
        outcomes[node]=outcome
        if phase(row,"call")=="failed" or (outcome=="failed" and phase(row,"setup")!="failed" and phase(row,"teardown")!="failed"):
            failed.add(node)
        if phase(row,"setup")=="failed" or phase(row,"teardown")=="failed":
            errors.add(node)
    for row in report.get("collectors") or ():
        if str(row.get("outcome") or "")=="failed":
            errors.add("COLLECT::"+str(row.get("nodeid") or "<collection>"))
    return {"outcomes":outcomes,"failed":sorted(failed),"errors":sorted(errors),"nodes":sorted(outcomes)}
def compare(name,b,c):
    b=summarize(b); c=summarize(c)
    bn=set(b["nodes"]); cn=set(c["nodes"])
    changed=sorted(n for n in bn&cn if b["outcomes"][n]!=c["outcomes"][n])
    return {
      "lane":name,"baseline":b,"candidate":c,
      "missing_nodes":sorted(bn-cn),"extra_nodes":sorted(cn-bn),
      "changed_outcomes":[{"node":n,"baseline":b["outcomes"][n],"candidate":c["outcomes"][n]} for n in changed],
      "new_failed":sorted(set(c["failed"])-set(b["failed"])),
      "new_errors":sorted(set(c["errors"])-set(b["errors"])),
      "exact_outcome_parity": not (bn-cn or cn-bn or changed),
    }
def digest(p): return Path(p).read_text(encoding="utf-8").strip()
def prot(prefix,args):
    bb=digest(getattr(args,f"baseline_{prefix}_protected_before"))
    ba=digest(getattr(args,f"baseline_{prefix}_protected_after"))
    cb=digest(getattr(args,f"candidate_{prefix}_protected_before"))
    ca=digest(getattr(args,f"candidate_{prefix}_protected_after"))
    return {"baseline_runtime_drift":bb!=ba,"candidate_runtime_drift":cb!=ca,"source_drift":bb!=cb}
def main():
    p=argparse.ArgumentParser()
    for lane in ("headless","xvfb"):
        p.add_argument(f"--baseline-{lane}",required=True)
        p.add_argument(f"--candidate-{lane}",required=True)
        for side in ("baseline","candidate"):
            for when in ("before","after"):
                p.add_argument(f"--{side}-{lane}-protected-{when}",required=True)
    p.add_argument("--output",required=True)
    a=p.parse_args()
    h=compare("headless",load(a.baseline_headless),load(a.candidate_headless))
    x=compare("xvfb",load(a.baseline_xvfb),load(a.candidate_xvfb))
    protected={"headless":prot("headless",a),"xvfb":prot("xvfb",a)}
    drift=any(v for lane in protected.values() for v in lane.values())
    unexplained=not(h["exact_outcome_parity"] and x["exact_outcome_parity"])
    classifier={
      "NEW_RELEVANT_HEADLESS":h["new_failed"],
      "NEW_RELEVANT_XVFB":x["new_failed"],
      "NEW_RELEVANT_ERRORS":sorted(set(h["new_errors"])|set(x["new_errors"])),
      "PROTECTED_DRIFT":1 if drift else 0,
      "UNEXPLAINED_3D_DELTA":1 if unexplained else 0,
    }
    decision="GREEN" if not classifier["NEW_RELEVANT_HEADLESS"] and not classifier["NEW_RELEVANT_XVFB"] and not classifier["NEW_RELEVANT_ERRORS"] and not classifier["PROTECTED_DRIFT"] and not classifier["UNEXPLAINED_3D_DELTA"] else "RED"
    payload={"schema":"WHD_ISSUE370_T6_PRODUCTION_FIRST_AB_V1","decision":decision,"headless":h,"xvfb":x,"protected":protected,"classifier":classifier}
    Path(a.output).parent.mkdir(parents=True,exist_ok=True)
    Path(a.output).write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({
      "decision":decision,
      "headless_nodes":len(h["baseline"]["nodes"]),
      "headless_failed_baseline":len(h["baseline"]["failed"]),
      "headless_failed_candidate":len(h["candidate"]["failed"]),
      "xvfb_nodes":len(x["baseline"]["nodes"]),
      "xvfb_failed_baseline":len(x["baseline"]["failed"]),
      "xvfb_failed_candidate":len(x["candidate"]["failed"]),
      **classifier
    },ensure_ascii=False,indent=2,sort_keys=True))
    assert decision=="GREEN",classifier
    print("ISSUE370_T6_PRODUCTION_FIRST_AB_DECISION=GREEN")
if __name__=="__main__": main()
