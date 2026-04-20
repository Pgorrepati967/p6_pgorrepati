import os, sys
import time
import traceback
from flask import Flask, request, jsonify
from datetime import datetime
from cassandra.cluster import Cluster
from cassandra import ConsistencyLevel

app = Flask(__name__)

project = os.environ.get("PROJECT", "p6")
nodes = [
    f"{project}-cassandra-1",
    f"{project}-cassandra-2",
    f"{project}-cassandra-3"
]

session = None


# -------------------------
# ERROR HANDLER
# -------------------------
@app.errorhandler(Exception)
def handle_exception(e):
    traceback.print_exc()
    return jsonify({
        "error": str(e),
        "type": type(e).__name__
    }), 500


# -------------------------
# HELPERS
# -------------------------
def to_pydate(cass_date):
    """Convert Cassandra DATE -> Python date safely"""
    if cass_date is None:
        return None
    return cass_date.date()


def is_stock_row(r):
    """Valid stock record (exclude static-only dummy row)"""
    d = to_pydate(r.date)
    return (
        d is not None and d.year != 1900
        and r.high is not None
        and r.low is not None
    )


def extract_meta(rows):
    name, sector = None, None
    for r in rows:
        if getattr(r, "name", None):
            name = r.name
        if getattr(r, "sector", None):
            sector = r.sector
    return name, sector


# -------------------------
# CREATE COMPANY
# -------------------------
@app.route("/<db>/api/companies/<ticker>", methods=["POST"])
def create_company(db, ticker):
    data = request.get_json()
    if not data or "name" not in data or "sector" not in data:
        return jsonify({"error": "Missing name or sector"}), 400

    session.set_keyspace(db)

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
# ADD STOCK RECORD
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records/<date>", methods=["POST"])
def add_record(db, ticker, date):
    data = request.get_json()
    if not data or "high" not in data or "low" not in data:
        return jsonify({"error": "Missing high or low"}), 400

    session.set_keyspace(db)

    d = datetime.strptime(date, "%Y-%m-%d").date()

    session.execute(
        "INSERT INTO stocks (ticker, date, high, low) VALUES (%s, %s, %s, %s)",
        (ticker, d, float(data["high"]), float(data["low"]))
    )

    return jsonify({"ticker": ticker, "date": date}), 201


# -------------------------
# GET ALL RECORDS
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records", methods=["GET"])
def get_records(db, ticker):
    session.set_keyspace(db)

    rows = list(session.execute(
        "SELECT * FROM stocks WHERE ticker = %s",
        (ticker,)
    ))

    if not rows:
        return jsonify({"error": "not found"}), 404

    name, sector = extract_meta(rows)
    valid = [r for r in rows if is_stock_row(r)]

    results = []
    for r in valid:
        results.append({
            "ticker": ticker,
            "name": name,
            "sector": sector,
            "date": str(to_pydate(r.date)),
            "high": r.high,
            "low": r.low
        })

    results.sort(key=lambda x: x["date"])
    return jsonify(results)


# -------------------------
# GET SINGLE DATE
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records/<date>", methods=["GET"])
def get_one(db, ticker, date):
    session.set_keyspace(db)

    d = datetime.strptime(date, "%Y-%m-%d").date()

    row = session.execute(
        "SELECT * FROM stocks WHERE ticker = %s AND date = %s",
        (ticker, d)
    ).one()

    if not row or not is_stock_row(row):
        return jsonify({"error": "not found"}), 404

    return jsonify({
        "ticker": ticker,
        "name": getattr(row, "name", None),
        "sector": getattr(row, "sector", None),
        "date": str(to_pydate(row.date)),
        "high": row.high,
        "low": row.low
    })


# -------------------------
# GET RANGE
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records/range", methods=["GET"])
def get_range(db, ticker):
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

    name, sector = extract_meta(rows)

    results = []
    for r in rows:
        if not is_stock_row(r):
            continue

        d = to_pydate(r.date)

        if start <= d <= end:
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
# GET MONTHLY AVERAGES
# -------------------------
@app.route("/<db>/api/companies/<ticker>/records/monthly", methods=["GET"])
def get_monthly(db, ticker):
    session.set_keyspace(db)

    rows = list(session.execute(
        "SELECT * FROM stocks WHERE ticker = %s",
        (ticker,)
    ))

    monthly = {}

    for r in rows:
        if not is_stock_row(r):
            continue

        d = to_pydate(r.date)
        key = d.strftime("%Y-%m")

        if key not in monthly:
            monthly[key] = {"sum": 0.0, "count": 0}

        monthly[key]["sum"] += r.high
        monthly[key]["count"] += 1

    if not monthly:
        return jsonify({"error": "not found"}), 404

    result = [
        {
            "month": k,
            "avg_high": round(v["sum"] / v["count"], 4)
        }
        for k, v in sorted(monthly.items())
    ]

    return jsonify(result)


# -------------------------
# MAIN
# -------------------------
if __name__ == "__main__":
    for _ in range(30):
        try:
            cluster = Cluster(nodes)
            session = cluster.connect()

            session.default_consistency_level = ConsistencyLevel.TWO

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
