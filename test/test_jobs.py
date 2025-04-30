from jobs import add_job
import pytest

def test_add_job():
    job = add_job(2000, 3000, "1745952031")
    assert isinstance(job, dict)
    assert job['min_altitude'] == 2000
    assert job['max_altitude'] == 3000
    assert job['hour'] == "1745952031"

    job = add_job(None, None, None)
    assert job is False
