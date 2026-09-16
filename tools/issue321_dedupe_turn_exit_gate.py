from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "AGENTS.md"
HEADING = "### 0.0.3.0 ASSISTANT_TURN_EXIT_HARD_GATE_V2"
NEXT = "### 0.0.3.1 Executable Continuity finalization bridge"


def main() -> None:
    text = PATH.read_text(encoding="utf-8")
    count = text.count(HEADING)
    if count == 1:
        return
    if count != 2:
        raise SystemExit(f"expected one or two turn-exit sections, found {count}")
    first = text.find(HEADING)
    second = text.find(HEADING, first + len(HEADING))
    end = text.find(NEXT, second)
    if second < 0 or end < 0:
        raise SystemExit("could not locate duplicate turn-exit section boundaries")
    text = text[:second] + text[end:]
    if text.count(HEADING) != 1:
        raise SystemExit("dedupe failed")
    PATH.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
