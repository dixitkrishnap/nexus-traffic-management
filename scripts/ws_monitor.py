"""
scripts/ws_monitor.py

Real-time WebSocket terminal monitor.
Displays live traffic updates as they arrive from the backend.

Run: python scripts/ws_monitor.py
"""

import asyncio
import json
import websockets
from datetime import datetime

WS_URL = "ws://localhost:8000/api/traffic/ws"

CYAN  = "\033[96m"; GREEN = "\033[92m"; YELLOW = "\033[93m"
RED   = "\033[91m"; BOLD  = "\033[1m";  DIM    = "\033[2m"; RESET = "\033[0m"

def status_color(st):
    return RED if st=="critical" else YELLOW if st=="warning" else GREEN

def clear_line():
    print("\033[2K\033[1G", end="")

async def monitor():
    print(f"\n{BOLD}NEXUS WebSocket Monitor — {WS_URL}{RESET}")
    print(f"{DIM}Ctrl+C to stop{RESET}\n")

    async with websockets.connect(WS_URL) as ws:
        print(f"{GREEN}✔ Connected{RESET}\n")
        frame = 0
        async for raw in ws:
            data = json.loads(raw)
            t    = datetime.now().strftime("%H:%M:%S")

            if data["type"] == "state_update":
                m = data.get("metrics", {})
                zones = data.get("zones", [])
                frame += 1

                # Header line
                print(f"\r{BOLD}[{t}] frame {frame:04d}{RESET}  "
                      f"vehicles={CYAN}{m.get('total_vehicles','?'):,}{RESET}  "
                      f"eff={GREEN}{m.get('flow_efficiency','?')}%{RESET}  "
                      f"incidents={RED}{m.get('active_incidents','?')}{RESET}  "
                      f"signals={m.get('adaptive_signals','?')}/12 adaptive")

                # Show top 3 congested zones
                top3 = sorted(zones, key=lambda z: -z.get("congestion", 0))[:3]
                for z in top3:
                    c   = z.get("congestion", 0)
                    col = status_color(z.get("status","normal"))
                    bar = "█" * int(c * 20)
                    print(f"  {z['zone_id']:<5} {z['name']:<26} "
                          f"{col}{bar:<20}{RESET} {round(c*100):>3}%  "
                          f"{z.get('speed_ms',0):.1f}m/s")
                print()

            elif data["type"] == "emergency":
                inc = data.get("payload", {})
                print(f"\n{RED}{BOLD}⚠ EMERGENCY: {inc.get('emergency_type','').upper()}{RESET}  "
                      f"corridor={inc.get('corridor',[])}  eta={inc.get('eta_min','?')}min\n")

            elif data["type"] == "emergency_cleared":
                print(f"\n{GREEN}{BOLD}✔ EMERGENCY CLEARED — adaptive control restored{RESET}\n")

            elif data["type"] == "alert":
                a = data.get("payload", {})
                col = RED if a.get("level")=="critical" else YELLOW if a.get("level")=="warning" else GREEN
                print(f"{col}[ALERT]{RESET} {a.get('message','')}")

            elif data["type"] == "ping":
                pass  # silent heartbeat


if __name__ == "__main__":
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print(f"\n{DIM}Monitor stopped.{RESET}")
    except Exception as e:
        print(f"\n{RED}Error: {e}{RESET}")
        print(f"{DIM}Make sure the server is running: uvicorn main:app --reload{RESET}")
