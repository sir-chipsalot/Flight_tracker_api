from jobs import add_job
import pytest

def test_add_job():
    job = add_job(2000, 3000)
    assert isinstance(job, dict)
    assert job['min_altitude'] == 2000
    assert job['max_altitude'] == 3000

def test_fail_add_job():
    job = add_job(None, None)
    assert job is False
