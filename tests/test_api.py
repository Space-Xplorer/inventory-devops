ITEM = {"name": "Laptop", "description": "14 inch", "quantity": 5, "price": 799.5}


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_create_and_get_item(client):
    r = client.post("/items", json=ITEM)
    assert r.status_code == 201
    body = r.json()
    assert body["id"] >= 1 and body["name"] == "Laptop"
    r2 = client.get(f"/items/{body['id']}")
    assert r2.status_code == 200
    assert r2.json()["quantity"] == 5


def test_list_items(client):
    client.post("/items", json=ITEM)
    client.post("/items", json={**ITEM, "name": "Mouse"})
    r = client.get("/items")
    assert r.status_code == 200
    assert [i["name"] for i in r.json()] == ["Laptop", "Mouse"]


def test_update_item(client):
    item_id = client.post("/items", json=ITEM).json()["id"]
    r = client.put(f"/items/{item_id}", json={**ITEM, "quantity": 9})
    assert r.status_code == 200
    assert r.json()["quantity"] == 9


def test_delete_item(client):
    item_id = client.post("/items", json=ITEM).json()["id"]
    assert client.delete(f"/items/{item_id}").status_code == 204
    assert client.get(f"/items/{item_id}").status_code == 404


def test_not_found(client):
    assert client.get("/items/999").status_code == 404
    assert client.put("/items/999", json=ITEM).status_code == 404
    assert client.delete("/items/999").status_code == 404


def test_validation_rejects_negative_quantity(client):
    r = client.post("/items", json={**ITEM, "quantity": -1})
    assert r.status_code == 422


def test_metrics_endpoint(client):
    client.get("/health")
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.text
