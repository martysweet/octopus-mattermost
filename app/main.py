import requests
import os
from zoneinfo import ZoneInfo
from datetime import datetime, timedelta


# Fetches consumption data from Octopus Consumption API
API_KEY = os.environ['API_KEY']
MPAN = os.environ['MPAN']
METER_ID = os.environ['METER_ID']
WEBHOOK_URL = os.environ['WEBHOOK_URL']
UPLOAD_TO_MATTERMOST = os.environ.get('UPLOAD_TO_MATTERMOST', 'true').lower() == 'true'
AGILE_TARIFF = "AGILE-FLEX-22-11-25"
FLEXIBLE_TARIFF = "VAR-22-11-01"
GSP_ID = "J" # https://developer.octopus.energy/docs/api/#list-grid-supply-points

# Setup times from midnight
TODAY = datetime.today().replace(hour=0, minute=0, second=0, microsecond=0)
TODAY.replace(tzinfo=ZoneInfo('Europe/London'))
YESTERDAY = TODAY - timedelta(days=1)

# Get current peak/off peak rates
def get_intelligent_rates():
    return {
        "peak": 0.4425,
        "off_peak": 0.10,
        "standing": 0.4557
    }

# Get yesterday's consumption
# Use the Octopus API to get yesterday's consumption
def get_day_consumption():
    # Get yesterday's consumption
    u = f"https://api.octopus.energy/v1/electricity-meter-points/{MPAN}/meters/{METER_ID}/consumption?period_from={YESTERDAY.isoformat()}&period_to={TODAY.isoformat()}&order_by=period"

    # use basic auth
    response = requests.get(u, auth=(API_KEY, ''))
    response.raise_for_status()

    return response.json()['results']

def get_standing(tariff):
    u = f"https://api.octopus.energy/v1/products/{tariff}/electricity-tariffs/E-1R-{tariff}-{GSP_ID}/standing-charges//?period_from={YESTERDAY.isoformat()}&period_to={TODAY.isoformat()}&order_by=period"
    response = requests.get(u, auth=(API_KEY, ''))
    response.raise_for_status()

    return response.json()['results'][0]['value_inc_vat'] / 100


def get_agile_kwh_rate():
    # Fetches the Octopus Agile rates for the day, returning the average rate across the day
    u = f"https://api.octopus.energy/v1/products/{AGILE_TARIFF}/electricity-tariffs/E-1R-{AGILE_TARIFF}-{GSP_ID}/standard-unit-rates/?period_from={YESTERDAY.isoformat()}&period_to={TODAY.isoformat()}&order_by=period"
    response = requests.get(u, auth=(API_KEY, ''))
    response.raise_for_status()

    results =  response.json()['results']

    # Add up all values and divide by count to get average
    total = 0
    for r in results:
        total += r['value_inc_vat']

    # TODO: How to add the standing charge?

    avg_pence_per_kwh = total / len(results)
    avg_pound_per_kwh = avg_pence_per_kwh / 100

    return avg_pound_per_kwh



def get_flexible_kwh_rate():
    # Fetches the Octopus Agile rates for the day, returning the average rate across the day
    u = f"https://api.octopus.energy/v1/products/{FLEXIBLE_TARIFF}/electricity-tariffs/E-1R-{FLEXIBLE_TARIFF}-{GSP_ID}/standard-unit-rates/?period_from={YESTERDAY.isoformat()}&period_to={TODAY.isoformat()}&order_by=period"
    response = requests.get(u, auth=(API_KEY, ''))
    response.raise_for_status()

    results =  response.json()['results'][0]
    return results['value_inc_vat'] / 100

def fmt_price(price):
    return f"£{price:.2f}"

def main():
    r = get_day_consumption()

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
    intelligent_peak_price = round(get_intelligent_rates()['peak'], 2)
    intelligent_off_peak_price = round(get_intelligent_rates()['off_peak'], 2)
    intelligent_standing_price = round(get_intelligent_rates()['standing'], 2)

    peak_cost = round(peak_kwh * intelligent_peak_price, 2)
    off_peak_cost = round(off_peak_kwh * intelligent_off_peak_price, 2)

    total_cost = round(peak_cost + off_peak_cost + intelligent_standing_price, 2)
    total_kwh = peak_kwh + off_peak_kwh
    avg_price_per_kwh = round(total_cost / total_kwh, 2)

    # Create a markdown table for the above
    buffer = f"Energy breakdown for {YESTERDAY} (Intelligent Tariff)\n\n"
    buffer += f"|  | £/kWh | kWh | £ |\n"
    buffer += f"| --- | --- | --- | --- |\n"
    buffer += f"| :sunny:  | {fmt_price(intelligent_peak_price)} | {peak_kwh} | {fmt_price(peak_cost)} |\n"
    buffer += f"| :crescent_moon:  | {fmt_price(intelligent_off_peak_price)} | {off_peak_kwh} | {fmt_price(off_peak_cost)} |\n"
    buffer += f"| :person_doing_cartwheel:  | - | - | {fmt_price(intelligent_standing_price)} |\n"
    buffer += f"| Total | - | { total_kwh } | **{fmt_price(total_cost) }** ({fmt_price(avg_price_per_kwh)}/kWh) |\n"

    # Compare with AGILE average and FLEXIBLE tarrifs
    buffer += f"\n\n"

    # Intelligent
    intelligent_rate = round(avg_price_per_kwh, 2)
    intelligent_total = total_cost

    # Agile
    agile_rate = round(get_agile_kwh_rate(), 2)
    agile_standing = get_standing(AGILE_TARIFF)
    agile_total = round((agile_rate * total_kwh) + agile_standing, 2)
    agile_diff = round((agile_total - intelligent_total) / intelligent_total * 100, 2)

    # Flexible
    flexible_rate = round(get_flexible_kwh_rate(), 2)
    flexible_standing = get_standing(FLEXIBLE_TARIFF)
    flexible_total = round((flexible_rate * total_kwh) + flexible_standing, 2)
    flexible_diff = round((flexible_total - intelligent_total) / intelligent_total * 100, 2)

    buffer += f"*Comparison with other tariffs*\n\n"
    buffer += f"| Tariff | £/kWh | £ + :person_doing_cartwheel: | :money_with_wings: |\n"
    buffer += f"| --- | --- | --- | --- |\n"
    # calculate percentage difference compared to intelligent
    buffer += f"| AGILE | {fmt_price(agile_rate)} (avg) | {fmt_price(agile_total)} | {agile_diff}% |\n"
    buffer += f"| FLEXIBLE | {fmt_price(flexible_rate)} | {fmt_price(flexible_total)} | {flexible_diff}% |\n"
    buffer += f"| **INTELLIGENT** | **{fmt_price(intelligent_rate)}** | **{fmt_price(intelligent_total)}** | **-** |\n"

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
    print(text)
    if UPLOAD_TO_MATTERMOST:
        upload_to_mattermost(text)


if __name__ == "__main__":
    lambda_handler(None, None)