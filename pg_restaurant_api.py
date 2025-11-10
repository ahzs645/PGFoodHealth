#!/usr/bin/env python3
"""
Simple Flask API for Prince George Restaurant Inspection Data
Serves the scraped HealthSpace data as a REST API
"""

from flask import Flask, jsonify, request
import json
import os
from datetime import datetime

app = Flask(__name__)

# Load restaurant data
def load_data():
    """Load restaurant data from JSON file"""
    if os.path.exists('pg_restaurants.json'):
        with open('pg_restaurants.json', 'r') as f:
            return json.load(f)
    return []

@app.route('/')
def home():
    """API documentation"""
    return jsonify({
        'name': 'Prince George Restaurant Inspection API',
        'version': '1.0',
        'endpoints': {
            '/restaurants': 'Get all restaurants',
            '/restaurants/<name>': 'Search restaurants by name (fuzzy match)',
            '/restaurants/hazard/<rating>': 'Filter by hazard rating (Low/Moderate/Unknown)',
            '/restaurants/stats': 'Get statistics about the dataset',
            '/restaurants/refresh': 'Trigger a refresh of the data (POST)'
        },
        'data_source': 'Northern Health Authority HealthSpace',
        'last_updated': get_last_updated()
    })

@app.route('/restaurants')
def get_restaurants():
    """Get all restaurants with optional filtering"""
    data = load_data()

    # Optional query parameters
    hazard = request.args.get('hazard')
    search = request.args.get('search')
    limit = request.args.get('limit', type=int)

    # Filter by hazard rating
    if hazard:
        data = [r for r in data if r.get('hazard_rating', '').lower() == hazard.lower()]

    # Search by name or address
    if search:
        search = search.lower()
        data = [r for r in data if
                search in r.get('name', '').lower() or
                search in r.get('address', '').lower()]

    # Limit results
    if limit:
        data = data[:limit]

    return jsonify({
        'count': len(data),
        'restaurants': data
    })

@app.route('/restaurants/name/<name>')
def search_by_name(name):
    """Search restaurants by name (partial match)"""
    data = load_data()
    name = name.lower()

    results = [r for r in data if name in r.get('name', '').lower()]

    return jsonify({
        'query': name,
        'count': len(results),
        'restaurants': results
    })

@app.route('/restaurants/hazard/<rating>')
def filter_by_hazard(rating):
    """Filter restaurants by hazard rating"""
    data = load_data()
    rating = rating.lower()

    results = [r for r in data if r.get('hazard_rating', '').lower() == rating]

    return jsonify({
        'hazard_rating': rating,
        'count': len(results),
        'restaurants': results
    })

@app.route('/restaurants/stats')
def get_stats():
    """Get statistics about the restaurant data"""
    data = load_data()

    # Count by hazard rating
    hazard_counts = {}
    for restaurant in data:
        rating = restaurant.get('hazard_rating', 'Unknown')
        hazard_counts[rating] = hazard_counts.get(rating, 0) + 1

    return jsonify({
        'total_restaurants': len(data),
        'hazard_ratings': hazard_counts,
        'last_updated': get_last_updated()
    })

@app.route('/restaurants/refresh', methods=['POST'])
def refresh_data():
    """Trigger a refresh of the restaurant data"""
    import subprocess

    try:
        # Run the scraper script
        result = subprocess.run(
            ['python3', 'healthspace_pg_restaurants.py'],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': 'Data refreshed successfully',
                'timestamp': datetime.now().isoformat()
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to refresh data',
                'error': result.stderr
            }), 500

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_last_updated():
    """Get the last updated timestamp from the JSON file"""
    if os.path.exists('pg_restaurants.json'):
        mtime = os.path.getmtime('pg_restaurants.json')
        return datetime.fromtimestamp(mtime).isoformat()
    return None

if __name__ == '__main__':
    port = 5001
    print("=" * 60)
    print("Prince George Restaurant Inspection API")
    print("=" * 60)
    print("\nStarting Flask server...")
    print(f"API will be available at: http://localhost:{port}")
    print("\nEndpoints:")
    print("  GET  /                              - API documentation")
    print("  GET  /restaurants                   - Get all restaurants")
    print("  GET  /restaurants?search=pizza      - Search restaurants")
    print("  GET  /restaurants?hazard=low        - Filter by hazard rating")
    print("  GET  /restaurants?limit=10          - Limit results")
    print("  GET  /restaurants/name/<name>       - Search by name")
    print("  GET  /restaurants/hazard/<rating>   - Filter by hazard")
    print("  GET  /restaurants/stats             - Get statistics")
    print("  POST /restaurants/refresh           - Refresh data")
    print("\n" + "=" * 60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=port)
