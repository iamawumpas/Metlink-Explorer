# Ferry Data Debug Log Guide

After these changes, check Home Assistant logs for `[FERRY]` tagged messages. Here's what to look for:

## Complete Flow:
```
[FERRY] Coordinator fetching AIS positions for route X
[FERRY] Coordinator got N positions from AIS for route X
[FERRY] AIS WebSocket connected
[FERRY] AIS subscription sent: {...}
[FERRY] AIS fetch complete: X messages received, Y position reports collected
[FERRY] Final registry after update: {mmsi: name, ...}
[FERRY] _normalize_ais_positions: route_id=X, Y input reports
[FERRY] Vessel registry has N MMSIs: [list]
[FERRY] After MMSI filtering: K/Y reports kept
```

## Debugging Checklist:

### 1. **Are AIS reports being received at all?**
   - Look for: `[FERRY] AIS fetch complete: X messages received`
   - If `X = 0` → **WebSocket may not be connecting or receiving**
   - Check the configured AIS API key validity

### 2. **Is the vessel registry populated?**
   - Look for: `[FERRY] Vessel registry has N MMSIs: [list]`
   - If `N = 0` → **No vessels configured or discovered**
   - Check config in Home Assistant GUI (did you add ferry MMSI/name pairs?)

### 3. **Are reports being filtered by MMSI?**
   - Look for: `[FERRY] After MMSI filtering: K/Y reports kept`
   - If `K < Y` → Some reports are being filtered (check MMSI list)
   - If `K = 0` → **All reports have MMSIs not in registry** (major issue!)
   - If `All reports filtered out!` warning → Report MMSIs don't match any configured vessels

### 4. **Are tracker entities being created?**
   - Check Home Assistant UI for `device_tracker.metlink_explorer_*` entities
   - If they exist but show `restored: true` → They were created but have no current data
   - If they don't exist → Check `device_tracker.py` extraction logic

### 5. **To enable debug logging in HA:**
   Add to `configuration.yaml`:
   ```yaml
   logger:
     logs:
       custom_components.metlink_explorer: DEBUG
   ```

### Expected Behavior When Working:
1. `[FERRY] AIS fetch complete: 50+ messages received, 3 position reports collected`
2. `[FERRY] Final registry after update: {'512010273': 'IKA RERE', '512003410': 'COBAR CAT', '512003252': 'CITY CAT'}`
3. `[FERRY] After MMSI filtering: 3/3 reports kept` (all 3 ferries found)

### Common Issues & Solutions:

| Issue | Log Evidence | Solution |
|-------|---|---|
| WebSocket not connecting | 0 messages received | Check AIS API key, network connectivity |
| Wrong MMSIs configured | All reports filtered out | Update MMSI list in HA options |
| Empty vessel registry | Vessel registry has 0 MMSIs | Configure ferries in HA integration options |
| No reports at all | 0 messages, 0 reports | Check if ferries are in Wellington Harbour bounding box |
