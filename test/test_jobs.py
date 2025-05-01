import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))


from jobs import add_job
import pytest
import requests

def test_add_job():
    response = requests.get("http://127.0.0.1:5000/time")
    sv = response.json()["times"][0]
    job = add_job(2000, 3000, sv)
    assert isinstance(job, dict)
    assert job['min_altitude'] == 2000
    assert job['max_altitude'] == 3000
    assert job['hour'] == sv

    job = add_job(None, None, None)
    assert job is False
