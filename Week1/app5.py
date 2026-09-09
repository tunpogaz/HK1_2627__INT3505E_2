from flask import Flask, jsonify
app = Flask(__name__)
ORDERS = {
    "ord_1": {"id": "ord_1", "status": "pending"},
    "ord_2": {"id": "ord_2", "status": "shipped"},
    "ord_3": {"id": "ord_3", "status": "delivered"}
}
@app.route("/orders/<order_id>", methods=["DELETE"])
def delete_order(order_id):
    order = ORDERS.get(order_id)
    if order is None:
        return jsonify({"error": "not found"}), 404

    if order["status"] in ("shipped", "delivered"):
        return jsonify({"error": "can not delete"}), 409

    ORDERS.pop(order_id, None)
    return "", 204

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)