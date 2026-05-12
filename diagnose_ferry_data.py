#!/usr/bin/env python3
"""
Diagnostic script to check if ferry data is available through Metlink API and AIS.
Run this with your API keys to see what data is actually being returned.
"""

import asyncio
import aiohttp
import logging
import sys
import os
from datetime import datetime

# Add the custom component to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'custom_components'))

from metlink_explorer.api import MetlinkApiClient

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

async def diagnose():
    """Run diagnostics on ferry data availability."""
    
    # Get API keys from environment or prompt user
    metlink_key = os.environ.get('METLINK_API_KEY', '').strip()
    ais_key = os.environ.get('AIS_API_KEY', '').strip()
    
    if not metlink_key:
        metlink_key = input("Enter your Metlink API key: ").strip()
    if not metlink_key:
        print("ERROR: Metlink API key required")
        return
    
    print(f"\n{'='*70}")
    print("FERRY DATA DIAGNOSTICS")
    print(f"{'='*70}\n")
    
    async with aiohttp.ClientSession() as session:
        # Initialize API client
        api_client = MetlinkApiClient(
            api_key=metlink_key,
            session=session,
            transportation_type=4,  # Ferry
            ais_api_key=ais_key or None,
            ais_vessel_map={
                "512010273": "IKA RERE",
                "512003410": "COBAR CAT",
                "512003252": "CITY CAT"
            }
        )
        
        # 1. Check API key validity
        print("1. Validating Metlink API key...")
        try:
            is_valid = await api_client.validate_api_key()
            print(f"   ✓ API key valid: {is_valid}\n" if is_valid else "   ✗ API key invalid\n")
            if not is_valid:
                return
        except Exception as e:
            print(f"   ✗ Error validating API key: {e}\n")
            return
        
        # 2. Check vehicle positions from GTFS-RT
        print("2. Checking Metlink vehicle positions (GTFS-RT)...")
        try:
            positions = await api_client.get_vehicle_positions()
            print(f"   ✓ Got {len(positions)} vehicle positions")
            
            # Count by transport type
            by_type = {}
            for pos in positions:
                label = pos.get('vehicle_label', 'unknown')
                route_id = pos.get('route_id', 'unknown')
                by_type[label] = by_type.get(label, 0) + 1
            
            for label, count in sorted(by_type.items()):
                print(f"     - {label}: {count}")
            
            # Look for ferry-like vehicles
            ferries = [p for p in positions if 'ferry' in p.get('vehicle_label', '').lower() 
                      or 'IKA RERE' in str(p.get('vehicle', {})).upper()
                      or 'COBAR CAT' in str(p.get('vehicle', {})).upper()
                      or 'CITY CAT' in str(p.get('vehicle', {})).upper()]
            
            if ferries:
                print(f"\n   Found {len(ferries)} ferry-like entries:")
                for f in ferries[:3]:  # Show first 3
                    print(f"     {f}")
            else:
                print(f"   ✗ No ferry entries found in vehicle positions\n")
        except Exception as e:
            print(f"   ✗ Error fetching vehicle positions: {e}\n")
        
        # 3. Check AIS positions if key available
        if ais_key:
            print("3. Checking AIS stream (ferries)...")
            try:
                ais_positions = await api_client.get_ferry_ais_positions("8")  # Ferry route 8
                print(f"   ✓ Got {len(ais_positions)} AIS positions for route 8 (QDF)")
                
                if ais_positions:
                    for pos in ais_positions[:3]:  # Show first 3
                        print(f"     {pos.get('vehicle_id', 'unknown')}: "
                              f"({pos.get('latitude')}, {pos.get('longitude')}) "
                              f"timestamp={pos.get('timestamp')}")
                else:
                    print(f"   ✗ No AIS positions returned for ferries\n")
            except Exception as e:
                print(f"   ✗ Error fetching AIS positions: {e}\n")
        else:
            print("3. AIS stream check skipped (no AIS_API_KEY)\n")
        
        # 4. Check trip updates
        print("4. Checking trip updates (realtime delays/cancellations)...")
        try:
            updates = await api_client.get_trip_updates()
            print(f"   ✓ Got {len(updates)} trip update records")
            
            # Look for ferry-related updates
            if updates:
                print(f"   (Trip updates are mostly for buses/trains; ferries use AIS instead)\n")
        except Exception as e:
            print(f"   ✗ Error fetching trip updates: {e}\n")
        
        # 5. Check last fetch timestamp
        print("5. Last data fetch timestamps...")
        fetched_at = api_client.vehicle_positions_fetched_at()
        if fetched_at:
            age_seconds = (datetime.now() - fetched_at).total_seconds()
            print(f"   Vehicle positions fetched {age_seconds:.1f}s ago at {fetched_at}")
        else:
            print(f"   Vehicle positions: never fetched")
        
        print(f"\n{'='*70}")
        print("INTERPRETATION:")
        print(f"{'='*70}\n")
        
        print("• If Metlink vehicle positions are empty or have no ferries:")
        print("  → Ferry data source may be experiencing an outage")
        print("  → Check https://api.opendata.metlink.co.nz/gtfs-rt/vehiclepositions\n")
        
        print("• If AIS positions are empty or error:")
        print("  → AIS API key may be invalid or ferries not in Wellington Harbour")
        print("  → Check https://api.aisstream.io/ for websocket connectivity\n")
        
        print("• If timestamps are old (> 120s):")
        print("  → Data is stale; check if coordinator is actually polling\n")
        
        print("Home Assistant device_tracker entities will show 'restored: true' until")
        print("fresh data arrives. Check the coordinator logs in HA for actual errors.")

if __name__ == "__main__":
    asyncio.run(diagnose())
