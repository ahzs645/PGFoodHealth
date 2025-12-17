#!/usr/bin/env python3
"""
Geocode restaurant addresses to get lat/lng coordinates.
Uses OpenStreetMap Nominatim (free, no API key needed).
Saves progress incrementally.
"""

import json
import time
from geopy.geocoders import Nominatim
from geopy.extra.rate_limiter import RateLimiter


def geocode_restaurants(input_file="prince_george_restaurants_full.json", delay=1.5):
    """
    Add latitude/longitude coordinates to each restaurant.

    Args:
        input_file: JSON file with restaurant data
        delay: Seconds between geocoding requests (Nominatim requires 1s minimum)
    """
    # Load data
    with open(input_file, 'r') as f:
        data = json.load(f)

    # Set up geocoder with rate limiting and longer timeout
    geolocator = Nominatim(user_agent="pg_restaurant_api/1.0", timeout=10)
    geocode = RateLimiter(geolocator.geocode, min_delay_seconds=delay, max_retries=3)

    # Count stats
    already_geocoded = sum(1 for r in data if r.get('latitude'))
    print(f"Loaded {len(data)} restaurants")
    print(f"Already geocoded: {already_geocoded}")
    print(f"Remaining: {len(data) - already_geocoded}")
    print("=" * 60)

    success_count = 0
    fail_count = 0
    skip_count = 0

    for i, restaurant in enumerate(data):
        name = restaurant.get('name', 'Unknown')

        # Skip if already geocoded
        if restaurant.get('latitude') and restaurant.get('longitude'):
            skip_count += 1
            print(f"[{i+1}/{len(data)}] SKIP: {name} (already geocoded)")
            continue

        # Get address
        address = restaurant.get('full_address') or restaurant.get('address')
        if not address:
            print(f"[{i+1}/{len(data)}] SKIP: {name} (no address)")
            fail_count += 1
            continue

        # Add BC, Canada if not present for better geocoding
        if 'BC' not in address and 'British Columbia' not in address:
            address = f"{address}, BC, Canada"
        elif 'Canada' not in address:
            address = f"{address}, Canada"

        print(f"[{i+1}/{len(data)}] Geocoding: {name}")
        print(f"  Address: {address}")

        try:
            location = geocode(address)

            if location:
                restaurant['latitude'] = location.latitude
                restaurant['longitude'] = location.longitude
                restaurant['geocoded_address'] = location.address
                success_count += 1
                print(f"  Found: {location.latitude}, {location.longitude}")
            else:
                # Try with just street + city
                simple_address = f"{restaurant.get('address', '')}, Prince George, BC, Canada"
                location = geocode(simple_address)

                if location:
                    restaurant['latitude'] = location.latitude
                    restaurant['longitude'] = location.longitude
                    restaurant['geocoded_address'] = location.address
                    success_count += 1
                    print(f"  Found (simplified): {location.latitude}, {location.longitude}")
                else:
                    restaurant['geocode_error'] = "Address not found"
                    fail_count += 1
                    print(f"  NOT FOUND")

            # Save progress after each geocode
            save_progress(data, input_file)

        except Exception as e:
            restaurant['geocode_error'] = str(e)
            fail_count += 1
            print(f"  ERROR: {e}")
            save_progress(data, input_file)

    print("\n" + "=" * 60)
    print("COMPLETE!")
    print(f"Successfully geocoded: {success_count}")
    print(f"Failed: {fail_count}")
    print(f"Skipped (already done): {skip_count}")
    print("=" * 60)

    return data


def save_progress(data, filename):
    """Save current progress to file"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    import sys

    input_file = "prince_george_restaurants_full.json"
    delay = 1.5  # Nominatim requires at least 1 second between requests

    # Parse args
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == '--file' and i + 1 < len(args):
            input_file = args[i + 1]
            i += 2
        elif args[i] == '--delay' and i + 1 < len(args):
            delay = float(args[i + 1])
            i += 2
        elif args[i] in ['--help', '-h']:
            print("Usage: python geocode_restaurants.py [--file FILE] [--delay SECONDS]")
            print("  --file FILE    Input JSON file (default: prince_george_restaurants_full.json)")
            print("  --delay SECS   Delay between requests (default: 1.5, min 1.0)")
            sys.exit(0)
        else:
            i += 1

    print("=" * 60)
    print("Restaurant Geocoder")
    print(f"Input file: {input_file}")
    print(f"Delay: {delay}s between requests")
    print("=" * 60)
    print("\nThis script saves progress after each restaurant.")
    print("If interrupted, just run again to resume.\n")

    geocode_restaurants(input_file=input_file, delay=delay)
