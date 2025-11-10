#!/usr/bin/env python3
"""
Example usage of the Prince George Restaurant Inspection API
"""

import requests
import json

# Base URL for the API
BASE_URL = "http://localhost:5001"

def print_section(title):
    """Print a section header"""
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60 + "\n")

def example_1_get_stats():
    """Example 1: Get overall statistics"""
    print_section("Example 1: Get Statistics")

    response = requests.get(f"{BASE_URL}/restaurants/stats")
    stats = response.json()

    print(f"Total Restaurants: {stats['total_restaurants']}")
    print(f"\nHazard Rating Breakdown:")
    for rating, count in stats['hazard_ratings'].items():
        percentage = (count / stats['total_restaurants']) * 100
        print(f"  {rating}: {count} ({percentage:.1f}%)")
    print(f"\nLast Updated: {stats['last_updated']}")

def example_2_search_restaurants():
    """Example 2: Search for specific restaurants"""
    print_section("Example 2: Search for Pizza Places")

    response = requests.get(f"{BASE_URL}/restaurants", params={'search': 'pizza', 'limit': 5})
    data = response.json()

    print(f"Found {data['count']} pizza restaurants (showing first 5):\n")
    for restaurant in data['restaurants']:
        print(f"• {restaurant['name']}")
        print(f"  Address: {restaurant['address']}")
        print(f"  Hazard Rating: {restaurant['hazard_rating']}")
        print(f"  Details: {restaurant['details_url']}")
        print()

def example_3_filter_by_hazard():
    """Example 3: Filter by hazard rating"""
    print_section("Example 3: Get Moderate Hazard Restaurants")

    response = requests.get(f"{BASE_URL}/restaurants/hazard/moderate")
    data = response.json()

    print(f"Found {data['count']} moderate hazard restaurants:\n")
    for restaurant in data['restaurants']:
        print(f"• {restaurant['name']} - {restaurant['address']}")

def example_4_get_by_name():
    """Example 4: Search by specific name"""
    print_section("Example 4: Find Tim Hortons Locations")

    response = requests.get(f"{BASE_URL}/restaurants/name/tim hortons")
    data = response.json()

    print(f"Found {data['count']} Tim Hortons locations:\n")
    for restaurant in data['restaurants']:
        print(f"• {restaurant['name']}")
        print(f"  {restaurant['address']}")
        print()

def example_5_complex_query():
    """Example 5: Complex filtering"""
    print_section("Example 5: Search for Low Hazard Sushi Restaurants")

    # First get all restaurants
    response = requests.get(f"{BASE_URL}/restaurants", params={
        'search': 'sushi',
        'hazard': 'low'
    })
    data = response.json()

    print(f"Found {data['count']} low hazard sushi restaurants:\n")
    for restaurant in data['restaurants']:
        print(f"• {restaurant['name']}")
        print(f"  Address: {restaurant['address']}")
        print(f"  Hazard: {restaurant['hazard_rating']}")
        print()

def example_6_get_all_restaurants():
    """Example 6: Get all restaurants and analyze"""
    print_section("Example 6: Analyze All Restaurants")

    response = requests.get(f"{BASE_URL}/restaurants")
    data = response.json()

    print(f"Total restaurants: {data['count']}\n")

    # Find restaurants with specific keywords
    keywords = ['coffee', 'pizza', 'sushi', 'burger', 'chinese']

    print("Restaurant types:")
    for keyword in keywords:
        count = sum(1 for r in data['restaurants']
                   if keyword.lower() in r['name'].lower())
        if count > 0:
            print(f"  {keyword.title()}: {count} restaurants")

def main():
    """Run all examples"""
    print("=" * 60)
    print("Prince George Restaurant Inspection API")
    print("Example Usage Script")
    print("=" * 60)
    print("\nMake sure the API server is running on http://localhost:5001")
    print("Start it with: python3 pg_restaurant_api.py")

    try:
        # Test if API is available
        response = requests.get(f"{BASE_URL}/", timeout=2)
        if response.status_code != 200:
            print("\n❌ API is not responding. Please start the server first.")
            return

        # Run examples
        example_1_get_stats()
        example_2_search_restaurants()
        example_3_filter_by_hazard()
        example_4_get_by_name()
        example_5_complex_query()
        example_6_get_all_restaurants()

        print("\n" + "=" * 60)
        print("Examples completed successfully!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n❌ Error: Could not connect to API server.")
        print("Please make sure the server is running:")
        print("  python3 pg_restaurant_api.py")
    except Exception as e:
        print(f"\n❌ Error: {e}")

if __name__ == "__main__":
    main()
