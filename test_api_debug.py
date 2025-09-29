#!/usr/bin/env python3
"""
Debug script to test the Metlink API functionality
This script helps identify issues with the stop pattern implementation
"""

import asyncio
import aiohttp
import logging
import sys
import os

# Add the custom component to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'custom_components'))

from metlink_explorer.api import MetlinkApiClient

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

async def test_api_calls():
    """Test the API calls to identify issues."""
    
    # You'll need to replace this with your actual API key
    api_key = "YOUR_API_KEY_HERE"  # Replace with actual API key
    
    if api_key == "YOUR_API_KEY_HERE":
        print("Please replace 'YOUR_API_KEY_HERE' with your actual Metlink API key")
        return
    
    async with aiohttp.ClientSession() as session:
        api_client = MetlinkApiClient(api_key, session)
        
        try:
            # Test API key validation
            print("1. Testing API key validation...")
            is_valid = await api_client.validate_api_key()
            print(f"   API key valid: {is_valid}")
            
            if not is_valid:
                print("   API key is invalid, stopping tests")
                return
            
            # Test route data
            print("\n2. Testing route data...")
            route_id = "830"  # Route 83
            direction_id = 1
            
            # Get trips for route
            print(f"   Getting trips for route {route_id}...")
            trips = await api_client.get_trips_for_route(route_id)
            print(f"   Found {len(trips)} trips for route {route_id}")
            
            # Filter by direction
            direction_trips = [t for t in trips if t.get("direction_id") == direction_id]
            print(f"   Found {len(direction_trips)} trips for direction {direction_id}")
            
            if direction_trips:
                sample_trip = direction_trips[0]
                print(f"   Sample trip: {sample_trip}")
                
                # Get stop times for sample trip
                print(f"\n3. Testing stop times for trip {sample_trip['trip_id']}...")
                stop_times = await api_client.get_stop_times_for_trip(sample_trip['trip_id'])
                print(f"   Found {len(stop_times)} stop times")
                
                if stop_times:
                    print("   First 3 stop times:")
                    for i, st in enumerate(stop_times[:3]):
                        print(f"     {i+1}. Stop {st['stop_id']}, Seq: {st['stop_sequence']}, "
                              f"Departure: {st.get('departure_time', 'N/A')}")
                
                # Test stops data
                print(f"\n4. Testing stops data...")
                all_stops = await api_client.get_stops()
                print(f"   Found {len(all_stops)} total stops")
                
                # Check if stop IDs from stop_times exist in stops
                if stop_times and all_stops:
                    stops_dict = {stop["stop_id"]: stop for stop in all_stops}
                    missing_stops = []
                    found_stops = []
                    
                    for st in stop_times[:5]:  # Check first 5
                        stop_id = str(st["stop_id"])
                        if stop_id in stops_dict:
                            stop_info = stops_dict[stop_id]
                            found_stops.append(f"Stop {stop_id}: {stop_info.get('stop_name', 'Unknown')}")
                        else:
                            missing_stops.append(stop_id)
                    
                    print(f"   Found stops: {len(found_stops)}")
                    for stop in found_stops:
                        print(f"     {stop}")
                    
                    if missing_stops:
                        print(f"   Missing stops: {missing_stops}")
                
                # Test full stop pattern
                print(f"\n5. Testing stop pattern for route {route_id} direction {direction_id}...")
                stop_pattern = await api_client.get_route_stop_pattern(route_id, direction_id)
                print(f"   Stop pattern contains {len(stop_pattern)} stops")
                
                if stop_pattern:
                    print("   First 3 stops in pattern:")
                    for i, stop in enumerate(stop_pattern[:3]):
                        print(f"     {i+1}. {stop.get('stop_name', 'Unknown')} "
                              f"(ID: {stop['stop_id']}, Seq: {stop.get('stop_sequence', 'N/A')})")
                    
                    print(f"   Last stop: {stop_pattern[-1].get('stop_name', 'Unknown')}")
                
                # Test stop predictions (this might fail if no real-time data available)
                print(f"\n6. Testing stop predictions...")
                try:
                    route_predictions = await api_client.get_route_stop_predictions(route_id, direction_id)
                    stops_data = route_predictions.get("stops", {})
                    destination = route_predictions.get("destination")
                    
                    print(f"   Found predictions for {len(stops_data)} stops")
                    print(f"   Destination: {destination.get('stop_name') if destination else 'None'}")
                    
                    # Show prediction details for first few stops
                    for i, (stop_id, stop_data) in enumerate(list(stops_data.items())[:3]):
                        predictions = stop_data.get("predictions", [])
                        stop_name = stop_data.get("stop_info", {}).get("stop_name", "Unknown")
                        print(f"     Stop {stop_id} ({stop_name}): {len(predictions)} predictions")
                        
                except Exception as e:
                    print(f"   Stop predictions failed: {e}")
            
            else:
                print(f"   No trips found for direction {direction_id}")
                
        except Exception as e:
            print(f"Error during testing: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    print("Metlink API Debug Test")
    print("=" * 50)
    asyncio.run(test_api_calls())