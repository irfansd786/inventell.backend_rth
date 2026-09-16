"""
Seed script to populate backend database with:
1. 24 Real FMCG Retail Products
2. 120 Orders (100 Today's Orders on 2026-09-09 + 20 Historical Orders)
3. Corresponding OrderItems with realistic quantities, prices, and status progress.
"""

import datetime
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "invintell_dev.db"

PRODUCTS = [
    {"id": 1, "sku": "BEV-001", "name": "Coca Cola 500ml", "category": "Beverages", "price": 40.0, "cost": 28.0, "wh": 350, "store": 85, "reorder": 50},
    {"id": 2, "sku": "SNK-001", "name": "Lays Classic Chips 50g", "category": "Snacks", "price": 20.0, "cost": 13.0, "wh": 420, "store": 120, "reorder": 60},
    {"id": 3, "sku": "BEV-002", "name": "Pepsi Can 330ml", "category": "Beverages", "price": 35.0, "cost": 24.0, "wh": 280, "store": 70, "reorder": 40},
    {"id": 4, "sku": "FD-001", "name": "Maggi 2-Min Noodles 70g", "category": "Food", "price": 15.0, "cost": 10.0, "wh": 500, "store": 150, "reorder": 80},
    {"id": 5, "sku": "SNK-002", "name": "Parle-G Biscuits 100g", "category": "Snacks", "price": 10.0, "cost": 7.0, "wh": 600, "store": 180, "reorder": 100},
    {"id": 6, "sku": "PC-001", "name": "Dove Bath Soap 100g", "category": "Personal Care", "price": 65.0, "cost": 45.0, "wh": 240, "store": 60, "reorder": 30},
    {"id": 7, "sku": "HH-001", "name": "Vim Dishwash Liquid 250ml", "category": "Household", "price": 55.0, "cost": 38.0, "wh": 220, "store": 55, "reorder": 30},
    {"id": 8, "sku": "DRY-001", "name": "Amul Taaza Milk 1L", "category": "Dairy", "price": 70.0, "cost": 58.0, "wh": 300, "store": 90, "reorder": 45},
    {"id": 9, "sku": "SNK-003", "name": "Cadbury Dairy Milk 50g", "category": "Snacks", "price": 45.0, "cost": 32.0, "wh": 380, "store": 110, "reorder": 50},
    {"id": 10, "sku": "SNK-004", "name": "Kurkure Masala Munch 90g", "category": "Snacks", "price": 20.0, "cost": 14.0, "wh": 450, "store": 130, "reorder": 70},
    {"id": 11, "sku": "BEV-003", "name": "Sprite Lime 500ml", "category": "Beverages", "price": 40.0, "cost": 28.0, "wh": 310, "store": 75, "reorder": 40},
    {"id": 12, "sku": "SNK-005", "name": "Bingo Mad Angles 75g", "category": "Snacks", "price": 20.0, "cost": 13.0, "wh": 390, "store": 95, "reorder": 50},
    {"id": 13, "sku": "BEV-004", "name": "Thums Up 500ml", "category": "Beverages", "price": 40.0, "cost": 27.0, "wh": 340, "store": 80, "reorder": 45},
    {"id": 14, "sku": "SNK-006", "name": "Britannia Good Day 120g", "category": "Snacks", "price": 30.0, "cost": 21.0, "wh": 360, "store": 90, "reorder": 50},
    {"id": 15, "sku": "SNK-007", "name": "Haldiram Bhujia Sev 150g", "category": "Snacks", "price": 50.0, "cost": 36.0, "wh": 290, "store": 70, "reorder": 40},
    {"id": 16, "sku": "SNK-008", "name": "Oreo Vanilla Cookies 120g", "category": "Snacks", "price": 35.0, "cost": 24.0, "wh": 330, "store": 85, "reorder": 45},
    {"id": 17, "sku": "GRO-001", "name": "Tata Salt Vacuum Evaporated 1kg", "category": "Food", "price": 28.0, "cost": 20.0, "wh": 480, "store": 140, "reorder": 80},
    {"id": 18, "sku": "BEV-005", "name": "Red Bull Energy Drink 250ml", "category": "Beverages", "price": 125.0, "cost": 92.0, "wh": 180, "store": 40, "reorder": 25},
    {"id": 19, "sku": "PC-002", "name": "Dettol Original Soap 75g", "category": "Personal Care", "price": 42.0, "cost": 29.0, "wh": 260, "store": 65, "reorder": 35},
    {"id": 20, "sku": "PC-003", "name": "Colgate Strong Teeth 150g", "category": "Personal Care", "price": 95.0, "cost": 68.0, "wh": 210, "store": 50, "reorder": 30},
    {"id": 21, "sku": "BEV-006", "name": "Frooti Mango Drink 600ml", "category": "Beverages", "price": 38.0, "cost": 26.0, "wh": 320, "store": 80, "reorder": 40},
    {"id": 22, "sku": "GRO-002", "name": "Nescafe Classic Coffee 50g", "category": "Beverages", "price": 180.0, "cost": 132.0, "wh": 150, "store": 35, "reorder": 20},
    {"id": 23, "sku": "SNK-009", "name": "Sunfeast Dark Fantasy 75g", "category": "Snacks", "price": 40.0, "cost": 27.0, "wh": 270, "store": 65, "reorder": 35},
    {"id": 24, "sku": "HH-002", "name": "Tide Plus Detergent Powder 1kg", "category": "Household", "price": 140.0, "cost": 102.0, "wh": 190, "store": 45, "reorder": 25},
]

DESTINATIONS = [
    "Main Street Store",
    "Sector 18 Store",
    "Downtown Express",
    "Cyber City Store",
    "North Bay Hub",
    "Direct Customer Delivery",
]

def generate_orders():
    # Deterministic generation using fixed pseudo-random sequencing
    import random
    rng = random.Random(42)  # Fixed seed for absolute determinism

    # 100 Today's orders (reconciled lifecycle states)
    # 15 Pending + 10 Confirmed = 25
    # 8 Partially Allocated + 12 Allocated = 20
    # 6 Ready for Picking + 12 Picking = 18
    # 5 Ready for Packing + 10 Packing = 15
    # 8 Packed + 4 Ready for Dispatch = 12
    # 6 Dispatched + 4 Delivered = 10
    # Sum = 100
    statuses_today = (
        ["Pending"] * 15 +
        ["Confirmed"] * 10 +
        ["Partially Allocated"] * 8 +
        ["Allocated"] * 12 +
        ["Ready for Picking"] * 6 +
        ["Picking"] * 12 +
        ["Ready for Packing"] * 5 +
        ["Packing"] * 10 +
        ["Packed"] * 8 +
        ["Ready for Dispatch"] * 4 +
        ["Dispatched"] * 6 +
        ["Delivered"] * 4
    )

    orders = []

    # Build 100 Today orders (2026-09-09)
    for i in range(100):
        order_num = f"ORD-2026-{101 + i:05d}"
        status = statuses_today[i]

        # Spread timestamps across 06:15 to 21:30 on 2026-09-09
        minutes = 375 + int((i / 100.0) * 915)  # 06:15 to 21:30
        hh = minutes // 60
        mm = minutes % 60
        created_at = f"2026-09-09T{hh:02d}:{mm:02d}:00Z"
        date_label = "09 Sep 2026"

        # Multi-product distribution:
        # ~30 orders: 1 product
        # ~35 orders: 2 products
        # ~25 orders: 3 products
        # ~10 orders: 4 products
        if i < 30:
            num_products = 1
        elif i < 65:
            num_products = 2
        elif i < 90:
            num_products = 3
        else:
            num_products = 4

        # Cycle products to ensure full coverage across all 24 products in each stage
        chosen_indices = [(i + p * 5) % len(PRODUCTS) for p in range(num_products)]
        chosen_products = [PRODUCTS[idx] for idx in chosen_indices]

        # Flag exactly 5 orders as at-risk / exception
        is_at_risk = i in (7, 18, 38, 62, 88)
        priority = "Critical" if is_at_risk else ("High" if i % 4 == 0 else ("Low" if i % 7 == 0 else "Normal"))
        order_type = "Customer Order" if i % 8 == 0 else ("Transfer" if i % 5 == 0 else "Replenishment")
        destination = DESTINATIONS[i % len(DESTINATIONS)]
        source = "Main Street Store" if order_type == "Customer Order" else "Central Warehouse"

        items = []
        for p in chosen_products:
            requested = 10 + ((i * 7 + p["id"] * 5) % 45)  # 10 to 54 units
            if status in ("Pending", "Confirmed", "Draft"):
                allocated = 0
                picked = 0
                packed = 0
            elif status == "Partially Allocated":
                allocated = requested // 2
                picked = 0
                packed = 0
            elif status in ("Allocated", "Ready for Picking"):
                allocated = requested
                picked = 0
                packed = 0
            elif status == "Picking":
                allocated = requested
                picked = int(requested * 0.6)
                packed = 0
            elif status in ("Ready for Packing", "Picked"):
                allocated = requested
                picked = requested
                packed = 0
            elif status == "Packing":
                allocated = requested
                picked = requested
                packed = int(requested * 0.5)
            else:  # Packed, Ready for Dispatch, Dispatched, Delivered
                allocated = requested
                picked = requested
                packed = requested

            unit_price = p["price"]
            subtotal = requested * unit_price
            items.append({
                "product_id": p["id"],
                "product": p["name"],
                "sku": p["sku"],
                "barcode": f"89012345{p['id']:04d}",
                "requested": requested,
                "allocated": allocated,
                "picked": picked,
                "packed": packed,
                "unitPrice": unit_price,
                "subtotal": subtotal,
                "storeStock": p["store"],
                "warehouseStock": p["wh"],
            })

        total_units = sum(it["requested"] for it in items)
        total_amount = sum(it["subtotal"] for it in items)

        orders.append({
            "id": order_num,
            "order_number": order_num,
            "createdAt": created_at,
            "dateLabel": date_label,
            "type": order_type,
            "source": source,
            "destination": destination,
            "priority": priority,
            "status": status,
            "expectedDate": "10 Sep 2026",
            "isAtRisk": is_at_risk,
            "items": items,
            "itemsCount": len(items),
            "totalUnits": total_units,
            "totalAmount": total_amount,
            "picker": "Ramesh K." if status in ("Picking", "Ready for Packing", "Packing", "Packed", "Ready for Dispatch", "Dispatched", "Delivered") else "Unassigned",
            "packer": "Sunita P." if status in ("Packed", "Ready for Dispatch", "Dispatched", "Delivered") else "Unassigned",
            "notes": "Fast-track retail store fulfillment batch.",
        })

    # 20 Historical orders on earlier dates (2026-09-08 down to 2026-08-28)
    hist_dates = [
        ("08 Sep 2026", "2026-09-08"),
        ("07 Sep 2026", "2026-09-07"),
        ("06 Sep 2026", "2026-09-06"),
        ("05 Sep 2026", "2026-09-05"),
        ("03 Sep 2026", "2026-09-03"),
        ("01 Sep 2026", "2026-09-01"),
        ("28 Aug 2026", "2026-08-28"),
    ]

    for h in range(20):
        order_num = f"ORD-2026-{201 + h:05d}"
        d_label, d_prefix = hist_dates[h % len(hist_dates)]
        created_at = f"{d_prefix}T{10 + (h % 8):02d}:30:00Z"
        status = "Delivered" if h < 14 else ("Dispatched" if h < 18 else "Cancelled")
        
        num_products = 1 + (h % 3)
        chosen_indices = [(h * 2 + p) % len(PRODUCTS) for p in range(num_products)]
        chosen_products = [PRODUCTS[idx] for idx in chosen_indices]

        items = []
        for p in chosen_products:
            requested = 20 + (h * 3) % 30
            unit_price = p["price"]
            items.append({
                "product_id": p["id"],
                "product": p["name"],
                "sku": p["sku"],
                "barcode": f"89012345{p['id']:04d}",
                "requested": requested,
                "allocated": requested if status != "Cancelled" else 0,
                "picked": requested if status != "Cancelled" else 0,
                "packed": requested if status != "Cancelled" else 0,
                "unitPrice": unit_price,
                "subtotal": requested * unit_price,
                "storeStock": p["store"],
                "warehouseStock": p["wh"],
            })

        orders.append({
            "id": order_num,
            "order_number": order_num,
            "createdAt": created_at,
            "dateLabel": d_label,
            "type": "Replenishment" if h % 2 == 0 else "Transfer",
            "source": "Central Warehouse",
            "destination": DESTINATIONS[h % len(DESTINATIONS)],
            "priority": "Normal",
            "status": status,
            "expectedDate": d_label,
            "isAtRisk": False,
            "items": items,
            "itemsCount": len(items),
            "totalUnits": sum(it["requested"] for it in items),
            "totalAmount": sum(it["subtotal"] for it in items),
            "picker": "Amit V.",
            "packer": "Sunita P.",
            "notes": "Historical store requisition.",
        })

    return orders

def seed_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # 1. Update/insert 24 products
    # Mark old M5 products inactive
    cur.execute("UPDATE products SET is_active = 0 WHERE sku NOT IN (" + ",".join(f"'{p['sku']}'" for p in PRODUCTS) + ")")

    for p in PRODUCTS:
        cur.execute("SELECT id FROM products WHERE sku = ?", (p["sku"],))
        row = cur.fetchone()
        if row:
            cur.execute("""
                UPDATE products 
                SET name = ?, category = ?, price = ?, cost_price = ?, is_active = 1
                WHERE sku = ?
            """, (p["name"], p["category"], p["price"], p["cost"], p["sku"]))
            pid = row[0]
        else:
            cur.execute("""
                INSERT INTO products (sku, name, category, price, cost_price, unit, is_active)
                VALUES (?, ?, ?, ?, ?, 'pcs', 1)
            """, (p["sku"], p["name"], p["category"], p["price"], p["cost"]))
            pid = cur.lastrowid

        # Update or insert inventory
        cur.execute("SELECT id FROM inventory WHERE product_id = ?", (pid,))
        inv_row = cur.fetchone()
        if inv_row:
            cur.execute("""
                UPDATE inventory 
                SET warehouse_stock = ?, store_stock = ?, reserved_stock = 0, reorder_level = ?, status = 'Healthy'
                WHERE product_id = ?
            """, (p["wh"], p["store"], p["reorder"], pid))
        else:
            cur.execute("""
                INSERT INTO inventory (product_id, warehouse_stock, store_stock, reserved_stock, reorder_level, status)
                VALUES (?, ?, ?, 0, ?, 'Healthy')
            """, (pid, p["wh"], p["store"], p["reorder"]))

    # Clean up any duplicate or old test orders
    cur.execute("DELETE FROM order_items")
    cur.execute("DELETE FROM orders")

    orders = generate_orders()
    for o in orders:
        cur.execute("""
            INSERT INTO orders (order_number, status, total_amount, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (o["order_number"], o["status"].upper(), o["totalAmount"], o["createdAt"], o["createdAt"]))
        order_db_id = cur.lastrowid

        for it in o["items"]:
            cur.execute("SELECT id FROM products WHERE sku = ?", (it["sku"],))
            p_row = cur.fetchone()
            p_id = p_row[0] if p_row else it["product_id"]
            cur.execute("""
                INSERT INTO order_items (order_id, product_id, quantity, unit_price)
                VALUES (?, ?, ?, ?)
            """, (order_db_id, p_id, it["requested"], it["unitPrice"]))

    conn.commit()

    # Verification queries
    cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1")
    prod_cnt = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders")
    tot_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE date(created_at) = '2026-09-09'")
    today_orders = cur.fetchone()[0]

    print(f"SUCCESS: Seeded {prod_cnt} active products, {tot_orders} total orders, {today_orders} today's orders into {DB_PATH}")
    conn.close()

if __name__ == "__main__":
    seed_db()
