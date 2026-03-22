from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI()

# -------------------- DATA --------------------

items = [
    {"id": 1, "name": "Tomato", "price": 30, "unit": "kg", "category": "Vegetable", "in_stock": True},
    {"id": 2, "name": "Milk", "price": 50, "unit": "litre", "category": "Dairy", "in_stock": True},
    {"id": 3, "name": "Rice", "price": 60, "unit": "kg", "category": "Grain", "in_stock": True},
    {"id": 4, "name": "Apple", "price": 120, "unit": "kg", "category": "Fruit", "in_stock": False},
    {"id": 5, "name": "Eggs", "price": 70, "unit": "dozen", "category": "Dairy", "in_stock": True},
    {"id": 6, "name": "Potato", "price": 25, "unit": "kg", "category": "Vegetable", "in_stock": True},
]

orders = []
order_counter = 1

cart = []

# -------------------- MODELS --------------------

class OrderRequest(BaseModel):
    customer_name: str = Field(..., min_length=2)
    item_id: int = Field(..., gt=0)
    quantity: int = Field(..., gt=0, le=50)
    delivery_address: str = Field(..., min_length=10)
    delivery_slot: str = "Morning"
    bulk_order: bool = False


class NewItem(BaseModel):
    name: str = Field(..., min_length=2)
    price: int = Field(..., gt=0)
    unit: str = Field(..., min_length=2)
    category: str = Field(..., min_length=2)
    in_stock: bool = True


class CheckoutRequest(BaseModel):
    customer_name: str = Field(..., min_length=2)
    delivery_address: str = Field(..., min_length=10)
    delivery_slot: str = "Morning"


# -------------------- HELPERS --------------------

def find_item(item_id):
    for item in items:
        if item["id"] == item_id:
            return item
    return None


def calculate_order_total(price, quantity, slot, bulk):
    total = price * quantity
    original = total

    if bulk and quantity >= 10:
        total *= 0.92

    if slot == "Morning":
        total += 40
    elif slot == "Evening":
        total += 60

    return original, total


# -------------------- BASIC GET --------------------

@app.get("/")
def home():
    return {"message": "Welcome to FreshMart Grocery"}


@app.get("/items")
def get_items():
    return {
        "items": items,
        "total": len(items),
        "in_stock_count": sum(1 for i in items if i["in_stock"])
    }


@app.get("/items/summary")
def summary():
    category_count = {}
    for i in items:
        category_count[i["category"]] = category_count.get(i["category"], 0) + 1

    return {
        "total": len(items),
        "in_stock": sum(1 for i in items if i["in_stock"]),
        "out_of_stock": sum(1 for i in items if not i["in_stock"]),
        "category_breakdown": category_count
    }


# -------------------- FILTER / SEARCH / SORT / PAGE --------------------

@app.get("/items/filter")
def filter_items(
    category: str = Query(None),
    max_price: int = Query(None),
    unit: str = Query(None),
    in_stock: bool = Query(None)
):
    result = items

    if category is not None:
        result = [i for i in result if i["category"] == category]

    if max_price is not None:
        result = [i for i in result if i["price"] <= max_price]

    if unit is not None:
        result = [i for i in result if i["unit"] == unit]

    if in_stock is not None:
        result = [i for i in result if i["in_stock"] == in_stock]

    return {"results": result}


@app.get("/items/search")
def search_items(keyword: str):
    result = [
        i for i in items
        if keyword.lower() in i["name"].lower() or keyword.lower() in i["category"].lower()
    ]
    return {"results": result, "total_found": len(result)}


@app.get("/items/sort")
def sort_items(sort_by: str = "price", order: str = "asc"):
    if sort_by not in ["price", "name", "category"]:
        return {"error": "Invalid sort_by"}

    reverse = True if order == "desc" else False
    sorted_items = sorted(items, key=lambda x: x[sort_by], reverse=reverse)

    return {"sorted": sorted_items}


@app.get("/items/page")
def paginate_items(page: int = 1, limit: int = 4):
    start = (page - 1) * limit
    end = start + limit
    total_pages = (len(items) + limit - 1) // limit

    return {
        "page": page,
        "total_pages": total_pages,
        "data": items[start:end]
    }


@app.get("/items/browse")
def browse(
    keyword: str = None,
    category: str = None,
    in_stock: bool = None,
    sort_by: str = "price",
    order: str = "asc",
    page: int = 1,
    limit: int = 4
):
    result = items

    if keyword:
        result = [i for i in result if keyword.lower() in i["name"].lower()]

    if category:
        result = [i for i in result if i["category"] == category]

    if in_stock is not None:
        result = [i for i in result if i["in_stock"] == in_stock]

    result = sorted(result, key=lambda x: x[sort_by], reverse=(order == "desc"))

    start = (page - 1) * limit
    end = start + limit

    return {
        "total": len(result),
        "page": page,
        "data": result[start:end]
    }

# -------------------- ITEM BY ID --------------------

@app.get("/items/{item_id}")
def get_item(item_id: int):
    item = find_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


# -------------------- CRUD --------------------

@app.post("/items", status_code=201)
def add_item(new_item: NewItem):
    for i in items:
        if i["name"].lower() == new_item.name.lower():
            raise HTTPException(status_code=400, detail="Duplicate item")

    new = new_item.dict()
    new["id"] = len(items) + 1
    items.append(new)
    return new


@app.put("/items/{item_id}")
def update_item(item_id: int, price: Optional[int] = None, in_stock: Optional[bool] = None):
    item = find_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if price is not None:
        item["price"] = price
    if in_stock is not None:
        item["in_stock"] = in_stock

    return item


@app.delete("/items/{item_id}")
def delete_item(item_id: int):
    item = find_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    for o in orders:
        if o["item_name"] == item["name"]:
            return {"error": "Item has active orders"}

    items.remove(item)
    return {"message": "Item deleted"}


# -------------------- ORDERS --------------------

@app.get("/orders")
def get_orders():
    return {"orders": orders, "total": len(orders)}


@app.post("/orders")
def create_order(order: OrderRequest):
    global order_counter

    item = find_item(order.item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")

    if not item["in_stock"]:
        return {"error": "Out of stock"}

    original, total = calculate_order_total(
        item["price"], 
        order.quantity, 
        order.delivery_slot,
        order.bulk_order
    )

    new_order = {
        "order_id": order_counter,
        "customer_name": order.customer_name,
        "item_name": item["name"],
        "quantity": order.quantity,
        "delivery_slot": order.delivery_slot,
        "original_price": original,
        "total_cost": total,
        "status": "confirmed"
    }

    orders.append(new_order)
    order_counter += 1

    return new_order


# -------------------- CART --------------------

@app.post("/cart/add")
def add_to_cart(item_id: int = Query(...), quantity: int = Query(1)):

    item = find_item(item_id)

    if not item:
        return {"error": "Item not found"}

    if not item["in_stock"]:
        return {"error": "Item out of stock"}

    # Merge logic
    for c in cart:
        if c["item_id"] == item_id:
            c["quantity"] += quantity
            return {"message": "Cart updated", "cart": cart}

    # Add new
    cart.append({
        "item_id": item_id,
        "name": item["name"],
        "price": item["price"],
        "quantity": quantity
    })

    return {"message": "Item added to cart", "cart": cart}


@app.get("/cart")
def view_cart():
    result = []
    grand_total = 0

    for item in cart:
        subtotal = item["price"] * item["quantity"]
        grand_total += subtotal

        result.append({
            "name": item["name"],
            "quantity": item["quantity"],
            "price": item["price"],   # ✅ add this
            "subtotal": subtotal
        })

    return {
        "cart_items": result,       # ✅ change key
        "grand_total": grand_total  # ✅ change key
    }


@app.delete("/cart/{item_id}")
def remove_cart(item_id: int):
    for c in cart:
        if c["item_id"] == item_id:
            cart.remove(c)
            return {"message": "Removed"}
    return {"error": "Item not in cart"}


@app.post("/cart/checkout", status_code=201)
def checkout(data: CheckoutRequest):
    global order_counter

    if not cart:
        return {"error": "Cart is empty"}

    result = []
    grand_total = 0

    for c in cart:
        item = find_item(c["item_id"])

        original, total = calculate_order_total(
            item["price"], c["quantity"], data.delivery_slot, False
        )

        order = {
            "order_id": order_counter,
            "customer_name": data.customer_name,
            "item_name": item["name"],
            "quantity": c["quantity"],
            "total_cost": total
        }

        orders.append(order)
        result.append(order)
        grand_total += total
        order_counter += 1

    cart.clear()

    return {"orders": result, "grand_total": grand_total}


# -------------------- ADVANCED ORDERS --------------------

@app.get("/orders/search")
def search_orders(customer_name: str):
    result = [o for o in orders if customer_name.lower() in o["customer_name"].lower()]
    return {"results": result}


@app.get("/orders/sort")
def sort_orders(order: str = "asc"):
    sorted_orders = sorted(orders, key=lambda x: x["total_cost"], reverse=(order == "desc"))
    return {"orders": sorted_orders}


@app.get("/orders/page")
def paginate_orders(page: int = 1, limit: int = 3):
    start = (page - 1) * limit
    end = start + limit
    return {"data": orders[start:end]}


# -------------------- COMBINED BROWSE --------------------
