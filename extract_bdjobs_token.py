"""
extract_bdjobs_token.py — Extract JWT token from BDJobs HAR file for CI use.

Run this on your PC after logging into BDJobs in your browser:
    python extract_bdjobs_token.py bdjobs_session.har

It will print the JWT, CompanyId, and EncryptId that you need to add
as GitHub secrets (BDJOBS_JWT, BDJOBS_COMPANY_ID, BDJOBS_ENCRYPT_ID).
"""
import base64
import json
import sys


def _decode_jwt_payload(token: str) -> dict:
    """Decode the payload section of a JWT (no signature verification)."""
    try:
        parts = token.split(".")
        if len(parts) >= 2:
            payload = parts[1]
            # Add padding if needed
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            decoded = base64.urlsafe_b64decode(payload)
            return json.loads(decoded)
    except Exception:
        pass
    return {}


def extract_from_har(har_path: str):
    with open(har_path, "r", encoding="utf-8") as f:
        har = json.load(f)

    token = company_id = encrypt_id = None

    for entry in har["log"]["entries"]:
        url = entry["request"]["url"]
        method = entry["request"]["method"]

        # Look for login API response
        if method == "POST" and "Login/Login" in url:
            body = entry["response"]["content"].get("text", "")
            if not body:
                continue
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                continue

            # Extract token from the nested structure
            event = data.get("event", {})
            event_data = event.get("eventData", [])
            for item in event_data:
                if isinstance(item, dict) and isinstance(item.get("value"), dict):
                    val = item["value"]
                    if "token" in val:
                        token = val.get("token")
                        encrypt_id = val.get("encryptId")
                        break

        # Look for SupportingData response to get CompanyId
        if method == "GET" and "SupportingData" in url:
            body = entry["response"]["content"].get("text", "")
            if body:
                import re
                m = re.search(r"ComNo=([^&;'\"\s]+)", body)
                if m:
                    company_id = m.group(1)

    # If CompanyId not found in HAR, try to extract from JWT payload
    if not company_id and token:
        payload = _decode_jwt_payload(token)
        company_id = payload.get("CompanyId")
        # Also try to get encryptId from JWT if not already found
        if not encrypt_id:
            # The CompanyCookie in JWT contains encryptId
            cookie_json = payload.get("CompanyCookie", "{}")
            try:
                cookie_data = json.loads(cookie_json) if isinstance(cookie_json, str) else cookie_json
                encrypt_id = cookie_data.get("ComUsrAcc")
            except Exception:
                pass

    return token, company_id, encrypt_id


if __name__ == "__main__":
    har_file = sys.argv[1] if len(sys.argv) > 1 else "bdjobs_session.har"

    print(f"Reading: {har_file}")
    token, company_id, encrypt_id = extract_from_har(har_file)

    print()
    print("=" * 70)
    if token:
        print("✅ JWT TOKEN FOUND")
        print(f"   Length: {len(token)} chars")
        print(f"   Preview: {token[:50]}...")
        print()
        print("   Add this as GitHub secret:  BDJOBS_JWT")
        print(f"   Value: {token}")
    else:
        print("❌ JWT token NOT found in HAR file.")
        print("   Make sure your HAR includes the Login/Login API request.")

    print()
    if company_id:
        print("✅ COMPANY ID FOUND")
        print(f"   Value: {company_id}")
        print()
        print("   Add this as GitHub secret:  BDJOBS_COMPANY_ID")
    else:
        print("❌ CompanyId NOT found.")
        print("   Make sure your HAR includes the SupportingData request.")

    print()
    if encrypt_id:
        print("✅ ENCRYPT ID FOUND")
        print(f"   Value: {encrypt_id}")
        print()
        print("   Add this as GitHub secret (optional):  BDJOBS_ENCRYPT_ID")
    else:
        print("⚠️  EncryptId not found (optional but recommended).")

    print("=" * 70)
    print()
    print("INSTRUCTIONS:")
    print("1. Go to: GitHub repo → Settings → Secrets and variables → Actions")
    print("2. Click 'New repository secret'")
    print("3. Add each secret name and value shown above")
    print("4. The workflow will use these tokens instead of logging in")
    print("   (avoids 'Invalid Credentials' from foreign IP addresses)")
    print()
    print("NOTE: The JWT token expires after some time.")
    print("      When workflows fail with 'Unauthorized', re-run this script")
    print("      after logging into BDJobs in your browser again.")
