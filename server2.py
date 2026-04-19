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
    return jsonify({"error": "not implemented"}), 501

@app.route("/<db>/api/companies/<ticker>/records/<date>", methods=["POST"])
def add_stock(db, ticker, date):
    return jsonify({"error": "not implemented"}), 501

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
