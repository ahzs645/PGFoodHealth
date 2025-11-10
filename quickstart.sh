#!/bin/bash
# Quick start script for Prince George Restaurant Inspection API

echo "======================================================================"
echo "Prince George Restaurant Inspection API - Quick Start"
echo "======================================================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv

    echo "📥 Installing dependencies..."
    source venv/bin/activate
    pip install -r requirements.txt
    echo ""
else
    echo "✅ Virtual environment already exists"
    source venv/bin/activate
    echo ""
fi

# Check if data file exists
if [ ! -f "pg_restaurants.json" ]; then
    echo "🔄 No data file found. Fetching restaurant data..."
    python3 healthspace_pg_restaurants.py
    echo ""
else
    echo "✅ Restaurant data file exists (pg_restaurants.json)"
    echo ""
fi

# Ask if user wants to start the API server
echo "======================================================================"
echo "Setup complete!"
echo "======================================================================"
echo ""
echo "Options:"
echo "  1. Start API server"
echo "  2. Refresh restaurant data"
echo "  3. Run example usage script"
echo "  4. Exit"
echo ""
read -p "Enter your choice (1-4): " choice

case $choice in
    1)
        echo ""
        echo "Starting API server..."
        python3 pg_restaurant_api.py
        ;;
    2)
        echo ""
        echo "Refreshing restaurant data..."
        python3 healthspace_pg_restaurants.py
        ;;
    3)
        echo ""
        echo "Running example usage script..."
        echo "Note: Make sure API server is running in another terminal"
        python3 example_api_usage.py
        ;;
    4)
        echo "Exiting..."
        ;;
    *)
        echo "Invalid choice"
        ;;
esac
