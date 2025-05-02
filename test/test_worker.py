import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import jobs
import time
import requests


def test_do_work():
    response = requests.get("http://127.0.0.1:5000/time")
    sv = response.json()["times"][0]
    job_dict = jobs.add_job(2000,3000, sv)
    id = job_dict["id"]
    time.sleep(10)  #wait at least 10 seconds to allow worker to complete task
    response = requests.get(f"http://127.0.0.1:5000/results-dat/{id}")
    assert response.status_code == 200
    assert "error" not in response.json()
