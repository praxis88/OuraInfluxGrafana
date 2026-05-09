import requests
from datetime import datetime, timedelta
import json

class PrintTimeStamp():
   def write(self,x):
       ts = str(datetime.now())
       print("<{}> {}".format(str(ts),x))

def data_exists_in_influx(end_date, query_api, INFLUXDB_BUCKET):
    """Check if data already exists for this date in InfluxDB"""
    pts = PrintTimeStamp()
    
    # The data is timestamped with bedtime_end, which is typically the morning
    # of the date we're querying. We need to check a wider range to catch it.
    date_obj = datetime.strptime(end_date, '%Y-%m-%d')
    
    # Check from the previous day to the next day to catch bedtime_end times
    start = (date_obj - timedelta(days=1)).strftime('%Y-%m-%dT00:00:00Z')
    stop = (date_obj + timedelta(days=1)).strftime('%Y-%m-%dT23:59:59Z')

    query = f'''
    from(bucket: "{INFLUXDB_BUCKET}")
        |> range(start: time(v: "{start}"), stop: time(v: "{stop}"))
        |> filter(fn: (r) => r["_measurement"] == "oura_measurements")
        |> filter(fn: (r) => r["_field"] == "day")
        |> filter(fn: (r) => r["_value"] == "{end_date}")
        |> limit(n: 1)
    '''
        
    try:
        result = query_api.query(query)
        for table in result:
            pts.write(f"Table has {len(table.records)} records")
        has_data = any(len(table.records) > 0 for table in result)
        return has_data
    except Exception as e:
        pts.write(f"Warning: Error checking InfluxDB for {end_date}: {e}")
        import traceback
        traceback.print_exc()
        return False


def fetch_data(start_date,end_date,datatype,OURA_CLOUD_PAT):
    pts = PrintTimeStamp()
    url = f"https://api.ouraring.com/v2/usercollection/{datatype}"
    headers = {"Authorization": f"Bearer {OURA_CLOUD_PAT}"}
    params = {"start_date": f"{start_date}", 'end_date': f"{end_date}"}
    response = requests.request('GET', url, headers=headers, params=params).json()

    if not response["data"]:
        pts.write("No {} data yet for time window {}".format(datatype, start_date))
        return None

    resp = response["data"][0]

    # For sleep data, aggregate all sleep periods (long_sleep + naps)
    if datatype == 'sleep':
        # Fields to sum across all sleep periods
        sum_fields = [
            'total_sleep_duration',
            'deep_sleep_duration', 
            'light_sleep_duration',
            'rem_sleep_duration',
            'awake_time',
            'time_in_bed',
            'restless_periods',
            'latency'
        ]
        
        # Find the long_sleep record to use as the base
        long_sleep_record = None
        for record in response["data"]:
            if record.get('type') == 'long_sleep':
                long_sleep_record = record
                break
        
        # If no long_sleep found, use the first record as base
        if long_sleep_record is None:
            long_sleep_record = response["data"][0]
            pts.write(f"No long_sleep found for {start_date}, using first record as base")
        
        # Start with the long_sleep record as base
        resp = long_sleep_record.copy()
        
        # If there are multiple sleep periods, aggregate the sum_fields
        if len(response["data"]) > 1:
            pts.write(f"Found {len(response['data'])} sleep periods for {start_date}, aggregating...")
            
            # Reset sum fields to zero
            for field in sum_fields:
                resp[field] = 0
            
            # Sum across all sleep periods
            for record in response["data"]:
                for field in sum_fields:
                    if field in record and record[field] is not None:
                        resp[field] += record[field]

    #Adds the contributors section at level 0 of our readiness json. Includes stats like hrv and sleep balance
    if datatype == 'daily_readiness':
        resp2 = response["data"][0]["contributors"]
        resp.pop('contributors', None)
        resp.update(resp2)

    # All data should be consistent in influxdb, so turn ints to floats
    resp = {k:float(v) if type(v) == int else v for k,v in resp.items()}
    return resp

def get_data_one_day(start_date, OURA_CLOUD_PAT):
    pts = PrintTimeStamp()
    end_date = start_date + timedelta(days=1)
    
    sleep_data = fetch_data(start_date, end_date, 'sleep', OURA_CLOUD_PAT)
    readiness_data = fetch_data(start_date, end_date, 'daily_readiness', OURA_CLOUD_PAT)
    activity_data = fetch_data(start_date, end_date, 'daily_activity', OURA_CLOUD_PAT)

    # Require at least one data source, but allow partial data
    if sleep_data is None and readiness_data is None and activity_data is None:
        pts.write("No data at all for {}, skipping".format(start_date))
        return None

    if sleep_data is None:
        pts.write("No sleep data for {}, continuing with partial data".format(start_date))
    if readiness_data is None:
        pts.write("No readiness data for {}, continuing with partial data".format(start_date))
    if activity_data is None:
        pts.write("No activity data for {}, continuing with partial data".format(start_date))

    # Clean out array type data (only if the source exists)
    if sleep_data is not None:
        for key in ['heart_rate', 'hrv', 'movement_30_sec', 'sleep_phase_5_min',
                    'sleep_phase_30_sec', 'low_battery_alert', 'type', 'readiness',
                    'app_sleep_phase_5_min']:
            sleep_data.pop(key, None)

    if readiness_data is not None:
        readiness_data.pop('contributors', None)

    if activity_data is not None:
        for key in ['contributors', 'met', 'class_5_min']:
            activity_data.pop(key, None)

    # Merge whatever data we have
    data = {}
    if sleep_data is not None:
        data.update(sleep_data)
    if readiness_data is not None:
        data.update(readiness_data)
    if activity_data is not None:
        data.update(activity_data)

    # Determine the timestamp — prefer bedtime_end, fall back to activity day
    timestamp = data.get('bedtime_end') or data.get('day') or str(start_date)

    post_data = [{
        "measurement": "oura_measurements",
        "time": timestamp,
        "fields": data
    }]
    return post_data