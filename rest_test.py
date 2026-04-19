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


def test_get_high_for_date():
    # use random tickers so tests don't interfere with data from previous runs
    ticker = random_ticker()

    # Create a company
    r = requests.post(f"{BASE}/companies/{ticker}",
                      json={"name": "TestCorp", "sector": "Testing"})
    assert r.status_code == 201

    # Post a record
    date1 = "2023-01-01"
    stock1 = {"open": 100, "close": 110, "high": 115, "low": 95, "volume": 10000}
    r = requests.post(f"{BASE}/companies/{ticker}/records/{date1}", json=stock1)
    assert r.status_code == 201

    # Fetch just the high for that date
    r = requests.get(f"{BASE}/companies/{ticker}/records/{date1}/high")
    assert r.status_code == 200
    data = r.json()
    assert data == {"high": 115}

    # Test not found case for a date that doesn't exist
    r = requests.get(f"{BASE}/companies/{ticker}/records/2023-01-02/high")
    assert r.status_code == 404

    # Post again to one of the same dates with different values (upsert)
    stock1_updated = {"open": 101, "close": 111, "high": 116, "low": 96, "volume": 10001}
    r = requests.post(f"{BASE}/companies/{ticker}/records/{date1}", json=stock1_updated)
    assert r.status_code == 201
    data = r.json()
    assert data["date"] == date1
    for k, v in stock1_updated.items():
        assert data[k] == v

    # Assert that:
    # - There are still only 2 records
    # - The updated record has the new values
    r = requests.get(f"{BASE}/companies/{ticker}/records")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    data.sort(key=lambda x: x['date'])

    assert data[0]['date'] == date1
    for k, v in stock1_updated.items():
        assert data[0][k] == v

    assert data[1]['date'] == date2
    for k, v in stock2.items():
        assert data[1][k] == v
