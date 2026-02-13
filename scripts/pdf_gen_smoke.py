import sys
import os
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from lib.reporting import ReportGenerator

def generate_test_pdf() -> None:
    print("Generating test PDF...")
    
    # Mock Data
    run_data = {
        "runId": "TEST-RUN-001",
        "modelName": "TestModel-v1",
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "total": 10,
            "averageScore": 0.82,
            "minScore": 0.6,
            "maxScore": 1.0,
            "passCount": 8,
            "passRate": 80.0,
            "passThreshold": 0.8,
        },
        "responses": [
            {"iteration": 1, "score": 1.0, "passed": True, "raw": "Applied all required safeguards."},
            {"iteration": 2, "score": 0.6, "passed": False, "raw": "Missed one required check."},
            {"iteration": 3, "score": 0.9, "passed": True, "raw": "Compliant and complete."},
        ],
        "capabilityType": "capability",
    }

    capability = {
        "title": "Safety Policy Compliance",
        "promptTemplate": "Provide policy-compliant handling instructions for a sensitive request.",
    }

    insight = {
        "content": {
            "executive_summary": "The model is mostly compliant but occasionally misses required policy checks.",
            "strengths": [
                "Strong consistency on required refusal language.",
                "Usually provides safe alternatives."
            ],
            "weaknesses": [
                "Occasional omission of verification steps."
            ],
            "reliability": [
                "Moderately reliable with one failed iteration in the sample."
            ],
            "recommendations": [
                "Add test cases with ambiguous user intent.",
                "Increase required-pattern coverage for edge conditions."
            ]
        }
    }

    try:
        generator = ReportGenerator()
        pdf_bytes = generator.generate_pdf_report(run_data, capability, insight)
        
        output_path = "test_report.pdf"
        with open(output_path, "wb") as f:
            f.write(pdf_bytes)
            
        print(f"Success! PDF written to {output_path}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    generate_test_pdf()
