import requests
import random
import string

BASE = "http://localhost:5000/test/api"

def random_ticker():
    return "".join(random.choices(string.ascii_uppercase, k=8))

def test_add_and_get_company():
    # use random tickers so tests don't interfere with data from previous runs
    ticker = random_ticker()

    # Create a company
    r = requests.post(f"{BASE}/companies/{ticker}",
                      json={"name": "MegaCorp", "sector": "Everything"})
    assert r.status_code == 201
    data = r.json()
    assert data["ticker"] == ticker
    assert data["name"] == "MegaCorp"
    assert data["sector"] == "Everything"

    # Update the same company (upsert)
    r = requests.post(f"{BASE}/companies/{ticker}",
                      json={"name": "Mega Corp", "sector": "All The Things"})
    assert r.status_code == 201
    data = r.json()
    assert data["ticker"] == ticker
    assert data["name"] == "Mega Corp"
    assert data["sector"] == "All The Things"


def test_add_and_get_records():
    # use random tickers so tests don't interfere with data from previous runs
    ticker = random_ticker()

    # Create a company
    company_name = "TestCorp"
    company_sector = "Testing"
    r = requests.post(f"{BASE}/companies/{ticker}",
                      json={"name": company_name, "sector": company_sector})
    assert r.status_code == 201

    # Post 2 different dates with different values
    date1 = "2023-01-01"
    stock1 = {"high": 115, "low": 95}
    r = requests.post(f"{BASE}/companies/{ticker}/records/{date1}", json=stock1)
    assert r.status_code == 201
    data = r.json()
    assert data["ticker"] == ticker
    assert data["date"] == date1

    date2 = "2023-01-02"
    stock2 = {"high": 125, "low": 105}
    r = requests.post(f"{BASE}/companies/{ticker}/records/{date2}", json=stock2)
    assert r.status_code == 201
    data = r.json()
    assert data["ticker"] == ticker
    assert data["date"] == date2

    # Fetch all records and assert both exist
    r = requests.get(f"{BASE}/companies/{ticker}/records")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    data.sort(key=lambda x: x['date'])

    assert data[0]['date'] == date1
    assert data[0]['ticker'] == ticker
    assert data[0]['name'] == company_name
    assert data[0]['sector'] == company_sector
    assert data[0]['high'] == stock1['high']
    assert data[0]['low'] == stock1['low']

    assert data[1]['date'] == date2
    assert data[1]['ticker'] == ticker
    assert data[1]['name'] == company_name
    assert data[1]['sector'] == company_sector
    assert data[1]['high'] == stock2['high']
    assert data[1]['low'] == stock2['low']

    # Post again to one of the same dates with different values (upsert)
    stock1_updated = {"high": 116, "low": 96}
    r = requests.post(f"{BASE}/companies/{ticker}/records/{date1}", json=stock1_updated)
    assert r.status_code == 201
    data = r.json()
    assert data["ticker"] == ticker
    assert data["date"] == date1

    # Assert that:
    # - There are still only 2 records
    # - The updated record has the new values
    r = requests.get(f"{BASE}/companies/{ticker}/records")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    data.sort(key=lambda x: x['date'])

    assert data[0]['date'] == date1
    assert data[0]['high'] == stock1_updated['high']
    assert data[0]['low'] == stock1_updated['low']

    assert data[1]['date'] == date2
    assert data[1]['high'] == stock2['high']
    assert data[1]['low'] == stock2['low']


def test_get_record_for_date():
    # use random tickers so tests don't interfere with data from previous runs
    ticker = random_ticker()

    # Create a company
    company_name = "TestCorp"
    company_sector = "Testing"
    r = requests.post(f"{BASE}/companies/{ticker}",
                      json={"name": company_name, "sector": company_sector})
    assert r.status_code == 201

    # Insert a record
    date1 = "2023-01-01"
    stock1 = {"high": 115, "low": 95}
    r = requests.post(f"{BASE}/companies/{ticker}/records/{date1}", json=stock1)
    assert r.status_code == 201

    # Fetch that specific date
    r = requests.get(f"{BASE}/companies/{ticker}/records/{date1}")
    assert r.status_code == 200
    data = r.json()

    # Assert the date, high, and low values are correct
    assert data['ticker'] == ticker
    assert data['name'] == company_name
    assert data['sector'] == company_sector
    assert data['date'] == date1
    assert data['high'] == stock1['high']
    assert data['low'] == stock1['low']

    # Test not found case for a date that doesn't exist
    r = requests.get(f"{BASE}/companies/{ticker}/records/2023-01-02")
    assert r.status_code == 404


def test_get_records_for_range():
    # use random tickers so tests don't interfere with data from previous runs
    ticker = random_ticker()

    # Create a company
    company_name = "RangeCorp"
    company_sector = "Ranges"
    r = requests.post(f"{BASE}/companies/{ticker}",
                      json={"name": company_name, "sector": company_sector})
    assert r.status_code == 201

    # Insert at least 3 dates across different ranges
    dates = ["2023-01-10", "2023-01-20", "2023-01-30"]
    stocks = [
        {"high": 100, "low": 90},
        {"high": 110, "low": 100},
        {"high": 120, "low": 110},
    ]

    for date, stock in zip(dates, stocks):
        r = requests.post(f"{BASE}/companies/{ticker}/records/{date}", json=stock)
        assert r.status_code == 201

    # Query a specific date range and assert only the correct subset is returned
    start = "2023-01-15"
    end = "2023-01-25"
    r = requests.get(f"{BASE}/companies/{ticker}/records/range?start={start}&end={end}")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]['date'] == dates[1]
    assert data[0]['high'] == stocks[1]['high']
    assert data[0]['low'] == stocks[1]['low']

    # Query a range that includes all records
    start = "2023-01-01"
    end = "2023-01-31"
    r = requests.get(f"{BASE}/companies/{ticker}/records/range?start={start}&end={end}")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert data[0]['date'] == dates[0]
    assert data[1]['date'] == dates[1]
    assert data[2]['date'] == dates[2]

    # Query a range with no results
    start = "2023-02-01"
    end = "2023-02-28"
    r = requests.get(f"{BASE}/companies/{ticker}/records/range?start={start}&end={end}")
    assert r.status_code == 404

    # Test missing query params
    r = requests.get(f"{BASE}/companies/{ticker}/records/range?start=2023-01-01")
    assert r.status_code == 400
    r = requests.get(f"{BASE}/companies/{ticker}/records/range?end=2023-01-31")
    assert r.status_code == 400


def test_get_records_for_range_inclusive_boundaries():
    # use random tickers so tests don't interfere with data from previous runs
    ticker = random_ticker()

    # Create a company
    company_name = "BoundaryCorp"
    company_sector = "Boundaries"
    r = requests.post(f"{BASE}/companies/{ticker}",
                      json={"name": company_name, "sector": company_sector})
    assert r.status_code == 201

    # Insert at least 3 dates across different ranges
    dates = ["2023-02-10", "2023-02-20", "2023-02-28"]
    stocks = [
        {"high": 100, "low": 90},
        {"high": 110, "low": 100},
        {"high": 120, "low": 110},
    ]

    for date, stock in zip(dates, stocks):
        r = requests.post(f"{BASE}/companies/{ticker}/records/{date}", json=stock)
        assert r.status_code == 201

    # Query a specific date range with inclusive boundaries
    start = "2023-02-10"
    end = "2023-02-20"
    r = requests.get(f"{BASE}/companies/{ticker}/records/range?start={start}&end={end}")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert data[0]['date'] == dates[0]
    assert data[1]['date'] == dates[1]


def test_get_monthly_records():
    # use random tickers so tests don't interfere with data from previous runs
    ticker = random_ticker()

    # Create a company
    company_name = "MonthlyCorp"
    company_sector = "Months"
    r = requests.post(f"{BASE}/companies/{ticker}",
                      json={"name": company_name, "sector": company_sector})
    assert r.status_code == 201

    # Insert multiple records in the same month and a different month
    records = [
        ("2023-01-10", {"high": 100, "low": 90}),
        ("2023-01-20", {"high": 110, "low": 100}),
        ("2023-02-05", {"high": 120, "low": 110}),
    ]

    for date, stock in records:
        r = requests.post(f"{BASE}/companies/{ticker}/records/{date}", json=stock)
        assert r.status_code == 201

    # Assert the monthly average high is computed correctly
    r = requests.get(f"{BASE}/companies/{ticker}/records/monthly")
    assert r.status_code == 200
    data = r.json()

    assert len(data) == 2

    # The endpoint returns data ordered by month
    assert data[0]['month'] == '2023-01'
    # avg_high for Jan is (100 + 110) / 2 = 105.0
    assert data[0]['avg_high'] == 105.0

    assert data[1]['month'] == '2023-02'
    # avg_high for Feb is 120 / 1 = 120.0
    assert data[1]['avg_high'] == 120.0

    # Test not found for a ticker with no records
    ticker_no_records = random_ticker()
    r = requests.post(f"{BASE}/companies/{ticker_no_records}",
                      json={"name": "NoRecordsCorp", "sector": "Empty"})
    assert r.status_code == 201
    r = requests.get(f"{BASE}/companies/{ticker_no_records}/records/monthly")
    assert r.status_code == 404
