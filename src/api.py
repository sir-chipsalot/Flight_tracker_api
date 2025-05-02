import json
import logging
from flask import Flask, jsonify, request, send_file
import requests
import redis
from hotqueue import HotQueue
import uuid
import os
from typing import Dict, List, Union, Any
from jobs import add_job

redis_host = os.environ.get('REDIS_HOST', 'localhost')
log_level = os.getenv("LOG_LEVEL", "INFO")
log_attr = getattr(logging, log_level, logging.INFO)
logging.basicConfig(level=log_attr)

app = Flask(__name__)
redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
q = HotQueue("queue", host=redis_host, port=6379, db=1, decode_responses=True)
jdb = redis.Redis(host=redis_host, port=6379, db=2, decode_responses=True)
results = redis.Redis(host=redis_host, port=6379, db=3, decode_responses=False)
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
            return jsonify({'error': 'No flight states found in the fetched data.'}), 500

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

@app.route('/data/<int:hour>', methods = ['DELETE'])
def delete_data(hour: int) -> json:
    """
    Deletes all data under the specified hour
    :return: message saying whether was successful or not
    """
    data = redis_client.get(str(hour))
    if not data:
        logging.error("Failed to get data")
        return jsonify({"error": "Failed to get data"}), 400

    redis_client.delete(str(hour))
    times_db.srem("times_set", str(hour))
    return jsonify({"message": f"deleted data at time {hour} from Redis"}), 200


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
        return jsonify(
            {'error': 'The given time does not exist in the database, check the /time method to find all the times'})

    for i in range(len(data)):
        if (data[i].get("origin_country") == country):
            count += 1

    return jsonify({'message': 'all the data has been counted',
                    f'total number of flights that left from {country}': count})


@app.route('/time', methods=['GET'])
def get_list_of_times():
    """
    gets all timestamps that the redis container has
    Returns: json of message of result and list of times
    """

    data = list(times_db.smembers("times_set"))
    return jsonify({'message': 'These are the list of times you can choose from',
                    'times': data})



@app.route('/flights_at_time/<time>', methods=['GET'])
def get_flights_at_time(time: str):
    """
    Get all flight ICAO24 codes for a specific timestamp.
    
    Args:
        time (str): The Unix timestamp (start of the hour in UTC).
    
    Returns:
        JSON response with either:
        - List of ICAO24 codes at the given time
        - Error message if time doesn't exist
    """
    # Check if timestamp exists
    if not times_db.sismember("times_set", time):
        return jsonify({
            "error": f"Timestamp {time} not found",
            "available_times": list(times_db.smembers("times_set"))
        }), 404

    # Get flight data
    flights_data = redis_client.get(time)
    if not flights_data:
        return jsonify({"error": f"No flight data found for timestamp {time}"}), 404

    try:
        flights_list = json.loads(flights_data)
        icao_list = [flight.get("icao24") for flight in flights_list if flight.get("icao24")]
        
        return jsonify({
            "timestamp": time,
            "icao24_codes": icao_list
        })
        
    except json.JSONDecodeError:
        return jsonify({"error": "Invalid flight data format"}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500




@app.route('/avg_velocity/<flight>/<time1>/<time2>', methods=['GET'])
def avg_velocity(flight: str, time1: str, time2: str):
    """
    Compute the average velocity of a flight between two timestamps.
    :param flight: icao24 flight name
    :param time1: starting timestamp
    :param time2: ending timestamp
    :return: avg_velocity of flight between times or error message
    """
    # First check if the timestamps exist in our database
    if not times_db.sismember("times_set", time1):
        logging.error(f"Timestamp {time1} not found in database")
        return jsonify({"error": f"Timestamp {time1} not found in database"}), 404

    if not times_db.sismember("times_set", time2):
        logging.error(f"Timestamp {time2} not found in database")
        return jsonify({"error": f"Timestamp {time2} not found in database"}), 404

    flight_key1 = f"flight:{flight}:{time1}"
    flight_key2 = f"flight:{flight}:{time2}"

    raw_data1 = redis_client.get(flight_key1)
    raw_data2 = redis_client.get(flight_key2)

    if raw_data1 is None:
        logging.error(f"Flight {flight} not found at timestamp {time1}")
        return jsonify({"error": f"Flight {flight} not found at timestamp {time1}"}), 404

    if raw_data2 is None:
        logging.error(f"Flight {flight} not found at timestamp {time2}")
        return jsonify({"error": f"Flight {flight} not found at timestamp {time2}"}), 404

    try:
        data1 = json.loads(raw_data1)
        data2 = json.loads(raw_data2)

        velocity1 = data1.get("velocity")
        velocity2 = data2.get("velocity")

        if velocity1 is None or velocity2 is None:
            logging.error("Velocity data missing for one or both timestamps")
            return jsonify({"error": "Velocity data missing for one or both timestamps"}), 400

        avg_v = (float(velocity1) + float(velocity2)) / 2
        logging.info(f"Successfully calculated average velocity: {avg_v}")

        return jsonify({
            "flight": flight,
            "time1": time1,
            "time2": time2,
            "average_velocity": avg_v,
            "units": "m/s"
        })

    except (ValueError, TypeError) as e:
        logging.error(f"Error processing velocity data: {e}")
        return jsonify({"error": "Invalid velocity data format"}), 400
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return jsonify({"error": "An unexpected error occurred"}), 500

@app.route('/count_flights/<int:hour>', methods=['GET'])
def count_flights(hour: int):
    """
    Determines the number of planes in flight, on ground, and unknown at the given hour
    :param hour: The Unix timestamp (start of the hour in UTC).
    :return: Number of planes in flight, on ground, and unknown at the given hour.
    """

    airborne = 0
    on_ground = 0
    unknown = 0
    data = json.loads(redis_client.get(str(hour)))
    if not data:
        return jsonify(
            {'error': 'The given time does not exist in the database, check the /time method to find all the times'})

    for plane in data:
        if 'on_ground' in plane:
            if plane['on_ground']:
                on_ground += 1
            else:
                airborne += 1
        else:
            unknown += 1

    return jsonify({"airborne": airborne, "on_ground": on_ground, 'unknown': unknown}), 200


@app.route('/jobs/<int:hour>', methods=['POST'])
def create_job(hour: int) -> json:
    """
    Creates a job with altitude range information (min_altitude, max_altitude) to be processed
    :return: Json string stating if request was successful or not
    """
    request_data = request.get_json()
    if not request_data or "min_altitude" not in request_data or "max_altitude" not in request_data:
        return jsonify({
            "error": "Missing required parameters: min_altitude and max_altitude"
        }), 400

    job_dict = add_job(request_data["min_altitude"], request_data["max_altitude"], hour)

    logging.info(str(job_dict))
    return jsonify({"message": "job successfully created", "id": job_dict["id"]}), 200  ###CHANGED?


@app.route('/jobs', methods=['GET'])
def list_jobs() -> json:
    """
    Returns a list of all job ids
    :return: list of all job ids in json format
    """
    id = []
    count = 0
    for key in jdb.keys():
        count += 1
        data = jdb.get(key)
        if data:
            data2 = json.loads(data)
            id.append(data2.get("id"))

    logging.info(f"Number of jobs: {str(count)}")
    return jsonify({"job ids": id}), 200


@app.route('/jobs/<jobid>', methods=['GET'])
def get_job(jobid: str) -> json:
    """
    Returns job information for a specific job given their id
    :param jobid: The id of the job that user wants information about
    :return: The information of a specific job in json format
    """
    job = jdb.get(jobid)
    if not job:
        return jsonify({"error": "job id not found"}), 404
    return jsonify(json.loads(job)), 200


@app.route('/results-dat/<jobid>', methods=['GET'])
def get_results_dat(jobid: str) -> json:
    """
    Returns the list of planes by icao24 id that are between a certain altitude range
    :param jobid: The id of the job that user wants information about
    :return: returns the dictionary of the list of planes by icao24 id that are between a certain longitude and latitude.
    """
    job = jdb.get(jobid)
    if not job:
        logging.error("job id not found")
        return jsonify({"error": "job id not found"}), 404
    job = json.loads(job)
    if job['status'] == "submitted":
        return jsonify({"message": "job not processed yet"}), 200
    elif job["status"] == "in progress":
        return jsonify({"message": "job in processing"}), 200
    elif job["status"] == "complete":
        return jsonify(json.loads(results.hget(jobid, 'data'))), 200
    else:
        return jsonify({"error": "job status not found"}), 404


@app.route('/results-img/<jobid>', methods=['GET'])
def get_results_image(jobid):
    """
    Returns the generated image of planes between a specified altitude range
    :param jobid: The id of the job that user wants information about
    :return: returns the image file corresponding to the requested job or a message about the job's status.
    """
    job = jdb.get(jobid)
    if not job:
        logging.error("job id not found")
        return jsonify({"error": "job id not found"}), 404
    job = json.loads(job)
    if job['status'] == "submitted":
        return jsonify({"message": "job not processed yet"}), 200
    elif job["status"] == "in progress":
        return jsonify({"message": "job in processing"}), 200
    elif job["status"] == "complete":
        image_data = results.hget(jobid, 'image')
        if image_data is None:
            return jsonify({"error": "image not found"}), 404

        path = f'/app/{jobid}.png'
        with open(path, 'wb') as f:
            f.write(image_data)
        return send_file(path, mimetype='image/png')
    else:
        return jsonify({"error": "job status not found"}), 404

@app.route('/help', methods=['GET'])
def help():
    """
    Provides documentation for all available API endpoints.
    Returns:
        JSON with all endpoints and their descriptions
    """
    endpoints = {
        'POST /data': 'Load flight data from OpenSky API into Redis',
        'DELETE /data/<hour>': 'Delete all flight data for a specific hour',
        'GET /flights_by_hour/<country>/<hour>': 'Get the number of flights from a specific country during a specific hour',
        'GET /time': 'Get all available timestamps in the database',
        'GET /avg_velocity/<flight>/<time1>/<time2>': 'Compute average velocity of a flight between two timestamps',
        'GET /count_flights/<hour>': 'Count flights by status (airborne, on ground, unknown) for a specific hour',
<<<<<<< HEAD
        'POST /jobs/<hour>': '''Create a job to find flights within an altitude range for a specific hour (requires min_altitude and max_altitude in JSON body) example comand: curl -X POST http://127.0.0.1:5000/jobs/<hour> -H "Content-Type: application/json" -d '{"min_altitude":10000, "max_altitude":12000}' ''',
=======
        'POST /jobs/<hour>': '''Create a job to find flights within an altitude range for a specific hour (requires min_altitude and max_altitude in JSON body)
        example comand: curl -X POST http://127.0.0.1:5000/jobs/<hour> -H "Content-Type: application/json" -d '{"min_altitude":10000, "max_altitude":12000}' ''',
>>>>>>> 6f65fad84d6f02bbe0e9dfaba9d5d43c4a28013e
        'GET /jobs': 'List all job IDs',
        'GET /jobs/<jobid>': 'Get information about a specific job',
        'GET /results-dat/<jobid>': 'Get results data for a completed job (list of flights in altitude range)',
        'GET /results-img/<jobid>': 'Get results image for a completed job (visualization of flights in altitude range)',
        'GET /flights_at_time/<time>': 'Get all the flights at a specific time',
        'GET /help': 'This help message - lists all available endpoints',
    }
    return jsonify(endpoints)

if __name__ == '__main__':
    logging.info("Starting Flask app...")
    app.run(host='0.0.0.0', port=5000, debug=True)
