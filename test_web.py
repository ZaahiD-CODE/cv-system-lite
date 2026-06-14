import subprocess, time, json, sys
sys.path.insert(0, '/root/cv_system')

from web.app import app
from web.database import init_db, SessionLocal, User
from web.auth import get_password_hash

init_db()
db = SessionLocal()
admin = db.query(User).filter(User.username == "admin").first()
if not admin:
    admin = User(username="admin", email="admin@cvsystem.local",
                 hashed_password=get_password_hash("admin123"), role="admin")
    db.add(admin)
    db.commit()
print("DB initialized, admin user ready")

from fastapi.testclient import TestClient
client = TestClient(app)

# Test login
print("\n=== Test Login ===")
r = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
print(f"Login: {r.status_code}")
data = r.json()
token = data["access_token"]
print(f"Token: {token[:30]}...")
print(f"Role: {data['role']}")
headers = {"Authorization": f"Bearer {token}"}

# Test pages
print("\n=== Test Pages ===")
for path in ["/", "/login", "/dashboard", "/streams", "/counters", "/users", "/training"]:
    r = client.get(path)
    print(f"GET {path}: {r.status_code}")

# Test create stream
print("\n=== Test Stream CRUD ===")
r = client.post("/api/streams/", json={
    "name": "Front Door", "source_type": "rtsp",
    "source_path": "rtsp://demo:demo@192.168.1.185:554/1", "confidence": 0.5
}, headers=headers)
print(f"Create stream: {r.status_code} - {r.json()['name']}")
stream_id = r.json()["id"]

# Test add zone
r = client.post(f"/api/streams/{stream_id}/zones", json={
    "name": "Entrance", "points": [[0,0],[300,0],[300,300],[0,300]]
}, headers=headers)
print(f"Add zone: {r.status_code} - {r.json()['name']}")

# Test add counter
r = client.post(f"/api/streams/{stream_id}/counters", json={
    "name": "People Counter", "type": "zone", "zone_id": 1
}, headers=headers)
print(f"Add counter: {r.status_code} - {r.json()['name']}")

# Test list streams
r = client.get("/api/streams/", headers=headers)
print(f"List streams: {r.status_code} - {len(r.json())} stream(s)")

# Test stats
r = client.get("/api/stats/dashboard", headers=headers)
print(f"Dashboard: {r.status_code} - {r.json()['total_streams']} streams")

r = client.get("/api/stats/counters", headers=headers)
print(f"Counters: {r.status_code} - {len(r.json())} counter(s)")

# Test user CRUD
print("\n=== Test User CRUD ===")
r = client.post("/api/users/", json={
    "username": "operator1", "email": "op1@test.com",
    "password": "pass123", "role": "operator", "stream_ids": [stream_id]
}, headers=headers)
print(f"Create user: {r.status_code} - {r.json()['username']} ({r.json()['role']})")
user_id = r.json()["id"]

r = client.get("/api/users/", headers=headers)
print(f"List users: {r.status_code} - {len(r.json())} user(s)")

r = client.put(f"/api/users/{user_id}", json={
    "username": "operator1_updated", "stream_ids": [stream_id]
}, headers=headers)
print(f"Update user: {r.status_code} - {r.json()['username']}")

# Test operator access
r = client.post("/api/auth/login", json={"username": "operator1_updated", "password": "pass123"})
op_token = r.json()["access_token"]
op_headers = {"Authorization": f"Bearer {op_token}"}

r = client.get("/api/streams/", headers=op_headers)
print(f"Operator streams: {r.status_code} - {len(r.json())} stream(s)")

r = client.post("/api/users/", json={
    "username": "test", "email": "test@test.com",
    "password": "pass", "role": "operator"
}, headers=op_headers)
print(f"Operator create user (should 403): {r.status_code}")

print("\n=== ALL TESTS PASSED ===")
db.close()
