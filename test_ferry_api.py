#!/usr/bin/env python3
"""Standalone API test - no HA dependencies needed."""
import asyncio
import aiohttp
from datetime import datetime

async def test_apis():
    metlink_key = 'u1iDX1bw2z6IzMS1HDbGu9mZCuVqnRRMY6PHvDxg'
    ais_key = 'b59d07081036ae2296cd4a453628948def784ebe'
    
    print("\n" + "="*70)
    print("FERRY DATA AVAILABILITY CHECK")
    print("="*70 + "\n")
    
    async with aiohttp.ClientSession() as session:
        # Test 1: Metlink vehicle positions
        print("1. Metlink Vehicle Positions")
        print("-" * 70)
        try:
            async with session.get(
                'https://api.opendata.metlink.co.nz/gtfs-rt/vehiclepositions',
                headers={'x-api-key': metlink_key},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.read()
                print(f"   Status: {resp.status}")
                print(f"   Content-Type: {resp.headers.get('content-type', 'unknown')}")
                print(f"   Size: {len(data)} bytes")
                
                # Try to decode as text if possible
                try:
                    text = data.decode('utf-8', errors='ignore')
                    if 'ferry' in text.lower() or 'city cat' in text.lower() or 'CITY CAT' in text:
                        print("   ✓ Ferry data FOUND in response")
                        # Print relevant lines
                        for line in text.split('\n'):
                            if 'ferry' in line.lower() or 'cat' in line.lower():
                                print(f"     {line[:100]}")
                    else:
                        print("   ✗ No ferry data in vehicle positions response")
                except:
                    print("   (Response is binary protobuf format)")
                    
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Test 2: Trip updates
        print("\n2. Trip Updates")
        print("-" * 70)
        try:
            async with session.get(
                'https://api.opendata.metlink.co.nz/gtfs-rt/tripupdates',
                headers={'x-api-key': metlink_key},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.read()
                print(f"   Status: {resp.status}")
                print(f"   Size: {len(data)} bytes")
                print("   (Trip updates are for bus/train delays, not ferries)")
        except Exception as e:
            print(f"   ✗ Error: {e}")
        
        # Test 3: AIS websocket (basic connectivity check)
        print("\n3. AIS Stream (Ferry data source)")
        print("-" * 70)
        try:
            # AIS uses websocket, so just test connectivity
            async with session.get(
                'https://api.aisstream.io',
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                print(f"   AIS API Status: {resp.status}")
                if resp.status == 200:
                    print("   ✓ AIS API is reachable (websocket endpoint)")
                else:
                    print(f"   ⚠ Unexpected status from AIS API")
        except Exception as e:
            print(f"   ⚠ Error connecting to AIS API: {e}")
        
        print("\n" + "="*70)
        print("CONCLUSION")
        print("="*70)
        print("""
If Metlink vehicle positions are empty:
  • Ferry service may not be operating currently (check timing)
  • Or the Metlink GTFS-RT feed doesn't include ferry live updates
  • Action: Check the raw API response at:
    https://api.opendata.metlink.co.nz/gtfs-rt/vehiclepositions
    (include header: x-api-key: u1iDX1bw2z6IzMS1HDbGu9mZCuVqnRRMY6PHvDxg)

Your tracker entities show "restored: true" when there's no active GPS data.
Once data arrives, they'll have latitude, longitude, timestamp, etc.
        """)

if __name__ == '__main__':
    asyncio.run(test_apis())
