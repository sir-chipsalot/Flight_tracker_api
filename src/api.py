import json
import logging
from flask import Flask, jsonify, request, send_file
import requests
import redis
from hotqueue import HotQueue
import uuid
import os
from typing import Dict, List, Union, Any

redis_host = os.environ.get('REDIS_HOST', 'localhost')
log_level = os.getenv("LOG_LEVEL", "INFO")
log_attr = getattr(logging, log_level, logging.INFO)
logging.basicConfig(level=log_attr)

app = Flask(__name__)
redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
q = HotQueue("queue", host=redis_host, port=6379, db=1, decode_responses=True)
jdb = redis.Redis(host=redis_host, port=6379, db=2, decode_responses=True)
results = redis.Redis(host=redis_host, port=6379, db=3, decode_responses=True)
times_db = redis.Redis(host=redis_host, port=6379, db=4, decode_responses=True)


fly_url = "https://opensky-network.org/api/states/all"

def get_flight_records() -> Dict[str, List]:
    """
    Retrieve all flight records from Redis.

    Returns:
        List of all flight records
    """
    try:
        logging.info("Fetching flight records from OpenSky API...")
        response = requests.get(fly_url)
        data = response.json()
        cur_time = data.get('time')

        logging.info(f"Successfully fetched flight records. Timestamp: {cur_time}")
        return data, cur_time
    except Exception as e:
        logging.error(f"Error fetching flight records: {e}")
        return []

@app.route('/data', methods=['POST'])
def load_data() -> Dict[str, str]:
    """
    Load fly gene data into Redis from the web source.

    Returns:
        Dict[str, str]
    """
    try:
        logging.info("Starting to load flight data...")
        data, cur_time = get_flight_records()
        if not data or cur_time is None:
            logging.warning("No data or timestamp retrieved from OpenSky API.")
            return jsonify({'error': 'Failed to retrieve flight data from OpenSky.'}), 500

        states = data.get("states")
        logging.info("sucessfully got states")
        if not states:
            logging.warning("No flight states found in fetched data.")
            return jsonify({'error': 'No flgght states found in the fetched data.'}), 500

        times_db.sadd("times_set", cur_time)
        logging.info(f"Saved timestamp {cur_time} into Redis times_set.")
        flight_list = []
        for state in states:
            try:
                icao24 = state[0]
                origin_country = state[2]
                velocity = float(state[9] or 0)
                timestamp = cur_time

                flight_key = f"flight:{icao24}:{timestamp}"

                flight_data = {
                    "icao24": icao24,
                    "callsign": state[1] or None,
                    "origin_country": origin_country,
                    "time_position": state[3],
                    "last_contact": state[4],
                    "longitude": state[5],
                    "latitude": state[6],
                    "baro_altitude": state[7],
                    "on_ground": state[8],
                    "velocity": velocity,
                    "true_track": state[10],
                    "vertical_rate": state[11],
                    "sensors": state[12],
                    "geo_altitude": state[13],
                    "squawk": state[14],
                    "spi": state[15],
                    "position_source": state[16],
                    "timestamp": timestamp
                }

                flight_list.append(flight_data)
                redis_client.set(flight_key, json.dumps(flight_data))

                logging.debug(f"Stored flight {icao24} at {timestamp} in Redis.")

            except Exception as e:
                logging.error(f"Error processing flight data for ICAO24 {state[0]}: {e}")
                continue

        logging.info(f"Successfully stored {len(flight_list)} flights.")

        redis_client.set(str(cur_time), json.dumps(flight_list))
        return jsonify({
            'message': 'Flight data successfully stored.',
            'timestamp': cur_time,
            'flights stored': len(flight_list)
        })
    except Exception as e:
        logging.error(f"Error in load_data: {e}")
        return {'error': f'An unexpected error occurred: {str(e)}'}

@app.route('/flights_by_hour/<country>/<int:hour>', methods=['GET'])
def flights_by_hour(country: str, hour: int):
    """
    Get the number of flights from a specific country during a specific hour.
    
    Args:
        country (str): The country name (origin_country).
        hour (int): The Unix timestamp (start of the hour in UTC).
    
    Example call:
        /flights_by_hour/United States/1745952031
    """

    count = 0
    data = json.loads(redis_client.get(str(hour)))
    logging.info(f"This is how the data looks: {data}")
    if not data:
        return jsonify ({'error': 'The given time does not exist in the database, check the /time method to find all the times'})

    for i in range (len(data)):
        if (data[i].get("origin_country") == country):
            count+=1

    return jsonify ({'message': 'all the data has been counted',
                    f'total number of flights that left from {country}': count})

@app.route('/time', methods=['GET'])
def get_list_of_times():
    data = list(times_db.smembers("times_set"))
    return jsonify({'message': 'The ese are the list of times you can choose from',
           'times': data})

@app.route('/avg_velocity_of_flight_between_times/<flight>/<time1>/<time2>', methods=['GET'])
def avg_velocity(flight: str, time1: str, time2: str):
     
    flight_key1 = f"flight:{flight}:{time1}"
    flight_key2 = f"flight:{flight}:{time2}"
    

    raw_data1 = redis_client.get(flight_key1)
    raw_data2 = redis_client.get(flight_key2)

    if raw_data1 is None or raw_data2 is None:
        logging.error(f"Missing data: {flight_key1} or {flight_key2}")
        return {"error": "One or both keys are missing in Redis"}, 404





    data1 = json.loads(redis_client.get(flight_key1))
    data2 = json.loads(redis_client.get(flight_key2))

    data1 = data1.get("velocity")
    logging.INFO(f"sucessfully gotten flight {data1}")
    data2 = data2.get("velocity")

    return (data1)

    






if __name__ == '__main__':
    logging.info("Starting Flask app...")
    app.run(host='0.0.0.0', port=5000, debug=True)

