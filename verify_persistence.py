import os

# Ensure required env vars BEFORE importing app (startup validates config).
os.environ["OPENROUTER_API_KEY"] = "test/dummy-key"
os.environ.setdefault("APP_BASE_URL", "http://localhost:8000")
os.environ.setdefault("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

from fastapi.testclient import TestClient
from main import app

def verify():
    with TestClient(app) as client:
        response = client.get("/")
        print(f"Status: {response.status_code}")

        # Check for presence of result headers
        if response.status_code == 200:
            html = response.text
            # We expect to see "Results Stream" and some content if runs exist
            if "Results Stream" in html:
                print("Found 'Results Stream' section.")

                # Check for at least one scenario title or run ID if we have files
                if 'class="scenario-title"' in html:
                    print("✅ SUCCESS: Found scenario titles in index page.")
                else:
                    # Fallback: maybe we have no runs?
                    # But ls showed runs. e.g. "nex-agi-deepseek..."
                    # Let's count how many we found
                    count = html.count('class="scenario-box"')
                    print(f"Found {count} result items.")

                    if count > 0:
                         print("✅ SUCCESS: Found result items (persistence working).")
                    else:
                         print("❌ FAILURE: No result items found in HTML.")
                         print("HTML Snapshot (partial):")
                         print(html[-1000:])
            else:
                 print("❌ FAILURE: 'Results Stream' header not found.")

if __name__ == "__main__":
    verify()
