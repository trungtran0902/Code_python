#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
check_oneway_connection.py

Công cụ kiểm tra kết nối một chiều (oneway) trong dữ liệu OSM.
- Đọc nodes và ways từ file OSM PBF
- Xác định các ways có tag `oneway`
- Tại các node nơi chỉ có 2 way tiếp xúc, kiểm tra xem có vấn đề về hướng vào/ra hay không

Đầu ra: file text liệt kê các node có vấn đề (hai way đều chỉ vào hoặc hai way đều chỉ ra node)
"""

import sys
from pathlib import Path
from collections import defaultdict

VENDOR_DIR = Path(__file__).resolve().parents[2] / "_vendor_geo"
if VENDOR_DIR.exists():
    sys.path.insert(0, str(VENDOR_DIR))

import osmium

ALLOWED_HIGHWAY_TYPES = {
    "motorway", "trunk", "primary", "secondary", "tertiary",
    "unclassified", "residential", "service", "living_street",
    "motorway_link", "trunk_link", "primary_link", "secondary_link",
    "tertiary_link", "road"
}

class OSMReader(osmium.SimpleHandler):
    """
    Handler để thu thập thông tin cần thiết từ OSM:
    - node_locations: vị trí của node
    - way_to_node_ids: danh sách node theo way
    - node_to_way_ids: các way gắn vào một node
    - oneway_ways: các way được coi là một chiều (1: forward, -1: reverse)
    - way_tags: một số tag hữu ích (name, ref, highway)
    """
    def __init__(self):
        super().__init__()
        self.node_to_way_ids = defaultdict(set)
        self.way_to_node_ids = {}
        self.node_locations = {}
        self.oneway_ways = {}
        self.way_tags = {}

    def node(self, n):
        # Lưu vị trí của node nếu hợp lệ
        if n.location.valid():
            self.node_locations[n.id] = (n.location.lat, n.location.lon)

    def way(self, w):
        # Lọc chỉ xử lý các loại đường quan tâm
        tags = {t.k: t.v for t in w.tags}
        highway = tags.get("highway")
        if highway not in ALLOWED_HIGHWAY_TYPES:
            return

        node_ids = [n.ref for n in w.nodes]
        if len(node_ids) < 2:
            return

        way_id = w.id
        self.way_to_node_ids[way_id] = node_ids
        # Lưu một số tag để hiển thị sau này
        self.way_tags[way_id] = {
            "name": tags.get("name", ""),
            "ref": tags.get("ref", ""),
            "highway": highway,
        }

        # Map node -> set(way_id) để biết những way nào chạm tại một node
        for nid in node_ids:
            self.node_to_way_ids[nid].add(way_id)

        # Xác định xem way này có phải là oneway không và hướng (1 hoặc -1)
        direction = self.normalize_oneway(tags)
        if direction != 0:
            self.oneway_ways[way_id] = direction

    @staticmethod
    def normalize_oneway(tags):
        """
        Chuẩn hóa tag oneway và các tình huống đặc biệt:
        - roundabout: mặc định coi là oneway
        - 'yes', 'true', '1' => forward (1)
        - '-1', 'reverse' => reverse (-1)
        Trả về 0 nếu không phải oneway.
        """
        oneway = tags.get("oneway", "").strip().lower()
        junction = tags.get("junction", "").strip().lower()
        if junction == "roundabout" and not oneway:
            return 1
        if oneway in ("yes", "true", "1"):
            return 1
        if oneway in ("-1", "reverse"):
            return -1
        return 0


def get_way_direction_at_node(way_id, node_id, reader):
    """
    Xác định khả năng vào/ra của một way tại một node cụ thể.

    Trả về tuple (can_in, can_out):
    - can_in: có thể vào node từ way này hay không (tức là hướng cho phép di chuyển vào node)
    - can_out: có thể rời node theo way này hay không

    Nguyên tắc:
    - Nếu way không phải oneway thì mặc định cả vào và ra đều True (với điều kiện node thuộc way)
    - Nếu way oneway thì chỉ cho phép theo hướng đã chuẩn hóa (nút đầu ordered[0] chỉ cho out, ordered[-1] chỉ cho in)
    - Nếu way là vòng kín (closed way) thì bỏ qua (False, False)
    """
    node_ids = reader.way_to_node_ids[way_id]

    if len(node_ids) < 2:
        return False, False

    # Nếu way khép kín (closed loop), bỏ qua — thường không phải đường di chuyển giữa nút
    if node_ids[0] == node_ids[-1]:
        return False, False

    if way_id not in reader.oneway_ways:
        # Không phải oneway: nếu node thuộc way thì có cả in và out
        return (True, True) if node_id in node_ids else (False, False)

    direction = reader.oneway_ways[way_id]
    # Nếu direction == 1 thì danh sách node theo thứ tự ban đầu, nếu -1 thì đảo ngược
    ordered = node_ids if direction == 1 else list(reversed(node_ids))

    # Nếu node là node bắt đầu theo thứ tự => chỉ có outgoing
    if node_id == ordered[0]:
        return False, True
    # Nếu node là node kết thúc theo thứ tự => chỉ có incoming
    if node_id == ordered[-1]:
        return True, False
    # Nếu node nằm ở giữa => có cả incoming và outgoing
    if node_id in ordered[1:-1]:
        return True, True
    return False, False


def get_way_label(way_id, reader):
    """
    Tạo nhãn mô tả cho way để in ra trong báo cáo.
    Sử dụng `name` và `ref` nếu có, kèm loại `highway`.
    """
    tags = reader.way_tags.get(way_id, {})
    name = tags.get("name") or ""
    ref = tags.get("ref") or ""
    highway = tags.get("highway") or ""
    if name and ref:
        return f"{name} ({ref}) [{highway}]"
    if name:
        return f"{name} [{highway}]"
    if ref:
        return f"{ref} [{highway}]"
    return f"way_id={way_id} [{highway}]"


def check_connectivity(reader, output="out.txt"):
    """
    Kiểm tra các điểm kết nối giữa các way one-way.

    Algorithm:
    - Duyệt qua mỗi way có oneway
    - Lấy node bắt đầu và kết thúc (theo hướng chuẩn hóa)
    - Với mỗi node, nếu có đúng 2 way tiếp xúc ở node đó thì kiểm tra khả năng in/out
    - Báo lỗi **chỉ** khi cả 2 way đều cho phép vào node (không có lối ra),
      hoặc cả 2 way đều cho phép rời node (không có lối vào).

    Trả về danh sách các lỗi để dùng chương trình hoặc kiểm tra tự động.
    """
    results = []
    checked_nodes = set()

    for way_id, direction in reader.oneway_ways.items():
        node_ids = reader.way_to_node_ids[way_id]
        ordered = node_ids if direction == 1 else list(reversed(node_ids))
        start_node = ordered[0]
        end_node = ordered[-1]

        for node_id in (start_node, end_node):
            if node_id in checked_nodes:
                continue
            checked_nodes.add(node_id)

            ways_at_node = reader.node_to_way_ids.get(node_id, set())
            # Chỉ quan tâm các node có đúng 2 way (đường giao nhánh đơn giản)
            if len(ways_at_node) != 2:
                continue

            in_count = 0
            out_count = 0
            touch_details = []

            for wid in sorted(ways_at_node):
                can_in, can_out = get_way_direction_at_node(wid, node_id, reader)
                if can_in:
                    in_count += 1
                if can_out:
                    out_count += 1
                touch_details.append({
                    "way_id": wid,
                    "label": get_way_label(wid, reader),
                    "can_in": can_in,
                    "can_out": can_out,
                    "nodes": reader.way_to_node_ids[wid],
                })

            problem = None
            # Chỉ báo lỗi khi cả hai way đều chỉ vào node (in_count==2, out_count==0)
            # hoặc cả hai way đều chỉ ra node (in_count==0, out_count==2)
            if in_count == 2 and out_count == 0:
                problem = "ONLY_INCOMING"
            elif in_count == 0 and out_count == 2:
                problem = "ONLY_OUTGOING"

            if problem:
                lat, lon = reader.node_locations.get(node_id, (None, None))
                results.append({
                    "node_id": node_id,
                    "lat": lat,
                    "lon": lon,
                    "problem": problem,
                    "ways": touch_details,
                    "in_count": in_count,
                    "out_count": out_count,
                })

    # Ghi báo cáo ra file
    with open(output, "w", encoding="utf-8") as f:
        if not results:
            f.write("Khong phat hien loi.\n")
            return results

        f.write(f"Phat hien {len(results)} loi.\n\n")
        for i, item in enumerate(results, 1):
            f.write(f"[{i}] Node: {item['node_id']}\n")
            f.write(f"    Position: lat={item['lat']}, lon={item['lon']}\n")
            f.write(f"    Problem: {item['problem']}\n")
            f.write(f"    in_count={item['in_count']}, out_count={item['out_count']}\n")
            f.write("    Ways:\n")
            for w in item["ways"]:
                f.write(
                    f"      - {w['label']}, way_id={w['way_id']}, "
                    f"can_in={w['can_in']}, can_out={w['can_out']}, "
                    f"node_ids={w['nodes']}\n"
                )
            f.write("\n")

    return results


def main():
    """Entry point: đọc file OSM PBF và chạy kiểm tra."""
    if len(sys.argv) < 2:
        print("Usage: python check_oneway_simple_updated.py input.osm.pbf [output.txt]")
        return

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) >= 3 else "out.txt"

    reader = OSMReader()
    # locations=True để thu thập tọa độ node
    reader.apply_file(input_file, locations=True)

    results = check_connectivity(reader, output_file)
    print(f"Done. Found {len(results)} errors -> {output_file}")


if __name__ == "__main__":
    main()
