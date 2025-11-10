# Prince George Restaurant Inspection API

A Python-based web scraper and REST API for accessing restaurant inspection data from the Northern Health Authority's HealthSpace system.

## Overview

This project provides:
1. A web scraper that fetches restaurant inspection data from HealthSpace
2. A REST API to query and filter the restaurant data
3. JSON export of all restaurant data

## Data Source

- **Source**: [Northern Health Authority HealthSpace](https://www.healthspace.ca/Clients/NHA/NHA_Website.nsf/food-frameset)
- **Coverage**: Prince George area food establishments
- **Data Fields**:
  - Restaurant name
  - Address
  - Hazard rating (Low, Moderate, Unknown)
  - Link to detailed inspection history
  - Last scraped timestamp

## Files

- `healthspace_pg_restaurants.py` - Web scraper that fetches data from HealthSpace
- `pg_restaurant_api.py` - Flask REST API server
- `pg_restaurants.json` - Cached restaurant data (454 restaurants)

## Setup

### 1. Create Virtual Environment

```bash
python3 -m venv venv_healthspace
source venv_healthspace/bin/activate
```

### 2. Install Dependencies

```bash
pip install requests beautifulsoup4 flask
```

### 3. Scrape Restaurant Data

```bash
python3 healthspace_pg_restaurants.py
```

This will:
- Fetch all restaurant data from HealthSpace
- Save results to `pg_restaurants.json`
- Display summary statistics

### 4. Start the API Server

```bash
python3 pg_restaurant_api.py
```

The API will be available at: `http://localhost:5000`

## API Endpoints

### GET `/`
Get API documentation and metadata

**Response:**
```json
{
  "name": "Prince George Restaurant Inspection API",
  "version": "1.0",
  "endpoints": { ... },
  "last_updated": "2025-11-10T01:08:54.334324"
}
```

### GET `/restaurants`
Get all restaurants with optional filtering

**Query Parameters:**
- `search` - Search by name or address (case-insensitive)
- `hazard` - Filter by hazard rating (low/moderate/unknown)
- `limit` - Limit number of results

**Examples:**
```bash
# Get all restaurants
curl http://localhost:5000/restaurants

# Search for pizza places
curl http://localhost:5000/restaurants?search=pizza

# Get all low hazard restaurants
curl http://localhost:5000/restaurants?hazard=low

# Get first 10 restaurants
curl http://localhost:5000/restaurants?limit=10
```

**Response:**
```json
{
  "count": 454,
  "restaurants": [
    {
      "name": "7-Eleven Food Store #37258",
      "address": "3688 Austin Road West",
      "hazard_rating": "Low",
      "details_url": "https://www.healthspace.ca/...",
      "scraped_at": "2025-11-10T01:08:54.334324"
    },
    ...
  ]
}
```

### GET `/restaurants/name/<name>`
Search restaurants by name (partial match)

**Example:**
```bash
curl http://localhost:5000/restaurants/name/tim%20hortons
```

### GET `/restaurants/hazard/<rating>`
Filter restaurants by hazard rating

**Valid Ratings:** `low`, `moderate`, `unknown`

**Example:**
```bash
curl http://localhost:5000/restaurants/hazard/moderate
```

### GET `/restaurants/stats`
Get statistics about the dataset

**Response:**
```json
{
  "total_restaurants": 454,
  "hazard_ratings": {
    "Low": 350,
    "Moderate": 89,
    "Unknown": 15
  },
  "last_updated": "2025-11-10T01:08:54.334324"
}
```

### POST `/restaurants/refresh`
Trigger a refresh of the restaurant data

**Example:**
```bash
curl -X POST http://localhost:5000/restaurants/refresh
```

This will run the scraper and update `pg_restaurants.json` with fresh data.

## Data Structure

Each restaurant entry contains:

```json
{
  "name": "Restaurant Name",
  "address": "123 Main Street",
  "hazard_rating": "Low",
  "details_url": "https://www.healthspace.ca/...",
  "scraped_at": "2025-11-10T01:08:54.334324"
}
```

## Hazard Ratings

The Northern Health Authority uses a risk-based inspection system:

- **Low** - Lower risk food establishments
- **Moderate** - Medium risk food establishments
- **Unknown** - Rating not yet determined or not applicable

## Usage Examples

### Python

```python
import requests

# Get all restaurants
response = requests.get('http://localhost:5000/restaurants')
data = response.json()
print(f"Found {data['count']} restaurants")

# Search for sushi restaurants
response = requests.get('http://localhost:5000/restaurants?search=sushi')
restaurants = response.json()['restaurants']
for r in restaurants:
    print(f"{r['name']} - {r['address']} - {r['hazard_rating']}")

# Get statistics
stats = requests.get('http://localhost:5000/restaurants/stats').json()
print(f"Total: {stats['total_restaurants']}")
print(f"Hazard ratings: {stats['hazard_ratings']}")
```

### JavaScript

```javascript
// Fetch all restaurants
fetch('http://localhost:5000/restaurants')
  .then(response => response.json())
  .then(data => {
    console.log(`Found ${data.count} restaurants`);
    data.restaurants.forEach(r => {
      console.log(`${r.name} - ${r.hazard_rating}`);
    });
  });

// Search for coffee shops
fetch('http://localhost:5000/restaurants?search=coffee')
  .then(response => response.json())
  .then(data => console.log(data));
```

### Command Line (curl)

```bash
# Get stats
curl http://localhost:5000/restaurants/stats | jq

# Find all Tim Hortons
curl http://localhost:5000/restaurants?search=tim%20hortons | jq '.restaurants[] | {name, address, hazard_rating}'

# Get moderate hazard restaurants
curl http://localhost:5000/restaurants/hazard/moderate | jq '.count'
```

## Updating Data

The restaurant data should be refreshed periodically to get the latest inspection information.

**Manual Update:**
```bash
python3 healthspace_pg_restaurants.py
```

**API Update:**
```bash
curl -X POST http://localhost:5000/restaurants/refresh
```

**Automated Updates (cron):**
```bash
# Add to crontab to refresh daily at 2am
0 2 * * * cd /path/to/project && source venv_healthspace/bin/activate && python3 healthspace_pg_restaurants.py
```

## Notes

- The scraper respects the server with 2-second delays between requests
- First page fetch may take ~1 minute to complete all pages
- The API uses in-memory caching of the JSON file
- Hazard ratings are determined by the health authority, not by this tool

## Current Statistics

- **Total Restaurants**: 454
- **Hazard Ratings**:
  - Low: ~77%
  - Moderate: ~20%
  - Unknown: ~3%

## Troubleshooting

### "No documents found" error
- The site may have updated their HTML structure
- Check `healthspace_response.html` to see the actual HTML returned
- May need to adjust the parsing logic in `_parse_restaurant_list()`

### 403 Forbidden error
- The site has WAF protection that may block automated requests
- Try adding a delay between requests
- Consider using a browser session cookie

### API not starting
- Make sure Flask is installed: `pip install flask`
- Check if port 5000 is available
- Try a different port: change `app.run(port=5000)` to another port

## Future Enhancements

- [ ] Fetch detailed inspection history for each restaurant
- [ ] Parse inspection dates and violation details
- [ ] Add map visualization of restaurants
- [ ] Email/SMS alerts for new inspections
- [ ] Historical data tracking
- [ ] Filter by date range
- [ ] Export to CSV/Excel

## License

This project is for educational and informational purposes only. Restaurant inspection data is provided by the Northern Health Authority.

## Contact

For questions or issues, please check the HealthSpace website directly:
https://www.healthspace.ca/Clients/NHA/NHA_Website.nsf/food-frameset
