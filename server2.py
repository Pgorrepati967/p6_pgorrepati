import os, sys
import time
import traceback
from flask import Flask, request, jsonify
from datetime import datetime
from cassandra.cluster import Cluster

app = Flask(__name__)

project = os.environ.get("PROJECT", "p6")
nodes = [f"{project}-cassandra-1", f"{project}-cassandra-2", f"{project}-cassandra-3"]
session = None


# -------------------------
# GLOBAL ERROR HANDLER
# -------------------------
@app.errorhandler(Exception)
def handle_exception(e):
    traceback.print_exc()
    return jsonify({
        "error": str(e),
        "type": type(e).__name__
    }), 500


# -------------------------
# helpers
# -------------------------
def cassandra_to_date(cass_date):
    """Convert Cassandra Date -> Python date"""
    if cass_date is None:
        return None
    return cass_date.date()


def is_valid_row(r):
    return (
        getattr(r, "date", None) is not None
        and getattr(r, "high", None) is not None
        and getattr(r, "low", None) is not None
    )


def extract_metadata(rows):
    name = None
    sector = None
    for r in rows:
        if getattr(r, "name", None):
            name = r.name
        if getattr(r, "sector", None):
            sector = r.sector
        if name and sector:
            break
    return name, sector


# -------------------------
# POST company
# -------------------------
@app.route("/<db>/api/companies/<ticker>", methods=["POST"])
def add_company(db, ticker):
    data = request.get_json()
    if not data or "name" not in data or "sector" not in data:
        return jsonify({"error": "Missing name or sector"}), 400

    session.set_keyspace(db)

    # Use a fixed dummy date for static columns
    dummy_date = datetime(1900, 1, 1).date()

    session.execute(
        "INSERT INTO stocks (ticker, date, name, sector) VALUES (%s, %s, %s, %s)",
        (ticker, dummy_date, data["name"], data["sector"])
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

    name, sector = extract_metadata(rows)
    valid_rows = [r for r in rows if is_valid_row(r)]

    if not valid_rows:
        return jsonify({"error": "not found"}), 404

    results = []
    for r in valid_rows:
        d = cassandra_to_date(r.date)
        results.append({
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "date": str(d),
            "high": r.high,
            "low": r.low
        })

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

    if not row or not is_valid_row(row):
        return jsonify({"error": "not found"}), 404

    d = cassandra_to_date(row.date)

    return jsonify({
        "ticker": ticker,
        "name": getattr(row, "name", None),
        "sector": getattr(row, "sector", None),
        "date": str(d),
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

    name, sector = extract_metadata(rows)
    valid_rows = [r for r in rows if is_valid_row(r)]

    results = []
    for r in valid_rows:
        d = cassandra_to_date(r.date)
        if d and start <= d <= end:
            results.append({
                "ticker": ticker,
                "name": name,
                "sector": sector,
                "date": str(d),
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

    valid_rows = [r for r in rows if is_valid_row(r)]

    if not valid_rows:
        return jsonify({"error": "not found"}), 404

    monthly = {}

    for r in valid_rows:
        d = cassandra_to_date(r.date)
        if not d:
            continue

        key = d.strftime("%Y-%m")

        if key not in monthly:
            monthly[key] = {"sum": 0.0, "count": 0}

        monthly[key]["sum"] += r.high
        monthly[key]["count"] += 1

    result = []
    for k in sorted(monthly.keys()):
        avg = round(monthly[k]["sum"] / monthly[k]["count"], 4)
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
