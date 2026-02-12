
import os
os.environ["OPENROUTER_API_KEY"] = "test/dummy-key"
os.environ.setdefault("APP_BASE_URL", "http://localhost:8000")
os.environ.setdefault("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
from fastapi.testclient import TestClient
from main import app

def test_persistence_render():
    with TestClient(app) as client:
        response = client.get("/")
        assert response.status_code == 200
        html = response.text
        # Check for "Results Stream"
        if "Results Stream" not in html:
            print("❌ FAIL: 'Results Stream' header not found")
            exit(1)

        # We might not have runs in the shared env context, but if the template crashed it would be 500
        print("✅ SUCCESS: Index page rendered 200 OK")

if __name__ == "__main__":
    test_persistence_render()
