#!/usr/bin/env python3
"""
HealthSpace API Client for Prince George Restaurant Inspections
Fetches restaurant inspection data from the Northern Health Authority HealthSpace system.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
import json
import time

class HealthSpaceAPI:
    def __init__(self):
        self.base_url = "https://www.healthspace.ca/Clients/NHA/NHA_Website.nsf"
        self.session = requests.Session()

        # Headers to mimic a browser request (helps avoid bot detection)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Sec-Fetch-Dest': 'frame',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'same-origin',
        })

    def get_restaurants(self, start=0, count=30, category="FD4BF9F2DD74F5A2FC5B1DE44C0A8E31"):
        """
        Fetch restaurant list from HealthSpace API

        Args:
            start: Starting index for pagination
            count: Number of results to return
            category: Category ID (default is for Prince George area)

        Returns:
            List of restaurant data dictionaries
        """
        url = f"{self.base_url}/Food-List-ByName"
        params = {
            'OpenView': '',
            'RestrictToCategory': category,
            'Count': count,  # Capital C
        }

        # Only add start if not the first page
        if start > 0:
            params['start'] = start

        try:
            print(f"Fetching: {url}")
            print(f"Params: start={start}, count={count}")

            response = self.session.get(url, params=params, timeout=30)
            print(f"Status Code: {response.status_code}")

            response.raise_for_status()

            # Parse the HTML response
            soup = BeautifulSoup(response.text, 'html.parser')
            restaurants = self._parse_restaurant_list(soup)

            return restaurants
        except requests.exceptions.RequestException as e:
            print(f"Error fetching data: {e}")
            print(f"Response status: {response.status_code if 'response' in locals() else 'N/A'}")

            # Save response for debugging if we got one
            if 'response' in locals():
                with open('healthspace_debug.html', 'w', encoding='utf-8') as f:
                    f.write(response.text)
                print("Response saved to healthspace_debug.html for inspection")

            return None

    def _parse_restaurant_list(self, soup):
        """Parse the restaurant list from HTML"""
        restaurants = []

        # Save HTML for debugging first time
        with open('healthspace_response.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print("HTML saved to healthspace_response.html for inspection\n")

        # Try to find the data table
        # HealthSpace typically uses viewEntryTable class
        table = soup.find('table', class_='viewEntryTable')

        if not table:
            # Try other common table patterns
            table = soup.find('table')

        if not table:
            print("Warning: Could not find data table in response")
            return restaurants

        # Find all rows, skip header
        rows = table.find_all('tr')[1:]  # Skip header row

        print(f"Found {len(rows)} rows in table\n")

        for idx, row in enumerate(rows):
            cells = row.find_all('td')

            if len(cells) < 2:
                continue

            restaurant = {}

            # Extract data from cells
            # Typical structure: Name, Address, Last Inspection, etc.
            for i, cell in enumerate(cells):
                # Get text content
                text = cell.get_text(strip=True)

                # Extract links
                link = cell.find('a')
                if link and 'href' in link.attrs:
                    if i == 0:  # First column usually has the name
                        restaurant['name'] = text
                        restaurant['details_url'] = f"https://www.healthspace.ca{link['href']}"

            # Map columns: Name (0), blank (1), Address (2), Hazard Rating (3)
            if len(cells) >= 1:
                restaurant['name'] = cells[0].get_text(strip=True)
            if len(cells) >= 3:
                restaurant['address'] = cells[2].get_text(strip=True)
            if len(cells) >= 4:
                restaurant['hazard_rating'] = cells[3].get_text(strip=True)

            # Get detail link from first cell
            link = cells[0].find('a') if cells else None
            if link and 'href' in link.attrs:
                href = link['href']
                if not href.startswith('http'):
                    restaurant['details_url'] = f"https://www.healthspace.ca{href}"
                else:
                    restaurant['details_url'] = href

            restaurant['scraped_at'] = datetime.now().isoformat()

            if restaurant.get('name'):
                restaurants.append(restaurant)

        return restaurants

    def get_all_restaurants(self, max_pages=None):
        """
        Fetch all restaurants by paginating through results

        Args:
            max_pages: Maximum number of pages to fetch (None for all)

        Returns:
            List of all restaurant data
        """
        all_restaurants = []
        start = 0
        count = 30
        page = 0

        print("=" * 60)
        print("Fetching All Prince George Restaurants")
        print("=" * 60 + "\n")

        while True:
            if max_pages and page >= max_pages:
                print(f"Reached max_pages limit ({max_pages})")
                break

            print(f"\n--- Page {page + 1} ---")
            restaurants = self.get_restaurants(start=start, count=count)

            if restaurants is None:
                print("Error occurred, stopping pagination")
                break

            if not restaurants:
                print("No more data, stopping pagination")
                break

            print(f"Found {len(restaurants)} restaurants on this page")
            all_restaurants.extend(restaurants)

            # If we got fewer results than requested, we've reached the end
            if len(restaurants) < count:
                print("Got fewer results than requested - reached end")
                break

            start += count
            page += 1

            # Be respectful to the server
            time.sleep(2)

        print(f"\n{'=' * 60}")
        print(f"Total restaurants fetched: {len(all_restaurants)}")
        print(f"{'=' * 60}\n")

        return all_restaurants

    def save_to_json(self, data, filename='pg_restaurants.json'):
        """Save restaurant data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(data)} restaurants to {filename}")


def main():
    """Main function to fetch and display restaurant data"""
    api = HealthSpaceAPI()

    print("=" * 60)
    print("Prince George Restaurant Inspections")
    print("HealthSpace API Scraper")
    print("=" * 60 + "\n")

    # Fetch all restaurants
    all_restaurants = api.get_all_restaurants()  # Fetch all pages

    if all_restaurants:
        print("\n" + "=" * 60)
        print("RESTAURANT SUMMARY")
        print("=" * 60 + "\n")

        # Display first 10 restaurants
        for i, restaurant in enumerate(all_restaurants[:10], 1):
            print(f"{i}. {restaurant.get('name', 'N/A')}")
            print(f"   Address: {restaurant.get('address', 'N/A')}")
            print(f"   Last Inspection: {restaurant.get('last_inspection', 'N/A')}")
            if restaurant.get('details_url'):
                print(f"   Details: {restaurant['details_url']}")
            print()

        if len(all_restaurants) > 10:
            print(f"... and {len(all_restaurants) - 10} more restaurants\n")

        # Save to JSON
        api.save_to_json(all_restaurants, 'pg_restaurants.json')

        print(f"\n{'=' * 60}")
        print("Data saved to pg_restaurants.json")
        print(f"{'=' * 60}")
    else:
        print("\nFailed to fetch data.")
        print("\nPossible issues:")
        print("1. Site requires cookies/session from browser visit")
        print("2. WAF protection blocking automated requests")
        print("3. Need to solve CAPTCHA first")
        print("\nCheck healthspace_response.html for the actual HTML structure")


if __name__ == "__main__":
    main()
