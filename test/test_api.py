import requests
import json
import pytest

def test_count_flights():
    response = requests.get("http://127.0.0.1:5000/planes/count_flights/1745952031")
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
    response = requests.post(f"http://127.0.0.1:5000/jobs/1745952031", json=job)
    assert response.status_code == 200
    assert response.json()["message"] == "job successfully created"

    job = {"min_altitude": 10000}
    response = requests.post(f"http://127.0.0.1:5000/jobs/1745952031", json=job)
    assert response.status_code == 400
    assert "Missing required parameters" in response.json()["error"]

def test_list_jobs():
    response = requests.get(f"http://127.0.0.1:5000/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_get_job():
    response = requests.get(f"http://127.0.0.1:5000/jobs/fake_id")
    assert response.status_code == 404
    assert "job id not found" in response.json()["error"]

    job = {"min_altitude": 10000, "max_altitude": 40000}
    response = requests.post(f"http://127.0.0.1:5000/jobs", json=job)
    response = requests.get(f"http://127.0.0.1:5000/jobs/{response.json()['id']}")
    assert response.status_code == 200

def test_get_results_dat():
    response = requests.get(f"http://127.0.0.1:5000/results-dat/fake_id")
    assert response.status_code == 404
    assert "job id not found" in response.json()["error"]

    job = {"min_altitude": 10000, "max_altitude": 40000}
    response = requests.post(f"http://127.0.0.1:5000/jobs", json=job)
    response = requests.get(f"http://127.0.0.1:5000/results-dat/{response.json()['id']}")
    assert response.status_code == 200

def test_get_results_img():
    response = requests.get(f"http://127.0.0.1:5000/results-img/fake_id")
    assert response.status_code == 404
    assert "job id not found" in response.json()["error"]

    job = {"min_altitude": 10000, "max_altitude": 40000}
    response = requests.post(f"http://127.0.0.1:5000/jobs", json=job)
    response = requests.get(f"http://127.0.0.1:5000/results-img/{response.json()['id']}")
    assert response.status_code == 200
