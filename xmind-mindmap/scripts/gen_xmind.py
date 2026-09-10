# -*- coding: utf-8 -*-
"""
XMind 思维导图生成器（纯 Python 内置，从零生成新版格式 .xmind）
==============================================================
新版 XMind(2020+) 的 .xmind 文件 = 一个 zip 包，内含：
    content.json       真正的导图数据(sheet -> rootTopic -> children.attached)
    metadata.json      版本信息
    manifest.json      文件清单（注意：不能把 manifest.json 自己列进去！）
    content.xml        旧版占位符（XMind 读的是 JSON，这只是写给老版本的警告）
    Thumbnails/thumbnail.png  缩略图（manifest 里要列它）

用法：
    python gen_xmind.py --root "中心主题" --tree tree.json --out output.xmind

tree.json 结构（Claude 提炼大纲后就是要生成这个）：
    {"title": 中心主题, "children": [
         {"title": "分支1", "children": [{"title": "叶子1"}, {"title": "叶子2"}]},
         {"title": "分支2", "children": [...]}
    ]}

本脚本不依赖任何第三方库，Python 3 自带 zipfile + json 即可运行。
"""
import argparse
import base64
import json
import os
import struct
import uuid
import zipfile
import zlib

# 自动配色调色板（XMind 打开时会按顺序给各分支自动上色）
COLOR_LIST = "#FF6B6B #FF9F69 #97D3B6 #88E2D7 #6FD0F9 #E18BEE"


def _hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _zlib_png(width, height, pixel_fn):
    """纯 Python 生成 PNG（不依赖 PIL）。pixel_fn(x,y)->(r,g,b)。"""
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # 每行滤波类型 0
        for x in range(width):
            raw.extend(pixel_fn(x, y))
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        c += struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        return c
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)  # 8bit 真彩
    idat = zlib.compress(bytes(raw), 9)
    return sig + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


def make_thumbnail(width=480, height=320):
    """生成一个干净的浅色占位缩略图（避免黑屏）。XMind 打开-保存后会自动覆盖成真导图封面。"""
    bg = (242, 245, 250)
    center = (width // 2, height // 2)
    def pixel(x, y):
        dx, dy = x - center[0], y - center[1]
        if dx * dx + dy * dy <= 42 * 42:
            return (66, 76, 132)  # 中央深蓝圆点，示意
        return bg
    return _zlib_png(width, height, pixel)


def _uid(tag=""):
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# 主题（theme）
# ---------------------------------------------------------------------------
# ⚠️ 踩坑记录（改这个函数前必读，两个坑都踩过了）：
#
# 【坑 1】每个 topic 层级都必须有 "fo:color"，否则 XMind 会退回它自己的默认文字色，
#   而中央主题的默认文字色是「白色」（XMind 的中央主题本来设计成彩色填充块 + 白字）。
#   偏偏中央主题又是 fill-pattern:none（无填充白底）→ 白字 + 白底 = 看不见文字。
#   注意：数据里 title 一直都在，不是内容丢了，是「隐身」了——所以表现出来像是
#   「打不进去字 / 改了没反应」，其实是打得进去、只是打什么都看不见。
#   → 中央主题的 fo:color 显式写死 "#000000"，不依赖 XMind 的 "inherited" 解析。
#
# 【坑 2】"svg:fill" 是【形状填充色】，不是文字色！各层级的正确写法不一样：
#     centralTopic        → 字面量颜色（"#000000"）
#     mainTopic/subTopic  → "inherited"（继承分支颜色）
#   给 mainTopic/subTopic 写死 "#000000" 会把节点整块涂成纯黑，
#   黑底 + 黑字 = 叶子节点看不见文字（整片变成黑条）。
#   这个坑只有在同时给了 shape-class（节点有形状）时才会暴露。
#
# 下面这套属性是从「XMind 自己保存出来的、渲染正常的文件」里逐字段抄出来的，
# 别凭感觉改。唯一的手工改动是 centralTopic 的 fo:color 写成 "#000000"。

def _topic_props(font_size, font_weight, text_align="left",
                 fill="inherited", fill_pattern="none",
                 font_color="inherited", line_color="inherited",
                 line_pattern="inherited", border_line_color="inherited",
                 line_class="org.xmind.branchConnection.roundedElbow"):
    """一个 topic 层级的完整属性集。

    fill       —— 形状填充色。mainTopic/subTopic 必须用 "inherited"，
                  写死颜色会把节点涂成纯色（黑底黑字就看不见字了）。
    font_color —— 文字色。只有 centralTopic 需要写死 "#000000"。
    """
    return {
        "fo:font-family": "NeverMind",
        "fo:font-size": font_size,
        "fo:font-weight": font_weight,
        "fo:font-style": "normal",
        "fo:color": font_color,
        "fo:text-transform": "manual",
        "fo:text-decoration": "none",
        "fo:text-align": text_align,
        "svg:fill": fill,
        "fill-pattern": fill_pattern,
        "line-width": "2pt",
        "line-color": line_color,
        "line-pattern": line_pattern,
        "border-line-color": border_line_color,
        "border-line-width": "0pt",
        "border-line-pattern": "inherited",
        "shape-class": "org.xmind.topicShape.roundedRect",
        "line-class": line_class,
        "arrow-end-class": "inherited",
        "alignment-by-level": "inherited",
    }


def _theme():
    """sheet 级主题，内含待调色板 -> 触发自动配色。"""
    return {
        "map": {
            "id": _uid(),
            "properties": {
                "svg:fill": "#ffffff",
                "multi-line-colors": COLOR_LIST,
                "color-list": COLOR_LIST,
                "line-tapered": "none",
            },
        },
        "centralTopic": {
            "id": _uid(),
            "properties": _topic_props(
                "30pt", "800", text_align="center",
                fill="#000000", fill_pattern="none",
                font_color="#000000",          # 只有中心主题写死黑色
                line_color="#ADADAD", line_pattern="solid",
                border_line_color="#000000",
                line_class="org.xmind.branchConnection.curve",
            ),
        },
        "mainTopic": {
            "id": _uid(),
            "properties": _topic_props("18pt", "500", fill_pattern="solid"),
        },
        "subTopic": {
            # fill 保持默认的 "inherited"，写死颜色会变成黑条
            "id": _uid(),
            "properties": _topic_props("14pt", "400"),
        },
        "floatingTopic": {
            "id": _uid(),
            "properties": _topic_props("14pt", "500", fill="#EEEBEE",
                                       fill_pattern="solid",
                                       line_pattern="solid",
                                       border_line_color="#EEEBEE"),
        },
        "summaryTopic": {
            "id": _uid(),
            "properties": _topic_props("14pt", "400", fill="#000000",
                                       border_line_color="#000000"),
        },
        "calloutTopic": {
            "id": _uid(),
            "properties": _topic_props("14pt", "400", fill="#000000",
                                       fill_pattern="solid",
                                       border_line_color="#000000"),
        },
        "importantTopic": {
            "id": _uid(),
            "properties": {
                "fo:font-weight": "bold",
                "svg:fill": "#7F00AC",
                "fill-pattern": "solid",
                "border-line-color": "#7F00AC",
                "border-line-width": "0",
            },
        },
        "minorTopic": {
            "id": _uid(),
            "properties": {
                "fo:font-weight": "bold",
                "svg:fill": "#82004A",
                "fill-pattern": "solid",
                "border-line-color": "#82004A",
                "border-line-width": "0",
            },
        },
        "level3": {
            "id": _uid(),
            "properties": _topic_props("14pt", "400", fill_pattern="solid"),
        },
        "boundary": {
            "id": _uid(),
            "properties": {
                "fo:font-family": "NeverMind",
                "fo:font-size": "14pt",
                "fo:font-weight": "400",
                "fo:font-style": "normal",
                "fo:color": "inherited",
                "fo:text-transform": "manual",
                "fo:text-decoration": "none",
                "fo:text-align": "center",
                "svg:fill": "#9B9B9B",
                "fill-pattern": "solid",
                "line-width": "2",
                "line-color": "#00000066",
                "line-pattern": "dash",
                "shape-class": "org.xmind.boundaryShape.roundedRect",
            },
        },
        "zone": {
            "id": _uid(),
            "properties": {
                "fo:font-family": "NeverMind, sans-serif, Microsoft YaHei, "
                                  "PingFang SC, Microsoft JhengHei, "
                                  "Apple Color Emoji, Segoe UI Emoji, "
                                  "Segoe UI Symbol, Noto Color Emoji",
                "fo:font-size": "12",
                "fo:font-weight": "400",
                "fo:font-style": "normal",
                "fo:color": "inherited",
                "fo:text-transform": "manual",
                "fo:text-decoration": "none",
                "fo:text-align": "left",
                "svg:fill": "#9b9b9b33",
                "fill-pattern": "none",
                "border-line-color": "#00000066",
                "border-line-width": "2pt",
                "border-line-pattern": "solid",
            },
        },
        "summary": {
            "id": _uid(),
            "properties": {
                "line-width": "2pt",
                "line-color": "#000000",
                "line-pattern": "solid",
                "shape-class": "org.xmind.summaryShape.round",
            },
        },
        "relationship": {
            "id": _uid(),
            "properties": {
                "fo:font-family": "NeverMind",
                "fo:font-size": "13pt",
                "fo:font-weight": "400",
                "fo:font-style": "normal",
                "fo:color": "inherited",
                "fo:text-transform": "manual",
                "fo:text-decoration": "none",
                "fo:text-align": "center",
                "line-width": "2",
                "line-color": "#00000066",
                "line-pattern": "dash",
                "shape-class": "org.xmind.relationshipShape.curved",
                "arrow-begin-class": "org.xmind.arrowShape.none",
                "arrow-end-class": "org.xmind.arrowShape.triangle",
            },
        },
    }


def _node(title, children=None, markers=None, is_topic_class=False):
    """构造一个 xmind topic 节点。"""
    n = {"id": _uid(), "title": title}
    if is_topic_class:
        n["class"] = "topic"
    if markers:
        n["markers"] = [{"markerId": m} for m in markers]
    if children:
        n["children"] = {"attached": children}
    return n


def _marker_for_index(i):
    """给第 i 个分支自动分配一个图标（兜底用，超出就省略）。"""
    names = [
        "priority-1", "priority-2", "priority-3", "priority-4", "priority-5",
        "priority-6", "priority-7", "priority-8", "priority-9",
    ]
    return [names[i]] if i < len(names) else None


def build_content(root_title, tree_children, add_icons=True):
    sheet_id = _uid("sheet")
    root = _node(root_title, is_topic_class=True)
    root["structureClass"] = "org.xmind.ui.map.clockwise"
    if tree_children:
        attached = []
        for i, br in enumerate(tree_children):
            markers = _marker_for_index(i) if add_icons else None
            subs = br.get("children") or []
            node = _node(br["title"], children=[_node(s["title"]) for s in subs], markers=markers)
            attached.append(node)
        root["children"] = {"attached": attached}

    sheet = {
        "id": sheet_id,
        "revisionId": _uid("rev"),
        "class": "sheet",
        "title": root_title,
        "rootTopic": root,
        "relationships": [],
        "topicOverlapping": "overlap",
        "floatingTopicAutoColor": "follow-color-theme",
        "relationshipAutoColor": "follow-target-topic",
        "arrangeableLayerOrder": [],
        "zones": [],
        "extensions": [],
        "theme": _theme(),
    }
    return sheet_id, [sheet]


def build_metadata(sheet_id):
    return {
        "dataStructureVersion": "3",
        "creator": {"name": "Vana", "version": "26.05.01106"},
        "layoutEngineVersion": "5",
    }


def build_manifest():
    # 注意：file-entries 里不要列 manifest.json 自己，要列缩略图
    return {
        "file-entries": {
            "content.json": {},
            "metadata.json": {},
            "Thumbnails/thumbnail.png": {},
        }
    }


CONTENT_XML_STUB = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
    '<xmap-content xmlns="urn:xmind:xmap:xmlns:content:2.0" version="2.0">'
    '<sheet id="__stub" modified-by="Vana">'
    '<topic id="__stubroot" structure-class="org.xmind.ui.map.clockwise">'
    "<title>该文件由自动化工具生成，实际内容见 content.json</title>"
    "</topic></sheet></xmap-content>"
)

def save_xmind(out_path, root_title, tree_children, add_icons=True):
    sheet_id, content = build_content(root_title, tree_children, add_icons)
    files = {
        "content.json": json.dumps(content, ensure_ascii=False, indent=2),
        "metadata.json": json.dumps(build_metadata(sheet_id), ensure_ascii=False, indent=2),
        "manifest.json": json.dumps(build_manifest(), ensure_ascii=False, indent=2),
        "content.xml": CONTENT_XML_STUB,
        "Thumbnails/thumbnail.png": make_thumbnail(),
    }
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return out_path


def load_tree(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="中心主题名")
    ap.add_argument("--tree", help="大纲 JSON 文件路径（可选，没有则用内置示例）")
    ap.add_argument("--out", required=True, help="输出 .xmind 路径")
    ap.add_argument("--no-icons", action="store_true", help="不加自动图标")
    args = ap.parse_args()

    branches = load_tree(args.tree).get("children") if args.tree else None
    if branches is None:
        branches = [
            {"title": "技术路线", "children": [{"title": "纯Python内置"}, {"title": "官方npm库"}]},
            {"title": "内容来源", "children": [{"title": "给主题生成"}, {"title": "给文字提炼"}]},
        ]
    save_xmind(args.out, args.root, branches, add_icons=not args.no_icons)
    print("已生成:", args.out, "| 分支数:", len(branches))
