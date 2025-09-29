# Metlink Explorer Stop Pattern Bug Fix - Troubleshooting Guide

## Problem Summary
The integration is not populating stop pattern data. All stop-related attributes show empty values:
- `destination_stop`: null
- `total_stops`: 0
- `stops_with_predictions`: 0
- `all_stops`: []
- `next_departures`: []

## Applied Fixes

### 1. Enhanced API Client (`api.py`)
- **Improved route ID matching**: Now handles both string and integer comparisons
- **Better error handling**: Added comprehensive logging at each step
- **String normalization**: Ensures stop_id comparisons work correctly
- **Enhanced debugging**: Added detailed logging to track data flow

### 2. Enhanced Sensor Logic (`sensor.py`)
- **Fallback mechanism**: Uses scheduled GTFS times when real-time predictions aren't available
- **Better error handling**: Validates data structures before processing
- **Enhanced attributes**: Added more debugging information and scheduled departure times
- **Improved logging**: Added route-specific debug information

### 3. Enhanced Debugging
- **Debug script**: Created `test_api_debug.py` to test API functionality independently
- **Logging configuration**: Created `debug_logging.yaml` for Home Assistant debug logging

## Debugging Steps

### Step 1: Enable Debug Logging
Add to your `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.metlink_explorer: debug
```

### Step 2: Check Home Assistant Logs
After restarting HA, look for debug messages like:
- "Getting trips for route 830"
- "Found X trips for route 830 out of Y total trips"
- "Getting stop pattern for route 830 direction 1"
- "Built stop pattern with X stops"

### Step 3: Verify API Data Structure
The debug logs should show:
1. **Trip Count**: How many trips were found for your route
2. **Stop Times**: How many stop times were found for the sample trip
3. **Stop Pattern**: How many stops were built in the final pattern

### Step 4: Check Entity Attributes
Look for the new `debug_info` attribute which shows:
- `coordinator_data_keys`: Should include "route_stops"
- `route_stops_keys`: Should include "stops", "destination", "stop_count"
- `stops_data_count`: Should show number of stops processed

## Potential Issues and Solutions

### Issue 1: No Trips Found
**Symptoms**: "Found 0 trips for route 830"
**Cause**: Route ID mismatch between integration and API
**Solution**: 
- Check if API uses different route identifiers
- Verify route exists in current GTFS data
- Route might be seasonal or temporarily suspended

### Issue 2: No Stop Times Found
**Symptoms**: "Found 0 stop times for trip X"
**Cause**: Trip ID doesn't exist in stop_times data
**Solution**:
- Trip might be from old GTFS data
- API might have data synchronization issues
- Try different trip from the list

### Issue 3: Stop ID Mismatches
**Symptoms**: "Stop X not found in stops dictionary"
**Cause**: stop_id format differences (string vs integer)
**Solution**: Fixed with string normalization in the code

### Issue 4: No Real-time Predictions
**Symptoms**: Stop pattern loads but no predictions
**Cause**: Real-time API might be down or route not active
**Solution**: 
- Integration now falls back to scheduled times from GTFS
- Check if route is currently running
- Verify stop-predictions API endpoint

## Expected Results After Fix

With the fixes applied, you should see:

1. **Populated stop list**: `all_stops` should contain all stops on the route
2. **Destination identified**: `destination_stop` should show the final stop
3. **Stop count**: `total_stops` should show correct number of stops
4. **Mixed data sources**: 
   - `stops_with_predictions`: Stops with real-time data
   - `stops_with_scheduled`: Stops with GTFS scheduled times
5. **Departure information**: Either real-time predictions or scheduled times

## Testing the Fix

1. Restart Home Assistant
2. Wait for next update cycle (60 seconds by default)
3. Check Developer Tools > States for your entity
4. Look for populated `all_stops` array with stop information
5. Check `debug_info` for troubleshooting information

## Manual Testing (Optional)

You can test the API calls independently:
1. Edit `test_api_debug.py` with your API key
2. Run: `python test_api_debug.py`
3. This will test each API call step by step

The fix addresses the core issues of data type mismatches and provides comprehensive fallback mechanisms to ensure you get stop pattern information even when real-time predictions aren't available.