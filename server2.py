import os, sys
import time
from flask import Flask, request, jsonify
from datetime import datetime
from cassandra.cluster import Cluster

app = Flask(__name__)

project = os.environ.get("PROJECT", "p6")
nodes = [f"{project}-cassandra-1", f"{project}-cassandra-2", f"{project}-cassandra-3"]
session = None

DUMMY_DATE = datetime(1900, 1, 1).date()


# -------------------------
# POST /companies
# -------------------------
@app.route("/<db>/api/companies/<ticker>", methods=["POST"])
def add_company(db, ticker):
    data = request.get_json()
    if not data or "name" not in data or "sector" not in data:
        return jsonify({"error": "Missing name or sector"}), 400

    session.set_keyspace(db)

    # Insert dummy row to create partition
    session.execute(
        "INSERT INTO stocks (ticker, date, name, sector) VALUES (%s, %s, %s, %s)",
        (ticker, DUMMY_DATE, data["name"], data["sector"])
    )

    return jsonify({
        "ticker": ticker,
        "name": data["name"],
        "sector": data["sector"]
    }), 201


# -------------------------
# POST stock record
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records/<date>", methods=["POST"])
def add_stock(db, ticker, date):
    data = request.get_json()
    if not data or "high" not in data or "low" not in data:
        return jsonify({"error": "Missing high or low"}), 400

    session.set_keyspace(db)

    date_obj = datetime.strptime(date, "%Y-%m-%d").date()

    session.execute(
        "INSERT INTO stocks (ticker, date, high, low) VALUES (%s, %s, %s, %s)",
        (ticker, date_obj, float(data["high"]), float(data["low"]))
    )

    return jsonify({"ticker": ticker, "date": date}), 201


# -------------------------
# GET all records
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records", methods=["GET"])
def get_stocks(db, ticker):
    session.set_keyspace(db)

    rows = list(session.execute(
        "SELECT * FROM stocks WHERE ticker = %s",
        (ticker,)
    ))

    if not rows:
        return jsonify({"error": "not found"}), 404

    results = []
    for r in rows:
        if (
            r.date is None
            or r.date == DUMMY_DATE
            or r.high is None
            or r.low is None
        ):
            continue

        results.append({
            "ticker": ticker,
            "name": r.name,
            "sector": r.sector,
            "date": str(r.date),
            "high": r.high,
            "low": r.low
        })

    if not results:
        return jsonify({"error": "not found"}), 404

    results.sort(key=lambda x: x["date"])
    return jsonify(results)


# -------------------------
# GET one date
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records/<date>", methods=["GET"])
def get_stock_date(db, ticker, date):
    session.set_keyspace(db)

    date_obj = datetime.strptime(date, "%Y-%m-%d").date()

    row = session.execute(
        "SELECT * FROM stocks WHERE ticker = %s AND date = %s",
        (ticker, date_obj)
    ).one()

    if (
        not row
        or row.date is None
        or row.date == DUMMY_DATE
        or row.high is None
        or row.low is None
    ):
        return jsonify({"error": "not found"}), 404

    return jsonify({
        "ticker": ticker,
        "name": row.name,
        "sector": row.sector,
        "date": str(row.date),
        "high": row.high,
        "low": row.low
    })


# -------------------------
# GET range
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records/range", methods=["GET"])
def get_stock_range(db, ticker):
    start = request.args.get("start")
    end = request.args.get("end")

    if not start or not end:
        return jsonify({"error": "Missing params"}), 400

    start = datetime.strptime(start, "%Y-%m-%d").date()
    end = datetime.strptime(end, "%Y-%m-%d").date()

    session.set_keyspace(db)

    rows = list(session.execute(
        "SELECT * FROM stocks WHERE ticker = %s",
        (ticker,)
    ))

    if not rows:
        return jsonify({"error": "not found"}), 404

    name = None
    sector = None
    results = []

    for r in rows:
        # capture static columns safely
        if r.name:
            name = r.name
        if r.sector:
            sector = r.sector

        if (
            r.date is None
            or r.date == DUMMY_DATE
            or r.high is None
            or r.low is None
        ):
            continue

        if start <= r.date <= end:
            results.append({
                "ticker": ticker,
                "name": name,
                "sector": sector,
                "date": str(r.date),
                "high": r.high,
                "low": r.low
            })

    if not results:
        return jsonify({"error": "not found"}), 404

    results.sort(key=lambda x: x["date"])
    return jsonify(results)
# -------------------------
# GET monthly averages
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records/monthly", methods=["GET"])
def get_stock_monthly(db, ticker):
    session.set_keyspace(db)

    rows = list(session.execute(
        "SELECT * FROM stocks WHERE ticker = %s",
        (ticker,)
    ))

    monthly = {}

    for r in rows:
        if (
            r.date is None
            or r.date == DUMMY_DATE
            or r.high is None
        ):
            continue

        key = r.date.strftime("%Y-%m")

        if key not in monthly:
            monthly[key] = {"sum": 0, "count": 0}

        monthly[key]["sum"] += r.high
        monthly[key]["count"] += 1

    if not monthly:
        return jsonify({"error": "not found"}), 404

    result = []
    for k in sorted(monthly.keys()):
        avg = monthly[k]["sum"] / monthly[k]["count"]
        result.append({
            "month": k,
            "avg_high": avg
        })

    return jsonify(result)


# -------------------------
# INIT
# -------------------------
if __name__ == "__main__":
    for _ in range(30):
        try:
            cluster = Cluster(nodes)
            session = cluster.connect()
            break
        except Exception:
            time.sleep(2)
    else:
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
                name TEXT STATIC,
                sector TEXT STATIC,
                PRIMARY KEY ((ticker), date)
            ) WITH CLUSTERING ORDER BY (date ASC)
        """)

    app.run(host="0.0.0.0", port=5000, debug=True)
