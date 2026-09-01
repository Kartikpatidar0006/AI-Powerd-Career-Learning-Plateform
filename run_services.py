"""
AI Career Hub — Microservices Launcher
Runs all microservices locally in detached background processes with valid log file handles.
"""

import os
import sys
import socket
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, ".logs")

SERVICES = [
    {"name": "Auth Service",         "dir": os.path.join(BASE_DIR, "services", "auth-service"),         "port": 8001},
    {"name": "Catalog Service",      "dir": os.path.join(BASE_DIR, "services", "catalog-service"),      "port": 8002},
    {"name": "Learning Service",     "dir": os.path.join(BASE_DIR, "services", "learning-service"),     "port": 8003},
    {"name": "Interview Service",    "dir": os.path.join(BASE_DIR, "services", "interview-service"),    "port": 8004},
    {"name": "Progress Service",     "dir": os.path.join(BASE_DIR, "services", "progress-service"),     "port": 8005},
    {"name": "Notification Service", "dir": os.path.join(BASE_DIR, "services", "notification-service"), "port": 8006},
    {"name": "Dashboard BFF",        "dir": os.path.join(BASE_DIR, "services", "dashboard-bff"),        "port": 8007},
    {"name": "API Gateway",          "dir": os.path.join(BASE_DIR, "gateway"),                       "port": 8000},
]

def is_port_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0

def start_services():
    os.makedirs(LOG_DIR, exist_ok=True)
    print("=" * 60)
    print("  Starting AI Career Hub Microservices")
    print("=" * 60)
    
    flags = 0
    if sys.platform == "win32":
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        flags = CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    
    for svc in SERVICES:
        name = svc["name"]
        folder = svc["dir"]
        port = svc["port"]
        
        if is_port_open(port):
            print(f"  [SKIP] {name:<20} - port {port} already in use")
            continue
            
        safe_name = name.replace(" ", "-")
        log_file_path = os.path.join(LOG_DIR, f"{safe_name}.log")
        log_file = open(log_file_path, "a", encoding="utf-8")
        
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port)],
            cwd=folder,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            creationflags=flags,
            close_fds=False if sys.platform == "win32" else True,
        )
        print(f"  [OK]   {name:<20} -> http://localhost:{port}")
        
    print("=" * 60)
    print("  All 8 services launched in background!")
    print("  API Gateway: http://localhost:8000")
    print("=" * 60)

def status_services():
    print("\n  Service Status:")
    print("  " + "=" * 48)
    for svc in SERVICES:
        name = svc["name"]
        port = svc["port"]
        if is_port_open(port):
            print(f"    [RUNNING]  {name:<20} -> http://localhost:{port}")
        else:
            print(f"    [STOPPED]  {name:<20} -> port {port}")
    print()

def kill_port(port: int):
    try:
        if sys.platform == "win32":
            output = subprocess.check_output(f"netstat -ano | findstr :{port}", shell=True).decode()
            pids = set()
            for line in output.strip().split("\n"):
                if "LISTENING" in line:
                    parts = line.strip().split()
                    pids.add(parts[-1])
            for pid in pids:
                subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
    except Exception:
        pass

def stop_services():
    print("\n  Stopping services on ports 8000-8007...")
    for svc in SERVICES:
        kill_port(svc["port"])
    print("  All services stopped.\n")

def dev_services():
    import time
    print("=" * 60)
    print("  Starting AI Career Hub Microservices in Interactive Mode")
    print("  Press Ctrl+C to stop all services.")
    print("=" * 60)
    
    processes = []
    try:
        for svc in SERVICES:
            name = svc["name"]
            folder = svc["dir"]
            port = svc["port"]
            
            if is_port_open(port):
                print(f"  [SKIP] {name:<20} - port {port} already in use")
                continue
                
            p = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", str(port), "--reload"],
                cwd=folder,
            )
            processes.append((name, p))
            print(f"  [OK]   {name:<20} -> http://localhost:{port}")
            
        print("=" * 60)
        print("  All services running. Press Ctrl+C to terminate.")
        print("=" * 60)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping all services...")
        for name, p in processes:
            p.terminate()
        for svc in SERVICES:
            kill_port(svc["port"])
        print("All services stopped.")

if __name__ == "__main__":
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "start"
    if action == "status":
        status_services()
    elif action == "stop":
        stop_services()
    elif action in ("dev", "--dev", "watch"):
        dev_services()
    else:
        start_services()

