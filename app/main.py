import requests
import datetime
import os

# Fetches consumption data from Octopus Consumption API

API_KEY = os.environ['API_KEY']
MPAN = os.environ['MPAN']
METER_ID = os.environ['METER_ID']
WEBHOOK_URL = os.environ['WEBHOOK_URL']

# Get current peak/off peak rates
def get_rates():
    return {
        "peak": 0.4425,
        "off_peak": 0.10,
        "standing": 0.4557
    }

# Get yesterday's consumption
# Use the Octopus API to get yesterday's consumption
def get_day_consumption(day):
    # Get today midnight
    today_midnight = datetime.datetime.combine(day, datetime.time(23, 30, 0))

    # Get yesterday's consumption
    u = f"https://api.octopus.energy/v1/electricity-meter-points/{MPAN}/meters/{METER_ID}/consumption?period_from={day}&period_to={today_midnight}&order_by=period"

    # use basic auth
    response = requests.get(u, auth=(API_KEY, ''))
    response.raise_for_status()

    return response.json()['results']

def main():
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    r = get_day_consumption(yesterday)

    peak_kwh = 0
    off_peak_kwh = 0

    for i in r:
        # Get HHmm from interval_start 2023-04-02T01:30:00+01:00 => 130
        hhmm = int(i['interval_start'][11:13] + i['interval_start'][14:16])

        if hhmm >= 530 and hhmm < 2330:
            peak_kwh += i['consumption']
        else:
            off_peak_kwh += i['consumption']

    # Round to 2 decimal places
    peak_kwh = round(peak_kwh, 2)
    off_peak_kwh = round(off_peak_kwh, 2)

    # Calculate price and round
    peak_price = round(peak_kwh * get_rates()['peak'], 2)
    off_peak_price = round(off_peak_kwh * get_rates()['off_peak'], 2)

    total_price = round(peak_price + off_peak_price + get_rates()['standing'], 2)
    total_kwh = peak_kwh + off_peak_kwh
    avg_price_per_kwh = round(total_price / total_kwh, 2)

    # Create a markdown table for the above
    buffer = f"| {yesterday} | Rate (per kWh) | Consumption (kWh) | Cost (£) |\n"
    buffer += f"| --- | --- | --- | --- |\n"
    buffer += f"| Peak | £{get_rates()['peak']} | {peak_kwh} | £{peak_price} |\n"
    buffer += f"| Off peak | £{get_rates()['off_peak']} | {off_peak_kwh} | £{off_peak_price} |\n"
    buffer += f"| Standing | - | - | £{get_rates()['standing']} |\n"
    buffer += f"| Total | - | { total_kwh } | **£{total_price}** (£{avg_price_per_kwh}/kWh) |\n"

    return buffer

def upload_to_mattermost(text):
    headers = {
        'Content-Type': 'application/json'
    }

    payload = {
        'text': text,
        'username': 'Octopus Energy',
        'icon_url': 'https://pbs.twimg.com/profile_images/1367436085064830977/O7SIYBjt_400x400.png'
    }

    response = requests.post(WEBHOOK_URL, headers=headers, json=payload)
    response.raise_for_status()

def lambda_handler(event, context):
    text = main()
    upload_to_mattermost(text)

if __name__ == "__main__":
    lambda_handler(None, None)