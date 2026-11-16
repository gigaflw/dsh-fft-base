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

REQUIRED = ('xmlns', 'width', 'height', 'viewBox')
EXPECT_XMLNS = 'http://www.w3.org/2000/svg'


def root_tag(src):
    m = re.search(r'<svg\b[^>]*>', src[:4096])
    return m.group(0) if m else None


def attr(tag, name):
    m = re.search(rf'\b{name}\s*=\s*"([^"]*)"', tag)
    return m.group(1) if m else None


def check(path):
    """返回 (ok, [问题描述])"""
    problems = []
    try:
        src = open(path, encoding='utf-8').read()
    except OSError as e:
        return False, [f'读不到文件：{e}']

    tag = root_tag(src)
    if tag is None:
        return False, ['找不到 <svg> 根元素（文件可能不是 SVG，或为空）']

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

    body = src[len(tag):] if tag else src
    ext = [u for u in re.findall(r'(?:href|src|xlink:href)\s*=\s*"(?!#)([^"]+)"', body)
           if u.startswith(('http://', 'https://', '//'))]
    if ext:
        problems.append(f'含外部引用（离线会加载失败）：{ext[:3]}')

    return (not problems), problems


def main(argv):
    quiet = '--quiet' in argv
    files = [a for a in argv[1:] if not a.startswith('--')]
    if not files:
        print('用法：python3 check_svg.py chart.svg [chart2.svg ...]')
        return 2

    failed = 0
    for f in files:
        ok, problems = check(f)
        if ok:
            if not quiet:
                print(f'  OK   {f}')
        else:
            failed += 1
            print(f'  FAIL {f}')
            for p in problems:
                print(f'       - {p}')
    print(f'\n{"PASS" if not failed else "FAIL"} ({len(files)-failed}/{len(files)})')
    return 0 if not failed else 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
