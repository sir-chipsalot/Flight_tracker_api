import requests
import json
import pytest

def test_count_flights():
    response = requests.get("http://127.0.0.1:5000/time")
    sv = response.json()["times"][0]
    response = requests.get(f"http://127.0.0.1:5000/count_flights/{sv}")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, dict)
    assert "airborne" in data
    assert "on_ground" in data
    assert "unknown" in data

    assert isinstance(data["airborne"], int)
    assert isinstance(data["on_ground"], int)
    assert isinstance(data["unknown"], int)

def test_create_jobs():
    job = {"min_altitude": 10000, "max_altitude": 40000}
    response = requests.get("http://127.0.0.1:5000/time")
    sv = response.json()["times"][0]
    response = requests.post(f"http://127.0.0.1:5000/jobs/{sv}", json=job)
    assert response.status_code == 200
    assert response.json()["message"] == "job successfully created"

    job = {"min_altitude": 10000}
    response = requests.post(f"http://127.0.0.1:5000/jobs/{sv}", json=job)
    assert response.status_code == 400
    assert "Missing required parameters" in response.json()["error"]

def test_list_jobs():
    response = requests.get(f"http://127.0.0.1:5000/jobs")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, dict)
    assert "job ids" in data
    assert isinstance(data["job ids"], list)

def test_get_job():
    response = requests.get(f"http://127.0.0.1:5000/jobs/fake_id")
    assert response.status_code == 404
    assert "job id not found" in response.json()["error"]

    response = requests.get("http://127.0.0.1:5000/time")
    sv = response.json()["times"][0]
    job = {"min_altitude": 10000, "max_altitude": 40000}
    response = requests.post(f"http://127.0.0.1:5000/jobs/{sv}", json=job)
    ids = response.json()['id']
    response = requests.get(f"http://127.0.0.1:5000/jobs/{ids}")
    assert response.status_code == 200

def test_get_results_dat():
    response = requests.get(f"http://127.0.0.1:5000/results-dat/fake_id")
    assert response.status_code == 404
    assert "job id not found" in response.json()["error"]

    response = requests.get("http://127.0.0.1:5000/time")
    sv = response.json()["times"][0]
    job = {"min_altitude": 10000, "max_altitude": 40000}
    response = requests.post(f"http://127.0.0.1:5000/jobs/{sv}", json=job)
    ids = response.json()['id']
    response = requests.get(f"http://127.0.0.1:5000/results-dat/{ids}")
    assert response.status_code == 200

def test_get_results_img():
    response = requests.get(f"http://127.0.0.1:5000/results-img/fake_id")
    assert response.status_code == 404
    assert "job id not found" in response.json()["error"]

    response = requests.get("http://127.0.0.1:5000/time")
    sv = response.json()["times"][0]
    job = {"min_altitude": 10000, "max_altitude": 40000}
    response = requests.post(f"http://127.0.0.1:5000/jobs/{sv}", json=job)
    ids = response.json()['id']
    response = requests.get(f"http://127.0.0.1:5000/results-img/{ids}")
    assert response.status_code == 200


