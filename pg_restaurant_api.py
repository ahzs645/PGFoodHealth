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
        'version': '2.0',
        'endpoints': {
            '/restaurants': 'Get all restaurants',
            '/restaurants/<name>': 'Search restaurants by name (fuzzy match)',
            '/restaurants/hazard/<rating>': 'Filter by hazard rating (Low/Moderate/Unknown)',
            '/restaurants/stats': 'Get statistics about the dataset',
            '/restaurants/refresh': 'Trigger a refresh of the data (POST)',
            '/restaurants/refresh-deep': 'Trigger deep refresh with inspections & violations (POST)',
            '/restaurant/<name>': 'Get single restaurant with full inspection history',
            '/inspections': 'Get all inspections across all restaurants',
            '/inspections/recent': 'Get most recent inspections',
            '/violations': 'Get all violations across all restaurants',
            '/violations/stats': 'Get violation statistics',
            '/search/live?q=<query>': 'Search live HealthSpace site (not cached)',
            '/search/live?q=<query>&details=true': 'Search live with full inspection details',
            '/restaurant/<name>/fetch': 'Fetch fresh data for a restaurant from live site',
            '/cities': 'List all cities in Northern Health',
            '/cities/<city>/restaurants': 'Get restaurants for a specific city (live fetch)'
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

@app.route('/restaurants/refresh-deep', methods=['POST'])
def refresh_data_deep():
    """Trigger a deep refresh that fetches all inspection details and violations"""
    import subprocess

    # Get optional parameters
    max_restaurants = request.args.get('max_restaurants', type=int)

    try:
        # Build command with optional limits
        cmd = ['python3', '-c', '''
import sys
sys.path.insert(0, ".")
from healthspace_pg_restaurants import HealthSpaceAPI
api = HealthSpaceAPI()
data = api.get_all_restaurants_with_details(max_restaurants={max_restaurants}, max_inspections_per_restaurant=None)
if data:
    api.save_to_json(data, "pg_restaurants.json")
    print(f"Saved {{len(data)}} restaurants with full details")
else:
    print("Failed to fetch data")
    sys.exit(1)
'''.format(max_restaurants=max_restaurants if max_restaurants else 'None')]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout for deep refresh
        )

        if result.returncode == 0:
            return jsonify({
                'status': 'success',
                'message': 'Deep refresh completed - data includes inspections and violations',
                'timestamp': datetime.now().isoformat(),
                'output': result.stdout
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Failed to refresh data',
                'error': result.stderr
            }), 500

    except subprocess.TimeoutExpired:
        return jsonify({
            'status': 'error',
            'message': 'Deep refresh timed out (1 hour limit)'
        }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/restaurant/<name>')
def get_restaurant(name):
    """Get a single restaurant with full inspection history"""
    data = load_data()
    name_lower = name.lower()

    # Find exact or closest match
    exact_match = None
    partial_matches = []

    for r in data:
        r_name = r.get('name', '').lower()
        if r_name == name_lower:
            exact_match = r
            break
        elif name_lower in r_name:
            partial_matches.append(r)

    if exact_match:
        return jsonify({
            'found': True,
            'restaurant': exact_match
        })
    elif partial_matches:
        if len(partial_matches) == 1:
            return jsonify({
                'found': True,
                'restaurant': partial_matches[0]
            })
        else:
            return jsonify({
                'found': False,
                'message': f'Multiple matches found for "{name}"',
                'matches': [r.get('name') for r in partial_matches]
            })
    else:
        return jsonify({
            'found': False,
            'message': f'No restaurant found matching "{name}"'
        }), 404

@app.route('/inspections')
def get_all_inspections():
    """Get all inspections across all restaurants"""
    data = load_data()

    # Query parameters
    inspection_type = request.args.get('type')  # e.g., "Routine"
    hazard = request.args.get('hazard')
    has_violations = request.args.get('has_violations')
    limit = request.args.get('limit', type=int)

    all_inspections = []

    for restaurant in data:
        inspections = restaurant.get('inspections', [])
        for insp in inspections:
            # Add restaurant info to each inspection
            inspection_data = {
                'restaurant_name': restaurant.get('name'),
                'restaurant_address': restaurant.get('address'),
                **insp
            }
            all_inspections.append(inspection_data)

    # Filter by inspection type
    if inspection_type:
        all_inspections = [i for i in all_inspections
                          if inspection_type.lower() in i.get('type', '').lower() or
                          inspection_type.lower() in i.get('inspection_type', '').lower()]

    # Filter by hazard rating
    if hazard:
        all_inspections = [i for i in all_inspections
                          if hazard.lower() == i.get('hazard_rating', '').lower()]

    # Filter by has violations
    if has_violations:
        has_viol = has_violations.lower() == 'true'
        all_inspections = [i for i in all_inspections
                          if (len(i.get('violations', [])) > 0) == has_viol]

    # Sort by date (most recent first)
    def parse_date(insp):
        date_str = insp.get('inspection_date') or insp.get('date', '')
        try:
            # Try different date formats
            for fmt in ['%B %d, %Y', '%d-%b-%Y', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except:
            pass
        return datetime.min

    all_inspections.sort(key=parse_date, reverse=True)

    # Limit results
    if limit:
        all_inspections = all_inspections[:limit]

    return jsonify({
        'count': len(all_inspections),
        'inspections': all_inspections
    })

@app.route('/inspections/recent')
def get_recent_inspections():
    """Get most recent inspections"""
    limit = request.args.get('limit', default=20, type=int)

    data = load_data()
    all_inspections = []

    for restaurant in data:
        inspections = restaurant.get('inspections', [])
        for insp in inspections:
            inspection_data = {
                'restaurant_name': restaurant.get('name'),
                'restaurant_address': restaurant.get('address'),
                **insp
            }
            all_inspections.append(inspection_data)

    # Sort by date (most recent first)
    def parse_date(insp):
        date_str = insp.get('inspection_date') or insp.get('date', '')
        try:
            for fmt in ['%B %d, %Y', '%d-%b-%Y', '%Y-%m-%d']:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except:
            pass
        return datetime.min

    all_inspections.sort(key=parse_date, reverse=True)

    return jsonify({
        'count': min(limit, len(all_inspections)),
        'inspections': all_inspections[:limit]
    })

@app.route('/violations')
def get_all_violations():
    """Get all violations across all restaurants"""
    data = load_data()

    # Query parameters
    code = request.args.get('code')
    critical = request.args.get('critical')
    search = request.args.get('search')
    limit = request.args.get('limit', type=int)

    all_violations = []

    for restaurant in data:
        for insp in restaurant.get('inspections', []):
            for violation in insp.get('violations', []):
                violation_data = {
                    'restaurant_name': restaurant.get('name'),
                    'restaurant_address': restaurant.get('address'),
                    'inspection_date': insp.get('inspection_date') or insp.get('date'),
                    'inspection_type': insp.get('inspection_type') or insp.get('type'),
                    **violation
                }
                all_violations.append(violation_data)

    # Filter by violation code
    if code:
        all_violations = [v for v in all_violations if v.get('code') == code]

    # Filter by critical (check if code indicates critical - codes < 200 are typically critical)
    if critical:
        is_critical = critical.lower() == 'true'
        def is_critical_violation(v):
            try:
                code_num = int(v.get('code', '999'))
                return code_num < 200
            except ValueError:
                return False
        all_violations = [v for v in all_violations
                          if is_critical_violation(v) == is_critical]

    # Search in description/observation
    if search:
        search = search.lower()
        all_violations = [v for v in all_violations
                          if search in v.get('description', '').lower() or
                          search in v.get('observation', '').lower() or
                          search in v.get('corrective_action', '').lower()]

    # Limit results
    if limit:
        all_violations = all_violations[:limit]

    return jsonify({
        'count': len(all_violations),
        'violations': all_violations
    })

@app.route('/search/live')
def search_live():
    """Search the live HealthSpace site for restaurants (not cached data)"""
    query = request.args.get('q')
    fetch_details = request.args.get('details', 'false').lower() == 'true'

    if not query:
        return jsonify({
            'error': 'Missing required parameter: q'
        }), 400

    try:
        from healthspace_pg_restaurants import HealthSpaceAPI
        api = HealthSpaceAPI()

        results = api.search_restaurants(query)

        if results is None:
            return jsonify({
                'error': 'Failed to search HealthSpace site'
            }), 500

        # Optionally fetch full details for each result
        if fetch_details and results:
            for restaurant in results:
                api.get_restaurant_full_details(
                    restaurant,
                    fetch_inspections=True,
                    max_inspections=5  # Limit to last 5 inspections
                )

        return jsonify({
            'query': query,
            'count': len(results),
            'include_details': fetch_details,
            'restaurants': results,
            'source': 'live'
        })

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/restaurant/<name>/fetch')
def fetch_restaurant_live(name):
    """Fetch fresh data for a specific restaurant from the live HealthSpace site"""
    try:
        from healthspace_pg_restaurants import HealthSpaceAPI
        api = HealthSpaceAPI()

        # First search for the restaurant
        results = api.search_restaurants(name)

        if not results:
            return jsonify({
                'found': False,
                'message': f'No restaurant found matching "{name}" on live site'
            }), 404

        # If multiple matches, let user know
        if len(results) > 1:
            exact_match = None
            for r in results:
                if r.get('name', '').lower() == name.lower():
                    exact_match = r
                    break

            if not exact_match:
                return jsonify({
                    'found': False,
                    'message': f'Multiple matches found for "{name}"',
                    'matches': [r.get('name') for r in results]
                })

            results = [exact_match]

        # Fetch full details for the restaurant
        restaurant = results[0]
        api.get_restaurant_full_details(
            restaurant,
            fetch_inspections=True,
            max_inspections=None  # Get all inspections
        )

        return jsonify({
            'found': True,
            'restaurant': restaurant,
            'source': 'live'
        })

    except Exception as e:
        return jsonify({
            'error': str(e)
        }), 500

@app.route('/cities')
def get_cities():
    """Get list of all cities in Northern Health"""
    try:
        from healthspace_pg_restaurants import HealthSpaceAPI
        cities = HealthSpaceAPI.get_cities()
        return jsonify({
            'count': len(cities),
            'cities': cities
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/cities/<city>/restaurants')
def get_city_restaurants(city):
    """Fetch restaurants for a specific city from the live HealthSpace site"""
    fetch_details = request.args.get('details', 'false').lower() == 'true'
    max_inspections = request.args.get('max_inspections', type=int, default=3)

    try:
        from healthspace_pg_restaurants import HealthSpaceAPI

        # Check if city is valid
        if city not in HealthSpaceAPI.CITIES:
            # Try case-insensitive match
            city_match = None
            for c in HealthSpaceAPI.CITIES.keys():
                if c.lower() == city.lower():
                    city_match = c
                    break

            if not city_match:
                return jsonify({
                    'error': f'Unknown city: {city}',
                    'available_cities': HealthSpaceAPI.get_cities()
                }), 404

            city = city_match

        api = HealthSpaceAPI(city=city)

        if fetch_details:
            restaurants = api.get_all_restaurants_with_details(
                max_inspections_per_restaurant=max_inspections
            )
        else:
            restaurants = api.get_all_restaurants()

        if restaurants:
            # Add city to each restaurant
            for r in restaurants:
                r['city'] = city

            return jsonify({
                'city': city,
                'count': len(restaurants),
                'include_details': fetch_details,
                'restaurants': restaurants,
                'source': 'live'
            })
        else:
            return jsonify({
                'city': city,
                'count': 0,
                'restaurants': [],
                'message': 'No restaurants found or error fetching data'
            })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/violations/stats')
def get_violation_stats():
    """Get statistics about violations"""
    data = load_data()

    # Count violations by code
    code_counts = {}
    total_violations = 0
    restaurants_with_violations = set()
    corrected_during_inspection = 0

    for restaurant in data:
        has_violation = False
        for insp in restaurant.get('inspections', []):
            for violation in insp.get('violations', []):
                total_violations += 1
                has_violation = True

                code = violation.get('code', 'Unknown')
                if code not in code_counts:
                    code_counts[code] = {
                        'count': 0,
                        'description': violation.get('description', '')
                    }
                code_counts[code]['count'] += 1

                if violation.get('corrected_during_inspection'):
                    corrected_during_inspection += 1

        if has_violation:
            restaurants_with_violations.add(restaurant.get('name'))

    # Sort by count
    sorted_codes = sorted(code_counts.items(), key=lambda x: x[1]['count'], reverse=True)

    return jsonify({
        'total_violations': total_violations,
        'restaurants_with_violations': len(restaurants_with_violations),
        'corrected_during_inspection': corrected_during_inspection,
        'top_violation_codes': [
            {'code': code, 'count': info['count'], 'description': info['description']}
            for code, info in sorted_codes[:10]
        ],
        'all_violation_codes': {code: info['count'] for code, info in sorted_codes}
    })

def get_last_updated():
    """Get the last updated timestamp from the JSON file"""
    if os.path.exists('pg_restaurants.json'):
        mtime = os.path.getmtime('pg_restaurants.json')
        return datetime.fromtimestamp(mtime).isoformat()
    return None

if __name__ == '__main__':
    port = 5001
    print("=" * 60)
    print("Prince George Restaurant Inspection API v2.0")
    print("=" * 60)
    print("\nStarting Flask server...")
    print(f"API will be available at: http://localhost:{port}")
    print("\nEndpoints:")
    print("  GET  /                              - API documentation")
    print("  GET  /restaurants                   - Get all restaurants")
    print("  GET  /restaurants?search=pizza      - Search restaurants")
    print("  GET  /restaurants?hazard=low        - Filter by hazard rating")
    print("  GET  /restaurants/name/<name>       - Search by name")
    print("  GET  /restaurants/hazard/<rating>   - Filter by hazard")
    print("  GET  /restaurants/stats             - Get statistics")
    print("  POST /restaurants/refresh           - Refresh data (basic)")
    print("  POST /restaurants/refresh-deep      - Refresh with inspections & violations")
    print("")
    print("  GET  /restaurant/<name>             - Get single restaurant with inspections")
    print("  GET  /inspections                   - Get all inspections")
    print("  GET  /inspections?has_violations=true - Filter inspections")
    print("  GET  /inspections/recent            - Get most recent inspections")
    print("  GET  /violations                    - Get all violations")
    print("  GET  /violations?search=temperature - Search violations")
    print("  GET  /violations/stats              - Get violation statistics")
    print("")
    print("  Live Data (fetches from HealthSpace directly):")
    print("  GET  /search/live?q=pizza           - Search live site")
    print("  GET  /search/live?q=pizza&details=true - With full details")
    print("  GET  /restaurant/<name>/fetch       - Fetch fresh restaurant data")
    print("\n" + "=" * 60 + "\n")

    app.run(debug=True, host='0.0.0.0', port=port)
