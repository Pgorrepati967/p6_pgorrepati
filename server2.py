import os, sys
import time
from flask import Flask, request, jsonify
from cassandra.cluster import Cluster
from cassandra.query import ConsistencyLevel

app = Flask(__name__)

project = os.environ.get("PROJECT", "p6")
nodes = [f"{project}-cassandra-1", f"{project}-cassandra-2", f"{project}-cassandra-3"]
session = None

@app.route("/<db>/api/companies/<ticker>", methods=["POST"])
def add_company(db, ticker):
    data = request.get_json()
    if not data or "name" not in data or "sector" not in data:
        return jsonify({"error": "Missing name or sector"}), 400

    name = data["name"]
    sector = data["sector"]

    session.set_keyspace(db)

    # Using UPDATE to set static columns. This works even if no rows exist for the partition key.
    # It's an upsert for the static data.
    query = "UPDATE stocks SET name = %s, sector = %s WHERE ticker = %s"
    session.execute(query, (name, sector, ticker))

    response = {
        "ticker": ticker,
        "name": name,
        "sector": sector,
    }
    return jsonify(response), 201

@app.route("/<db>/api/companies/<ticker>/records/<date>", methods=["POST"])
def add_stock(db, ticker, date):
    data = request.get_json()
    if not data or "high" not in data or "low" not in data:
        return jsonify({"error": "Missing high or low"}), 400

    high = data["high"]
    low = data["low"]

    try:
        session.set_keyspace(db)
        query = "INSERT INTO stocks (ticker, date, high, low) VALUES (%s, %s, %s, %s)"
        session.execute(query, (ticker, date, high, low))

        response = {
            "ticker": ticker,
            "date": date,
        }
        return jsonify(response), 201
    except Exception as e:
        print(f"Error inserting stock data: {e}")
        return jsonify({"error": "Failed to insert stock record"}), 500

@app.route("/<db>/api/companies/<ticker>/records", methods=["GET"])
def get_stocks(db, ticker):
    return jsonify({"error": "not implemented"}), 501

@app.route("/<db>/api/companies/<ticker>/records/<date>", methods=["GET"])
def get_stock_date(db, ticker, date):
    return jsonify({"error": "not implemented"}), 501

@app.route("/<db>/api/companies/<ticker>/records/range", methods=["GET"])
def get_stock_range(db, ticker):
    return jsonify({"error": "not implemented"}), 501

@app.route("/<db>/api/companies/<ticker>/records/monthly", methods=["GET"])
def get_stock_monthly(db, ticker):
    return jsonify({"error": "not implemented"}), 501

if __name__ == "__main__":
    for _ in range(30):
        try:
            cluster = Cluster(nodes)
            session = cluster.connect()
            break
        except Exception as ex:
            print(ex)
            time.sleep(2)
    else:
        print("Failed to connect to Cassandra after 30 attempts")
        sys.exit(1)

    for ks in ["prod", "test"]:

        session.execute(f"""
            CREATE KEYSPACE IF NOT EXISTS {ks}
            WITH replication = {{
                'class': 'SimpleStrategy',
                'replication_factor': 3
            }}
        """)

        session.set_keyspace(ks)

        session.execute("""
            CREATE TABLE IF NOT EXISTS stocks (
                ticker TEXT,
                date DATE,
                high DOUBLE,
                low DOUBLE,

                -- STATIC columns (per partition / per ticker)
                name TEXT STATIC,
                sector TEXT STATIC,

                PRIMARY KEY ((ticker), date)
            ) WITH CLUSTERING ORDER BY (date ASC)
        """)

    app.run(host="0.0.0.0", port=5000, debug=True)
