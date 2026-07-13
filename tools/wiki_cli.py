"""CLI HubEx.Wiki. Использование: python3 tools/wiki_cli.py update [флаги]."""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from update import manifest, pipeline, recompress, report  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wiki_cli", description="Пайплайн обновления HubEx.Wiki")
    sub = p.add_subparsers(dest="command", required=True)
    up = sub.add_parser("update",
                        help="дифф страниц вики против pages/ → отчёт; "
                             "--recompress пишет pages/ и аннотации индексов (unstaged)")
    up.add_argument("--page", action="append", default=None,
                    help="ограничить страницей <section>/<slug> (можно повторять; "
                         "removed при этом не вычисляется)")
    up.add_argument("--recompress", action="store_true",
                    help="перезаписать затронутые pages/** и обновить аннотации моделью (claude -p)")
    up.add_argument("--report-file", type=Path, default=None,
                    help="продублировать отчёт в файл")
    up.add_argument("--jobs", type=int, default=8,
                    help="параллельность HTTP-забора страниц (по умолчанию 8)")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "update":
        try:
            results = pipeline.run_update(pages=args.page, recompress=args.recompress,
                                          jobs=args.jobs)
        except manifest.ManifestError as e:
            print(f"ОШИБКА: {e}", file=sys.stderr)
            return 2
        text = report.render(results)
        print(text, end="")
        if args.recompress:
            print(recompress.render_summary(results), end="")
        if args.report_file:
            args.report_file.write_text(text, encoding="utf-8")
        has_err = any(r["status"] == "error" for r in results)
        rcs = [r.get("recompress") or {} for r in results]
        has_rc_err = any(rc.get("status") == "error" for rc in rcs)
        has_problems = any(rc.get("problems") for rc in rcs)
        return 1 if (has_err or has_rc_err or has_problems) else 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
