"""Fixed, independently checkable workload contracts for cache experiments."""

from copy import deepcopy

_SUITES = {
    'matrix': {
        'id': 'matrix', 'title': '矩陣遍歷',
        'variants': {'cache_row': '連續存取 Row', 'cache_column': '跨列存取 Column'},
        'checksum': 8394752, 'oracle_values': [8394752], 'operations': 16384,
        'allocated_bytes': 16384, 'hot_bytes': 16384, 'symbol': 'cache_matrix',
        'description': '64 × 64 uint32，每個元素加一兩次',
    },
    'layout': {
        'id': 'layout', 'title': 'AoS／SoA／Hot-cold',
        'variants': {'cache_aos': 'AoS', 'cache_soa': 'SoA', 'cache_hotcold': 'Hot/cold'},
        'checksum': 131584, 'oracle_values': [131584, 7334656], 'operations': 2048,
        'allocated_bytes': 16384, 'hot_bytes': 2048, 'symbol': 'cache_records',
        'description': '256 records，兩個 hot 欄位加一兩次；14 cold 欄位保持不變',
    },
}


def suite_spec(name):
    if name not in _SUITES:
        raise ValueError('unknown cache suite')
    return deepcopy(_SUITES[name])
