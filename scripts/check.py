"""Portable checks; Windows CI shards files without omitting or duplicating tests."""
import argparse
import json
from pathlib import Path
import subprocess
import sys


def select_files(root, shard):
    try:
        index, total = map(int, shard.split('/'))
    except (ValueError, AttributeError):
        raise ValueError('Use --shard INDEX/TOTAL, with 1 <= INDEX <= TOTAL.') from None
    if not 1 <= index <= total <= 16:
        raise ValueError('Use --shard INDEX/TOTAL, with 1 <= INDEX <= TOTAL <= 16.')
    files = sorted(p.relative_to(root).as_posix() for p in (root / 'tests').rglob('test_*.py'))
    selected = files[index - 1::total]
    if not selected:
        raise ValueError('The selected shard has no test files.')
    return selected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shard', default='1/1')
    options = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    try:
        selected = select_files(root, options.shard)
    except ValueError as exc:
        parser.error(str(exc))
    result_dir = root / 'test-results'
    result_dir.mkdir(exist_ok=True)
    (result_dir / 'selection.json').write_text(json.dumps({'shard': options.shard, 'files': selected}, indent=2), encoding='utf-8')
    checks = ([sys.executable, '-m', 'compileall', '-q', 'src'],
              [sys.executable, '-m', 'pytest', '-v', '--durations=20', '-o', 'faulthandler_timeout=60',
               '--junitxml=' + str(result_dir / 'results.xml'), *selected])
    for args in checks:
        result = subprocess.run(args, cwd=root)
        if result.returncode:
            raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
