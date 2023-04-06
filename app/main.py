import os
from datetime import datetime, timedelta

import dateutil.parser as dt
import pytz
import requests

from slot_mapper import SlotMapper

# Fetches consumption data from Octopus Consumption API
API_KEY = os.environ['API_KEY']
MPAN = os.environ['MPAN']
METER_ID = os.environ['METER_ID']
WEBHOOK_URL = os.environ['WEBHOOK_URL']
UPLOAD_TO_MATTERMOST = os.environ.get('UPLOAD_TO_MATTERMOST', 'true').lower() == 'true'
AGILE_TARIFF = "AGILE-FLEX-22-11-25"
FLEXIBLE_TARIFF = "VAR-22-11-01"
INTELLIGENT_TARIFF = "INTELLI-BB-VAR-23-03-01"
GSP_ID = "J"  # https://developer.octopus.energy/docs/api/#list-grid-supply-points

# Setup times from midnight
london_tz = pytz.timezone('Europe/London')
now = datetime.now(london_tz)

TODAY = now.replace(hour=0, minute=0, second=0, microsecond=0)
YESTERDAY = TODAY - timedelta(days=1)
YESTERDAY_2330 = YESTERDAY.replace(hour=23, minute=30, second=0, microsecond=0)

def get_standard_unit_rates(tariff):
    # Fetches the Octopus Agile rates for the day, returning the average rate across the day
    u = f"https://api.octopus.energy/v1/products/{tariff}/electricity-tariffs/E-1R-{tariff}-{GSP_ID}/standard-unit-rates/"
    response = requests.get(u, auth=(API_KEY, ''),
                            params={'period_from': YESTERDAY.isoformat(), 'period_to': TODAY.isoformat(),
                                    'order_by': 'period'})
    response.raise_for_status()

    # Convert valid_from and valid_to to isoformat with our timezone
    rates = []
    for rate in response.json()['results']:
        rate['valid_from'] = dt.parse(rate['valid_from']).astimezone(pytz.timezone('Europe/London')).isoformat()
        if rate['valid_to'] is not None:
            rate['valid_to'] = dt.parse(rate['valid_to']).astimezone(pytz.timezone('Europe/London')).isoformat()
        rates.append(rate)

    return rates


# Get yesterday's consumption
# Use the Octopus API to get yesterday's consumption
def get_day_consumption():
    # Get yesterday's consumption
    u = f"https://api.octopus.energy/v1/electricity-meter-points/{MPAN}/meters/{METER_ID}/consumption"
    # use basic auth
    response = requests.get(u, auth=(API_KEY, ''),
                            params={'period_from': YESTERDAY.isoformat(), 'period_to': YESTERDAY_2330.isoformat(),
                                    'order_by': 'period'})
    response.raise_for_status()

    return response.json()['results']


def get_standing(tariff):
    u = f"https://api.octopus.energy/v1/products/{tariff}/electricity-tariffs/E-1R-{tariff}-{GSP_ID}/standing-charges/"
    response = requests.get(u, auth=(API_KEY, ''),
                            params={'period_from': YESTERDAY.isoformat(), 'period_to': TODAY.isoformat(),
                                    'order_by': 'period'})
    response.raise_for_status()

    return response.json()['results'][0]['value_inc_vat'] / 100


def fmt_price(price):
    return f"£{price:.2f}"


def calculate_total_kwh_cost(consumption_slots, unit_slots):
    price_per_slot = SlotMapper.product_maps(consumption_slots.get(), unit_slots.get())

    # Sum the array for total cost
    total_kwh = sum(consumption_slots.get())
    total_cost = sum(price_per_slot) / 100

    return round(total_kwh, 2), round(total_cost, 2)


def get_peak_off_price(unit_slots, peak):
    # Assumes just HIGH and LOW pricing
    if peak:
        return max(unit_slots.get())
    else:
        return min(unit_slots.get())


def calculate_peak_off_kwh_and_cost(consumption_slots, unit_slots, peak):
    rate_match = get_peak_off_price(unit_slots, peak)

    # Get the slots that match the rate
    m = zip(consumption_slots.get(), unit_slots.get())
    slots = [i for i in m if i[1] == rate_match]

    # Sum the consumption for the slots
    total_kwh = sum([i[0] for i in slots])
    total_cost = sum([i[0] * i[1] for i in slots]) / 100
    #
    # print(f"{'Peak' if peak else 'Off peak'} kwh: {total_kwh:.2f}")
    # print(f"{'Peak' if peak else 'Off peak'} cost: {fmt_price(total_cost)}")
    #

    return round(total_kwh, 2), round(total_cost, 2)


def main():
    # Get yesterday's consumption
    consumption_slots = SlotMapper()
    consumption_slots.map_from_sparse(get_day_consumption(), "interval_start", "consumption")

    intelligent_unit_slots = SlotMapper()
    intelligent_unit_slots.map_from_sparse(get_standard_unit_rates(INTELLIGENT_TARIFF), "valid_from", "value_inc_vat")

    int_standing_charge = get_standing(INTELLIGENT_TARIFF)
    int_peak_price = get_peak_off_price(intelligent_unit_slots, True) / 100
    int_off_peak_price = get_peak_off_price(intelligent_unit_slots, False) / 100

    int_peak_kwh, int_peak_cost = calculate_peak_off_kwh_and_cost(consumption_slots, intelligent_unit_slots, True)
    int_off_peak_kwh, int_off_peak_cost = calculate_peak_off_kwh_and_cost(consumption_slots, intelligent_unit_slots,
                                                                          False)

    total_kwh_usage, int_total_kwh_cost = calculate_total_kwh_cost(consumption_slots, intelligent_unit_slots)
    int_total_cost = int_total_kwh_cost + int_standing_charge
    int_total_avg = int_total_cost / total_kwh_usage

    # Create a markdown table for the above
    buffer = f"Energy breakdown for {YESTERDAY} (Intelligent Tariff)\n\n"
    buffer += f"|  | £/kWh | kWh | £ |\n"
    buffer += f"| --- | --- | --- | --- |\n"
    buffer += f"| :sunny:  | {fmt_price(int_peak_price)} | {int_peak_kwh} | {fmt_price(int_peak_cost)} |\n"
    buffer += f"| :crescent_moon:  | {fmt_price(int_off_peak_price)} | {int_off_peak_kwh} | {fmt_price(int_off_peak_cost)} |\n"
    buffer += f"| :person_doing_cartwheel:  | - | - | {fmt_price(int_standing_charge)} |\n"
    buffer += f"| Total | - | {total_kwh_usage} | **{fmt_price(int_total_cost)}** |\n"

    # Compare with AGILE average and FLEXIBLE tarrifs
    buffer += f"\n\n"

    # Agile
    # Map consumption data with Agile unit rates
    agile_unit_slots = SlotMapper()
    agile_unit_slots.map_from_sparse(get_standard_unit_rates(AGILE_TARIFF), "valid_from", "value_inc_vat")
    _, agi_total_kwh_cost = calculate_total_kwh_cost(consumption_slots, agile_unit_slots)
    agi_standing = get_standing(AGILE_TARIFF)
    agi_total_cost = agi_total_kwh_cost + agi_standing
    agi_total_avg = agi_total_cost / total_kwh_usage
    agi_diff = round((agi_total_cost - int_total_cost) / int_total_cost * 100, 2)

    # Flexible
    flexible_unit_slots = SlotMapper()
    flexible_unit_slots.map_from_sparse(get_standard_unit_rates(FLEXIBLE_TARIFF), "valid_from", "value_inc_vat")
    _, flexible_total_kwh_cost = calculate_total_kwh_cost(consumption_slots, flexible_unit_slots)

    flexible_standing = get_standing(FLEXIBLE_TARIFF)
    flexible_total = flexible_total_kwh_cost + flexible_standing
    flexible_avg = flexible_total / total_kwh_usage
    flexible_diff = round((flexible_total - int_total_cost) / int_total_cost * 100, 2)

    buffer += f"*Comparison with other tariffs*\n\n"
    buffer += f"| Tariff | £/kWh | £ + :person_doing_cartwheel: | :money_with_wings: |\n"
    buffer += f"| --- | --- | --- | --- |\n"
    # calculate percentage difference compared to intelligent
    buffer += f"| AGILE | {fmt_price(agi_total_avg)} | {fmt_price(agi_total_cost)} | {agi_diff}% |\n"
    buffer += f"| FLEXIBLE | {fmt_price(flexible_avg)} | {fmt_price(flexible_total)} | {flexible_diff}% |\n"
    buffer += f"| **INTELLIGENT** | **{fmt_price(int_total_avg)}** | **{fmt_price(int_total_cost)}** | **-** |\n"

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
