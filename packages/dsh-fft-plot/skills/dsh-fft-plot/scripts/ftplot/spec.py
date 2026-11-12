"""spec 与数据加载。

spec 是 **JSON**（不是 YAML）：只依赖标准库，机器上无需 PyYAML。
数据可以在 spec 里直接给（`"rows": [...]`），也可以给一个文件路径
（`"data": "rows.json"`，相对 spec 文件所在目录解析）——行数多时用后者，
spec 保持可读。
"""
import json
import os


class SpecError(ValueError):
    """spec 内容不合规。消息里写清哪个字段、期望什么，便于直接改正。"""


def load(path):
    """读 spec 文件，返回 dict。"""
    with open(path, encoding='utf-8') as handle:
        try:
            spec = json.load(handle)
        except json.JSONDecodeError as exc:
            raise SpecError(f'{path} is not valid JSON: {exc}') from None
    if not isinstance(spec, dict):
        raise SpecError(f'{path} must contain a JSON object at the top level')
    spec.setdefault('_dir', os.path.dirname(os.path.abspath(path)))
    if 'chart' not in spec:
        raise SpecError('spec needs a "chart" object')
    return spec


def rows_of(spec):
    """取数据行：支持内联 `rows` 或引用 `data` 文件。"""
    inline = spec.get('rows')
    if inline is not None:
        if not isinstance(inline, list):
            raise SpecError('"rows" must be a JSON array of objects')
        return [_as_row(r, i) for i, r in enumerate(inline)]

    ref = spec.get('data')
    if ref is None:
        raise SpecError('spec needs either "rows" (inline array) or "data" (file path)')
    path = ref if os.path.isabs(ref) else os.path.join(spec.get('_dir', '.'), ref)
    if not os.path.exists(path):
        raise SpecError(f'data file not found: {path}')
    with open(path, encoding='utf-8') as handle:
        payload = json.load(handle)

    # 允许 {"rows": [...]} 或直接是数组
    if isinstance(payload, dict):
        for key in ('rows', 'data', 'items', 'records', 'list', 'result'):
            if isinstance(payload.get(key), list):
                return [_as_row(r, i) for i, r in enumerate(payload[key])]
        raise SpecError(f'{path}: object has no array under rows/data/items/records/list/result')
    if isinstance(payload, list):
        return [_as_row(r, i) for i, r in enumerate(payload)]
    raise SpecError(f'{path}: expected an array or an object holding one')


def _as_row(row, index):
    if not isinstance(row, dict):
        raise SpecError(f'row {index} is {type(row).__name__}, expected an object')
    return row
