#!/usr/bin/env python3
"""
LinkedIn Session Verification Script

Verifies that the LinkedIn authentication session was successfully saved
to disk and is ready for authenticated scraping.

Usage:
    python scripts/verify_linkedin_session.py
"""

import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def verify_linkedin_session():
    """Verify if LinkedIn session was saved successfully."""
    
    # Define session directory
    base_dir = Path(__file__).parent.parent
    session_dir = base_dir / "browser_data" / "linkedin_profile"
    
    print("LinkedIn Session Verification")
    print("=" * 50)
    print(f"Session directory: {session_dir}")
    print()
    
    # Check if directory exists
    if not session_dir.exists():
        print("❌ SESSION DIRECTORY DOES NOT EXIST ❌")
        print()
        print("The session was not saved. To create a new session:")
        print()
        print("Option 1: Use Chrome with persistent profile")
        print("=" * 60)
        chrome_cmd = (
            "open -a Google\ Chrome --args "
            f"--user-data-dir={session_dir} "
            "https://www.linkedin.com/login"
        )
        print(chrome_cmd)
        print()
        print("Steps:")
        print("1. Copy and run the command above in Terminal")
        print("2. Log in to LinkedIn with your Google account")
        print("3. Close browser when done")
        print()
        return False
    
    print("✅ SESSION DIRECTORY EXISTS ✅")
    print()
    
    # Check Default subdirectory (where Chrome stores data)
    default_dir = session_dir / "Default"
    if not default_dir.exists():
        print("❌ Default Directory MISSING ❌")
        print("This browser profile directory structure is incomplete.")
        print()
        return False
    
    print("📁 Session Structure:")
    print(f"   {session_dir}")
    print(f"   └── Default/ ✅")
    print()
    
    # Check critical files for session persistence
    critical_files = [
        default_dir / "Cookies",
        default_dir / "Login Data",
        default_dir / "History",
        default_dir / "Preferences",
        default_dir / "Local Storage",
        default_dir / "Session Storage"
    ]
    
    session_valid = True
    file_details = []
    
    for file_path in critical_files:
        if file_path.exists():
            # Get file stats
            stat = file_path.stat()
            size_kb = stat.st_size / 1024
            modified = datetime.fromtimestamp(stat.st_mtime)
            
            # Check if file has data (not empty)
            has_data = stat.st_size > 0
            
            file_details.append({
                'path': file_path,
                'size_kb': size_kb,
                'modified': modified,
                'has_data': has_data,
                'type': 'file' if file_path.is_file() else 'dir'
            })
        else:
            session_valid = False
    
    # Display file status
    print("📄 Critical Session Files:")
    print()
    
    for detail in file_details:
        status = "✅" if detail['has_data'] else "⚠️"
        if detail['type'] == 'dir':
            print(f"   {status} {detail['path'].name}/ - directory found")
        else:
            size = f"{detail['size_kb']:.1f} KB"
            print(f"   {status} Cookies - {size} - {detail['modified'].strftime('%Y-%m-%d %H:%M')}")
    
    print()
    
    # Calculate total size of Default directory
    try:
        import subprocess
        result = subprocess.run(
            ['du', '-sh', str(default_dir)],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            total_size = result.stdout.strip().split()[0]
            print(f"💾 Total session data: {total_size}")
            print()
    except:
        pass
    
    # Check if Cookies file exists and has data
    cookies_file = default_dir / "Cookies"
    if cookies_file.exists():
        cookies_stat = cookies_file.stat()
        cookies_size_kb = cookies_stat.st_size / 1024
        cookies_modified = datetime.fromtimestamp(cookies_stat.st_mtime)
        
        print("🍪 Cookies Analysis:")
        print(f"   - File size: {cookies_size_kb:.1f} KB")
        print(f"   - Last modified: {cookies_modified.strftime('%Y-%m-%d %H:%M')}")
        
        # Check age (session freshness)
        age_hours = (datetime.now() - cookies_modified).total_seconds() / 3600
        if age_hours < 1:
            print(f"   - Age: {age_hours:.1f} hours (Very Fresh ✅)")
        elif age_hours < 24:
            print(f"   - Age: {age_hours:.1f} hours (Fresh ✅)")
        else:
            print(f"   - Age: {age_hours:.1f} hours (Old ⚠️)")
        
        # Size indicates activity
        if cookies_size_kb > 20:
            print("   - Activity level: HIGH (Many cookies stored) ✅")
            print("   - Session likelihood: ACTIVE ✅")
        elif cookies_size_kb > 5:
            print("   - Activity level: MEDIUM (Some cookies stored) ✅")
            print("   - Session likelihood: LIKELY ACTIVE ✅")
        else:
            print("   - Activity level: LOW (Few cookies stored) ⚠️")
            print("   - Session likelihood: MAY BE INCOMPLETE ⚠️")
    else:
        print("❌ Cookies file MISSING")
        session_valid = False
    
    print()
    
    # Overall assessment
    if session_valid:
        print("=" * 50)
        print("🏆 ASSESSMENT: SESSION READY FOR USE ✅")
        print("=" * 50)
        print()
        print("The LinkedIn session was successfully saved during the")
        print("manual login process. The session appears to be complete")
        print("and suitable for authenticated LinkedIn scraping.")
        print()
        print("✅ Next step: Test authenticated scraping")
        print()
        return True
    else:
        print("❌ ASSESSMENT: SESSION INCOMPLETE ❌")
        print()
        print("The LinkedIn session was not properly saved.")
        print("Manual re-authentication will be required.")
        print()
        print("⚠️ Action required: Re-authenticate with LinkedIn")
        print()
        return False

def check_baseline_comparison():
    """Check if baseline data exists for comparison."""
    
    print("📊 Baseline Comparison:")
    print("-" * 30)
    
    # Check for unauthenticated scrape
    base_dir = Path(__file__).parent.parent
    baseline_file = base_dir / "test_outputs" / "carlo_unauthenticated_scrape.md"
    
    if baseline_file.exists():
        size = baseline_file.stat().st_size
        print(f"✅ Baseline file exists: {baseline_file.name}")
        print(f"   Size: {size / 1024:.1f} KB (unauthenticated)")
        print()
        return True
    else:
        print("⚠️ No baseline file found for comparison")
        print("   Will generate baseline during test")
        print()
        return False

def main():
    """Main verification function."""
    
    try:
        # Run session verification
        session_ok = verify_linkedin_session()
        
        # Check baseline
        baseline_exists = check_baseline_comparison()
        
        # Summary
        print("=" * 50)
        print("VERIFICATION COMPLETE")
        print("=" * 50)
        print()
        
        if session_ok:
            print("🎉 RESULT: SUCCESS - Session verified and ready!")
            print()
            print("✅ Next steps:")
            print("   1. Test authenticated scraping: tests/test_authenticated_linkedin_scraping.py")
            print("   2. Run B2B lead pipeline with LinkedIn authentication")
            print()
            sys.exit(0)
        else:
            print("❌ RESULT: FAILED - Session incomplete")
            print()
            print("⚠️ Action required: Re-authenticate with LinkedIn")
            print("   Instructions provided above")
            print()
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n\nVerification cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ ERROR during verification: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
