import argparse
from pathlib import Path

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


EVENT_PREFIX = "events.out.tfevents"


def find_event_files(paths):
    event_files = []
    for raw_path in paths:
        path = Path(raw_path)
        if path.is_file():
            event_files.append(path)
        elif path.is_dir():
            event_files.extend(path.rglob(f"{EVENT_PREFIX}*"))
        else:
            print(f"[skip] path does not exist: {path}")

    return sorted(
        {p.resolve() for p in event_files if p.name.startswith(EVENT_PREFIX)},
        key=lambda p: (str(p.parent), p.stat().st_size, p.name),
    )


def is_higher_better(tag):
    name = tag.lower()
    return "accuracy" in name or "auc" in name or name.endswith("/acc")


def load_scalars(event_file):
    accumulator = EventAccumulator(
        str(event_file),
        size_guidance={"scalars": 100000},
    )
    accumulator.Reload()
    return accumulator


def print_scalar_summary(tag, values):
    if not values:
        return

    first = values[0]
    last = values[-1]
    selector = max if is_higher_better(tag) else min
    best = selector(values, key=lambda item: item.value)
    metric_name = "best" if is_higher_better(tag) else "min"

    print(
        f"  {tag:<18} "
        f"n={len(values):<4} "
        f"first=({first.step:>5}, {first.value:.5f})  "
        f"{metric_name}=({best.step:>5}, {best.value:.5f})  "
        f"last=({last.step:>5}, {last.value:.5f})"
    )


def print_points(tag, values):
    print(f"\n  points: {tag}")
    for item in values:
        print(f"    step={item.step:<5} value={item.value:.6f}")


def main():
    parser = argparse.ArgumentParser(
        description="Read TensorBoard event files and print scalar summaries."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["logs"],
        help="Event file or directory. Defaults to logs.",
    )
    parser.add_argument(
        "--tag",
        action="append",
        help="Only show a scalar tag, for example --tag test/AUC. Can be repeated.",
    )
    parser.add_argument(
        "--points",
        action="store_true",
        help="Print every point for the selected tags.",
    )
    parser.add_argument(
        "--min-size",
        type=int,
        default=100,
        help="Skip tiny/incomplete event files smaller than this many bytes.",
    )
    args = parser.parse_args()

    event_files = find_event_files(args.paths)
    if not event_files:
        print("No TensorBoard event files found.")
        return

    selected_tags = set(args.tag or [])

    for event_file in event_files:
        size = event_file.stat().st_size
        if size < args.min_size:
            print(f"\n[skip] {event_file} ({size} bytes)")
            continue

        print(f"\n== {event_file} ({size} bytes) ==")
        try:
            accumulator = load_scalars(event_file)
        except Exception as exc:
            print(f"  failed to read event file: {exc}")
            continue

        tags = accumulator.Tags().get("scalars", [])
        if selected_tags:
            tags = [tag for tag in tags if tag in selected_tags]

        if not tags:
            print("  no matching scalar tags")
            continue

        for tag in tags:
            values = accumulator.Scalars(tag)
            print_scalar_summary(tag, values)
            if args.points:
                print_points(tag, values)


if __name__ == "__main__":
    main()
