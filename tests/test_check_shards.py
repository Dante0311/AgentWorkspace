import importlib.util
from pathlib import Path

import pytest


def test_shards_are_disjoint_and_cover_every_file():
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('check_script', root / 'scripts/check.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    all_files = module.select_files(root, '1/1')
    shards = [module.select_files(root, f'{i}/4') for i in range(1, 5)]
    flat = [p for shard in shards for p in shard]
    assert len(flat) == len(set(flat))
    assert sorted(flat) == all_files
    for invalid in ('0/4', '5/4', '1/0', '1/99', 'bad'):
        with pytest.raises(ValueError):
            module.select_files(root, invalid)
