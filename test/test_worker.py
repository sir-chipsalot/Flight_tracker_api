import jobs
import time
import requests

def test_do_work():
    job_dict = jobs.add_job(2000,3000, "1745952031")
    id = job_dict["id"]
    time.sleep(10)  #wait at least 5 seconds to allow worker to complete task
    response = requests.get(f"http://127.0.0.1:5000/results/{id}")
    assert response.status_code == 200
    assert "message" not in response.json()
    assert "error" not in response.json()
