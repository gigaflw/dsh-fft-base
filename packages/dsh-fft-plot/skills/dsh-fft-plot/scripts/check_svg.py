#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验独立 SVG 产物能否被 <img> 正确渲染。

背景：`viewBox` 只定义坐标系，不提供内在尺寸。HTML 里用
`<img src="chart.svg">` 引用时，浏览器按 SVG 的 width/height 决定布局盒子；
两者都缺失时会塌成 0 高 —— 表现就是「图发出去，对方只看到空白」。
同一份 SVG 直接拖进浏览器却能显示（独立文档模式按视口铺满），所以这个错误
在本地自测时**看不出来**，只能靠校验。

用法：
    python3 check_svg.py chart.svg [chart2.svg ...]
    python3 check_svg.py --quiet chart.svg     # 只报失败

退出码：全部通过 0，有任一失败 1，无参数 2。
"""
import re
import sys
import xml.etree.ElementTree as ET

REQUIRED = ('xmlns', 'width', 'height', 'viewBox')
EXPECT_XMLNS = 'http://www.w3.org/2000/svg'
SIZE_WARN_BYTES = 200 * 1024


def root_tag(src):
    m = re.search(r'<svg\b[^>]*>', src[:4096])
    return m.group(0) if m else None


def attr(tag, name):
    m = re.search(rf'\b{name}\s*=\s*"([^"]*)"', tag)
    return m.group(1) if m else None


def check(path):
    """返回 (ok, [问题描述], [告警描述])"""
    problems, warnings = [], []
    try:
        with open(path, encoding='utf-8') as handle:
            src = handle.read()
    except OSError as e:
        return False, [f'读不到文件：{e}'], []

    tag = root_tag(src)
    if tag is None:
        return False, ['找不到 <svg> 根元素（文件可能不是 SVG，或为空）'], []

    for name in REQUIRED:
        val = attr(tag, name)
        if val is None:
            problems.append(f'根元素缺 {name}')
            continue
        if name in ('width', 'height'):
            if not re.fullmatch(r'\d+(\.\d+)?', val):
                problems.append(f'{name} 必须是纯数字像素值，实际是 "{val}"')
            elif float(val) <= 0:
                problems.append(f'{name} 必须为正，实际是 {val}')

    ns = attr(tag, 'xmlns')
    if ns is not None and ns != EXPECT_XMLNS:
        problems.append(f'xmlns 应为 {EXPECT_XMLNS}，实际 {ns}')

    vb, w, h = attr(tag, 'viewBox'), attr(tag, 'width'), attr(tag, 'height')
    if vb and w and h:
        try:
            _, _, vw, vh = [float(x) for x in re.split(r'[\s,]+', vb.strip())]
            if vw > 0 and vh > 0 and abs(vw / vh - float(w) / float(h)) > 0.01:
                problems.append(
                    f'viewBox 宽高比 {vw/vh:.3f} 与 width/height 比 {float(w)/float(h):.3f} 不一致，'
                    f'<img> 里会变形')
        except ValueError:
            problems.append(f'viewBox 无法解析："{vb}"')

    # 整份文件必须是合法 XML：控制字符、未闭合标签都只能靠解析抓，
    # 浏览器打开时可能只是渲染异常，不会报错。
    try:
        ET.fromstring(src)
    except ET.ParseError as exc:
        problems.append(f'不是合法 XML：{exc}')

    # 非有限坐标会让路径直接消失（NaN/Infinity 不是合法 SVG 数值）。
    if re.search(r'(?i)(?<![\w-])(nan|infinity|inf)(?![\w-])', src):
        problems.append('含 NaN/Infinity 或非有限坐标')

    # 脚本与内联事件：自包含图片不允许（离线渲染会静默失败，也有注入风险）。
    if re.search(r'<script\b', src, re.I):
        problems.append('含 <script>')
    if re.search(r'\son[a-z]+\s*=', src, re.I):
        problems.append('含内联事件属性（on*）')
    if re.search(r'<foreignObject\b', src, re.I):
        problems.append('含 <foreignObject>（独立图片里不可靠）')

    body = src[len(tag):] if tag else src
    ext = [u for u in re.findall(r'(?:href|src|xlink:href)\s*=\s*"(?!#)([^"]+)"', body)
           if u.startswith(('http://', 'https://', '//'))]
    if ext:
        problems.append(f'含外部引用（离线会加载失败）：{ext[:3]}')

    if len(src.encode('utf-8')) > SIZE_WARN_BYTES:
        warnings.append(f'体积 {len(src.encode("utf-8")) / 1024:.0f}KB 偏大（> {SIZE_WARN_BYTES // 1024}KB）')

    return (not problems), problems, warnings


def main(argv):
    quiet = '--quiet' in argv
    files = [a for a in argv[1:] if not a.startswith('--')]
    if not files:
        print('用法：python3 check_svg.py chart.svg [chart2.svg ...]')
        return 2

    failed = 0
    for f in files:
        ok, problems, warnings = check(f)
        if ok:
            if not quiet:
                print(f'  OK   {f}')
                for warning in warnings:
                    print(f'       ~ {warning}')
        else:
            failed += 1
            print(f'  FAIL {f}')
            for problem in problems:
                print(f'       - {problem}')
    print(f'\n{"PASS" if not failed else "FAIL"} ({len(files)-failed}/{len(files)})')
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
