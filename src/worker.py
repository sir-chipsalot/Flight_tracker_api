from hotqueue import HotQueue
import time
import json
import logging
import redis
import os
import matplotlib.pyplot as plt
import cartopy.crs as ccrs

redis_host = os.environ.get('REDIS_HOST', 'localhost')
log_level = os.getenv("LOG_LEVEL", "INFO")
log_attr = getattr(logging, log_level, logging.INFO)
logging.basicConfig(level=log_attr)
redis_client = redis.Redis(host=redis_host, port=6379, db=0)

attempt = 1
while attempt <= 100:
    try:
        r = redis.Redis(host=redis_host, port=6379, db=0)
        r.ping()
        logging.info("Connected")
        break
    except redis.exceptions.ConnectionError:
        logging.warning(f"Failed to connect. Attempt {attempt}")
        attempt += 1
        time.sleep(2)

q = HotQueue('queue', host=redis_host, port=6379, db=1)
logging.info("Created queue")
jdb = redis.Redis(host=redis_host, port=6379, db=2)
results = redis.Redis(host=redis_host, port=6379, db=3, decode_responses=True)
logging.info("Created redis container for jobs and results")


def plot_data(lat: list, lon: list, alt: list, min_alt: float, max_alt: float, output_path : str):
    """
    Plots the positions of planes on a world map colored by altitude and saves the plot as an image.
    :param lat: latitudes of the planes
    :param lon: longitudes of the planes
    :param alt: altitudes of the planes
    :param min_alt: minimum altitude
    :param max_alt: maximum altitude
    :param output_path: path to save the generated plot image
    :return: None. Saves the plot image to the specified path
    """

    fig = plt.figure(figsize=(14, 8))
    ax = plt.axes(projection=ccrs.PlateCarree())
    ax.stock_img()
    ax.coastlines()

    sc = plt.scatter(lat, lon, c=alt, cmap='inferno', s=10, transform=ccrs.PlateCarree())
    plt.colorbar(sc, label='Altitude (meters)')
    plt.title(f'Planes between {min_alt} meters and {max_alt} meters')
    plt.savefig(output_path)


@q.worker
def do_work(jobid):
    """
    gets id of jobs which contains information about min_altitude and max_altitude
    Finds all planes that are flying between the requested altitudes
    Creates a plot of the locations of the planes and colormap based on their altitude
    Stores the icao24 id of all planes to be returned and stored along with the plot
    :param jobid: id of the job to process
    :return: updates status of job and if successful stores the specific id of the planes as well as the plot of the data
    """
    if jobid is None:
        logging.error("no job id found")
    else:
        logging.info(f"Processing job: {jobid}")
        job_info = jdb.get(jobid)
        if job_info is None:
            logging.error("no job id found")
        else:
            job = json.loads(job_info)
            job['status'] = 'in progress'
            jdb.set(jobid, json.dumps(job))

            min_altitude = job["min_altitude"]
            max_altitude = job["max_altitude"]
            hour = job["hour"]
            if min_altitude is None or max_altitude is None or hour is None:
                logging.error("Failed to get min and max altitude")
                job['status'] = 'failed'
                jdb.set(jobid, json.dumps(job))
            else:

                data = redis_client.get(str(hour))
                if not data:
                    logging.error("no data found")
                    job['status'] = 'failed'
                    jdb.set(jobid, json.dumps(job))
                else:
                    long = []
                    lat = []
                    alt = []
                    dataset = []
                    for plane in json.loads(data):
                        if "longitude" in plane:
                            if plane["geo_altitude"] and plane["latitude"] and plane["longitude"] and min_altitude <= plane["geo_altitude"] <= max_altitude:
                                lat.append(plane.get("latitude"))
                                long.append(plane.get("longitude"))
                                alt.append(plane["geo_altitude"])
                                if plane["icao24"]:
                                    dataset.append(plane["icao24"])

                    output_path = f"/app/{jobid}.png"
                    if long:
                        plot_data(long, lat, alt, min_altitude, max_altitude, output_path)
                        with open(output_path, 'rb') as f:
                            img = f.read()
                        results.hset(jobid, 'image', img)
                        results.hset(jobid, 'data', json.dumps(dataset))
                    else:
                        logging.info("No planes within the specified altitude")

                    time.sleep(5)
                    logging.info(f"Job, {jobid}, processing complete")
                    job['status'] = 'complete'
                    job['result'] = dataset
                    jdb.set(jobid, json.dumps(job))


if __name__ == '__main__':
    logging.info("Started worker.py")
    do_work()
