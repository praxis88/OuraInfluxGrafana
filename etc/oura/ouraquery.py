import requests
from datetime import datetime, timedelta
import json
from datetime import datetime, timedelta, date
from influxdb_client import WritePrecision, InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import influxdb_client, os, time
import utils as utils
import requests
import argparse
import json
import re

OURA_CLOUD_PAT = os.getenv('OURA_CLOUD_PAT')
# end_date = date.today() + timedelta(days=1)
# start_date = date.today()
start_date = datetime.strptime("2026-02-14", "%Y-%m-%d")
end_date = start_date + timedelta(days=1)


def get_data(start_date,end_date,OURA_CLOUD_PAT,datatype):
    url = f"https://api.ouraring.com/v2/usercollection/{datatype}"
    headers = {"Authorization": f"Bearer {OURA_CLOUD_PAT}"}
    params = {"start_date": f"{start_date}", 'end_date': f"{end_date}"}
    response = requests.request('GET', url, headers=headers, params=params).json()
    
    if not response.get("data"):
        print(f"No {datatype} data for {start_date}")
        return None
    
    resp = response

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
            print(f"No long_sleep found for {start_date}, using first record as base")
        
        # Start with the long_sleep record as base
        aggregated_resp = long_sleep_record.copy()
        
        # If there are multiple sleep periods, aggregate the sum_fields
        if len(response["data"]) > 1:
            print(f"Found {len(response['data'])} sleep periods for {start_date}, aggregating...")
            
            # Reset sum fields to zero
            for field in sum_fields:
                aggregated_resp[field] = 0
            
            # Sum across all sleep periods
            for record in response["data"]:
                for field in sum_fields:
                    if field in record and record[field] is not None:
                        aggregated_resp[field] += record[field]
            
            print(f"Aggregated totals:")
            for field in sum_fields:
                print(f"  {field}: {aggregated_resp[field]}")
        
        # Replace the full response with just the aggregated record
        resp = {"data": [aggregated_resp]}

    #Adds the contributors section at level 0 of our readiness json. Includes stats like hrv and sleep balance
    if datatype == 'daily_readiness':
        resp2 = response["data"][0]["contributors"]
        resp.pop('contributors', None)
        resp.update(resp2)

    # All data should be consistent in influxdb, so turn ints to floats
    resp = {k:float(v) if type(v) == int else v for k,v in resp.items()}
    return resp

def prune(sleep_data, readiness_data, activity_data):
    # Extract the first (and only) sleep record after aggregation
    if sleep_data and 'data' in sleep_data and len(sleep_data['data']) > 0:
        sleep_record = sleep_data['data'][0]
    else:
        sleep_record = {}
    
    sleep_record.pop('heart_rate', None)
    sleep_record.pop('hrv', None)
    sleep_record.pop('movement_30_sec', None)
    sleep_record.pop('sleep_phase_5_min', None)
    sleep_record.pop('sleep_phase_30_sec', None)
    sleep_record.pop('low_battery_alert', None)
    sleep_record.pop('type', None)
    sleep_record.pop('readiness', None)
    sleep_record.pop('app_sleep_phase_5_min', None)
    
    if readiness_data:
        readiness_data.pop('contributors', None)
    if activity_data:
        activity_data.pop('contributors', None)
        activity_data.pop('met', None)
        activity_data.pop('class_5_min', None)

    data = sleep_record
    # data.update(readiness_data)
    # data.update(activity_data)
    return data


sleep_data = get_data(start_date,end_date,OURA_CLOUD_PAT, datatype='sleep')
readiness_data = get_data(start_date,end_date,OURA_CLOUD_PAT, datatype='daily_readiness')
activity_data = get_data(start_date,end_date,OURA_CLOUD_PAT, datatype='daily_activity')


data = prune(sleep_data, readiness_data, activity_data)



print(json.dumps(data, indent=4))
