#!/usr/bin/env python3
import requests
import json
import logging
from flask import Flask, jsonify, request
import redis
from hotqueue import HotQueue
import uuid
import os


redis_host = os.environ.get('REDIS_HOST', 'localhost')
log_level = os.getenv("LOG_LEVEL", "INFO")
log_attr = getattr(logging, log_level, logging.INFO)
logging.basicConfig(level=log_attr)

app = Flask(__name__)
redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
q = HotQueue("queue", host=redis_host, port=6379, db=1)
jdb = redis.Redis(host=redis_host, port=6379, db=2)
results = redis.Redis(host=redis_host, port=6379, db=3)


def _generate_jid():
    """
    Generate a pseudo-random idenatifier for a job.
    """
    return str(uuid.uuid4())

def _instantiate_job(jid, status, min_altitude, max_altitude):
    """
    Create the job object description as a python dictionary. Requires the job id,
    status, min_altitude, max_altitude parameters as well a null space for result.
    """
    return {'id': jid,
            'status': status,
            'min_altitude': min_altitude,
            'max_altitude': max_altitude,
            'result': None}

def _save_job(jid, job_dict):
    """Save a job object in the Redis database."""
    jdb.set(jid, json.dumps(job_dict))
    return

def _queue_job(jid):
    """Add a job to the redis queue."""
    q.put(jid)
    return

def add_job(min_altitude, max_altitude, status="submitted"):
    """Add a job to the redis queue."""
    if min_altitude is None:
        logging.error("Minimum Altitude is None")
        return False
    if max_altitude is None:
        logging.error("Maximum Altitude is None")
        return False
    jid = _generate_jid()
    job_dict = _instantiate_job(jid, status, min_altitude, max_altitude)
    _save_job(jid, job_dict)
    logging.info(f"Job id for created task: {jid}")
    _queue_job(jid)
    return job_dict

def get_job_by_id(jid):
    """Return job dictionary given jid"""
    return json.loads(jdb.get(jid))

def update_job_status(jid, status):
    """Update the status of job with job id `jid` to status `status`."""
    job_dict = get_job_by_id(jid)
    if job_dict:
        job_dict['status'] = status
        _save_job(jid, job_dict)
    else:
        raise Exception()

