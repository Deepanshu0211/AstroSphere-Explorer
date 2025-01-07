from flask import Flask, jsonify, render_template, request
import requests
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from cachetools import TTLCache
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()

app = Flask(__name__)

# Initialize cache with a TTL (Time-To-Live) of 1 hour
cache = TTLCache(maxsize=100, ttl=3600)

# Initialize the scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# NASA API Keys
NASA_API_KEY = os.getenv('NASA_API_KEY')
DONKI_API_KEY = os.getenv('DONKI_API_KEY')

# Launch Library 2 API base URL
BASE_URL = "https://ll.thespacedevs.com/2.2.0/"

def get_missions(agency_ids, status):
    cache_key = f"missions_{agency_ids}_{status}"
    if cache_key in cache:
        return cache[cache_key]

    endpoint = 'launch/upcoming/' if status == 'upcoming' else 'launch/previous/'
    url = f"{BASE_URL}{endpoint}"
    params = {
        'lsp__id__in': ','.join(map(str, agency_ids)),
        'mode': 'detailed',
        'limit': 20,
    }
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            launches = response.json().get('results', [])
            if status == 'ongoing':
                ongoing_launches = [launch for launch in launches if launch['status']['name'] == 'In Flight']
                launches = ongoing_launches
            cache[cache_key] = launches
            return launches
        elif response.status_code == 429:
            print("Rate limit exceeded. Using cached data if available.")
            if cache_key in cache:
                return cache[cache_key]
            else:
                return []
        else:
            print(f"Error fetching missions: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching missions: {e}")
        return []

def get_space_weather():
    cache_key = 'space_weather'
    if cache_key in cache:
        return cache[cache_key]

    start_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
    end_date = datetime.utcnow().strftime('%Y-%m-%d')
    url = f"https://api.nasa.gov/DONKI/FLR?startDate={start_date}&endDate={end_date}&api_key={DONKI_API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            flares = response.json()
            events = []
            for flare in flares:
                event = {
                    'event_time': flare['beginTime'],
                    'class_type': flare.get('classType', 'N/A'),
                    'location': flare.get('sourceLocation', 'N/A'),
                    'region': flare.get('activeRegionNum', 'N/A'),
                    'instruments': ', '.join(instr.get('displayName', 'N/A') for instr in flare.get('instruments', []))
                }
                events.append(event)
            cache[cache_key] = events
            return events
        else:
            print(f"Error fetching space weather: {response.status_code}")
            return []
    except requests.exceptions.RequestException as e:
        print(f"Error fetching space weather: {e}")
        return []

def get_astronomical_events():
    cache_key = 'astro_event'
    if cache_key in cache:
        return cache[cache_key]

    url = f"https://api.nasa.gov/planetary/apod?api_key={NASA_API_KEY}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            astro_event = response.json()
            cache[cache_key] = astro_event
            return astro_event
        else:
            print(f"Error fetching astronomical events: {response.status_code}")
            return {}
    except requests.exceptions.RequestException as e:
        print(f"Error fetching astronomical events: {e}")
        return {}

@app.route('/')
def home():
    current_year = datetime.now().year
    space_weather = get_space_weather()
    astro_event = get_astronomical_events()
    return render_template(
        'index.html',
        space_weather=space_weather,
        astro_event=astro_event,
        current_year=current_year
    )

@app.route('/api/missions')
def api_missions():
    agency = request.args.get('agency', 'all')
    status = request.args.get('status', 'upcoming')

    agency_ids = {
        'spacex': 121,
        'nasa': 44,
        'isro': 31,
        # Add other agencies as needed
    }

    if agency.lower() == 'all':
        selected_agency_ids = list(agency_ids.values())
    else:
        agency_id = agency_ids.get(agency.lower())
        if not agency_id:
            return jsonify([])
        selected_agency_ids = [agency_id]

    missions = get_missions(selected_agency_ids, status)
    return jsonify(missions)

def update_cached_data():
    with app.app_context():
        cache.clear()
        agencies = ['all']
        statuses = ['upcoming', 'ongoing', 'completed']
        for agency in agencies:
            for status in statuses:
                # Fetch and cache missions
                agency_ids = list(agency_ids.values()) if agency == 'all' else [agency_ids.get(agency)]
                get_missions(agency_ids, status)
        # Fetch and cache space weather and astronomical events
        get_space_weather()
        get_astronomical_events()
    print("Cached data updated.")

# Schedule the cache update daily at midnight
scheduler.add_job(func=update_cached_data, trigger='cron', hour=0)

if __name__ == "__main__":
    app.run(debug=True)
