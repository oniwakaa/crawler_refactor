"""
Test script for authenticated LinkedIn profile extraction.
Validates that the saved session allows full content extraction.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from tools.crawl4ai_client import Crawl4AIClient
from agents.content_extractor import ContentExtractorAgent
from models.lead import LeadProfile
import structlog

logger = structlog.get_logger()

# Test profile URL
TEST_PROFILE_URL = "https://www.linkedin.com/in/carlo-bizzaro/"

# Baseline metrics from unauthenticated scraping
BASELINE_MARKDOWN_LENGTH = 48209
BASELINE_SIGN_IN_COUNT = 17

async def test_authenticated_extraction():
    """Test LinkedIn profile extraction with authenticated session."""
    
    print("\n" + "="*70)
    print("Authenticated LinkedIn Extraction Test")
    print("="*70)
    print(f"\nTest Profile: {TEST_PROFILE_URL}\n")
    
    # Step 1: Session Status
    print("1. Session Status:")
    session_dir = Path("browser_data/linkedin_profile")
    print(f"   - Browser data dir: {session_dir.absolute()}")
    print(f"   - Session found: {'YES' if session_dir.exists() else 'NO'}")
    
    cookies_file = session_dir / "Default" / "Cookies"
    print(f"   - Cookies loaded: {'YES' if cookies_file.exists() else 'NO'}")
    print()
    
    # Step 2: Initialize client with authentication
    print("2. Initializing Crawl4AI with authentication...")
    async with Crawl4AIClient(linkedin_auth=True) as client:
        # Validate session first
        print("3. Validating session...")
        session_valid = await client.validate_linkedin_session()
        
        if not session_valid:
            print("   ❌ Session validation FAILED")
            print("\n   Session appears to be expired or invalid.")
            print("   Please refresh authentication:")
            print("   1. Run: python scripts/refresh_linkedin_auth.py")
            print("   2. Or manually login using Chrome with the profile directory")
            print("   3. Then retry this test")
            return False
        
        print("   ✅ Session validation PASSED")
        print()
        
        # Step 3: Fetch profile
        print("4. Fetching LinkedIn profile...")
        result = await client.fetch_linkedin_profile(TEST_PROFILE_URL)
        
        if result["fetch_status"] != "success":
            print(f"   ❌ Fetch FAILED: {result.get('error', 'Unknown error')}")
            return False
        
        print(f"   ✅ Fetch SUCCESS")
        
        # Save markdown for inspection
        markdown = result["markdown"]
        markdown_file = project_root / "tests" / "outputs" / "authenticated_linkedin_profile.md"
        markdown_file.parent.mkdir(parents=True, exist_ok=True)
        markdown_file.write_text(markdown)
        print(f"   - Saved markdown to: {markdown_file}")
        print()
        
        # Step 4: Content Analysis
        print("5. Content Analysis:")
        print(f"   - Status: SUCCESS")
        print(f"   - Markdown length: {len(markdown):,} characters")
        
        markdown_lower = markdown.lower()
        sign_in_count = markdown_lower.count("sign in to view")
        print(f"   - 'Sign in to view' count: {sign_in_count}")
        print()
        
        # Check for key sections
        has_experience = "experience" in markdown_lower and len(markdown) > 60000
        has_education = "education" in markdown_lower
        has_company_info = "company" in markdown_lower or "founder" in markdown_lower
        
        print("   Content sections:")
        print(f"   - Experience section: {'VISIBLE' if has_experience else 'HIDDEN'}")
        print(f"   - Education section: {'VISIBLE' if has_education else 'HIDDEN'}")
        print(f"   - Company info: {'VISIBLE' if has_company_info else 'HIDDEN'}")
        print()
        
        # Step 5: Extract structured data
        print("6. Extraction Results:")
        
        # Initialize extractor (it loads config internally)
        async with ContentExtractorAgent() as extractor:
            # Extract lead data
            lead_data = await extractor.extract_entities(
                markdown=markdown,
                schema=LeadProfile,
                url=TEST_PROFILE_URL
            )
            
            if lead_data:
                print(f"   - Name: {lead_data.name}")
                print(f"   - Company: {lead_data.company}")
                print(f"   - Role: {lead_data.role}")
                print(f"   - LinkedIn: {lead_data.linkedin_url}")
                print(f"   - Completeness: {lead_data.completeness_score:.0%}")
            else:
                print("   ❌ Extraction returned None")
                lead_data = LeadProfile(name="Unknown", company="Unknown Company", completeness_score=0.0)
        print()
        
        # Step 6: Comparison
        print("7. Comparison with Unauthenticated:")
        print(f"   Before (no auth):")
        print(f"   - Markdown: {BASELINE_MARKDOWN_LENGTH:,} chars")
        print(f"   - 'Sign in to view': {BASELINE_SIGN_IN_COUNT} occurrences")
        print(f"   - Company: 'Unknown Company'")
        print(f"   - Role: null")
        print(f"   - Completeness: ~30%")
        print()
        print(f"   After (authenticated):")
        print(f"   - Markdown: {len(markdown):,} chars")
        print(f"   - 'Sign in to view': {sign_in_count} occurrences")
        print(f"   - Company: {lead_data.company}")
        print(f"   - Role: {lead_data.role}")
        print(f"   - Completeness: {lead_data.completeness_score:.0%}")
        print()
        
        # Calculate improvement
        markdown_increase = ((len(markdown) - BASELINE_MARKDOWN_LENGTH) / BASELINE_MARKDOWN_LENGTH) * 100
        print(f"   Improvement: +{markdown_increase:.0f}% content")
        print()
        
        # Final verdict
        print("="*70)
        
        # Success criteria:
        # - No "Sign in to view" messages (or drastically reduced)
        # - Markdown length increased significantly (70%+)
        # - Company and role extracted
        # - Completeness > 60%
        
        success = (
            sign_in_count < 5 and  # Drastically reduced or eliminated
            len(markdown) > BASELINE_MARKDOWN_LENGTH * 1.5 and  # 50%+ more content
            lead_data.company != "Unknown Company" and
            lead_data.role is not None and
            lead_data.completeness_score >= 0.60
        )
        
        if success:
            print("RESULT: ✅ PASS")
            print("\nAuthenticated LinkedIn extraction is working correctly!")
            print(f"- Full profile data extracted")
            print(f"- {markdown_increase:.0f}% more content than unauthenticated")
            print(f"- Company and role successfully extracted")
            print(f"- {lead_data.completeness_score:.0%} completeness")
        else:
            print("RESULT: ❌ FAIL")
            print("\nAuthenticated extraction did not meet success criteria:")
            if sign_in_count >= 5:
                print(f"- Still seeing 'Sign in' messages ({sign_in_count} times)")
            if len(markdown) <= BASELINE_MARKDOWN_LENGTH * 1.5:
                print(f"- Content increase insufficient ({markdown_increase:.0f}%)")
            if lead_data.company == "Unknown Company":
                print(f"- Company not extracted")
            if lead_data.role is None:
                print(f"- Role not extracted")
            if lead_data.completeness_score < 0.60:
                print(f"- Completeness too low ({lead_data.completeness_score:.0%})")
        
        print("="*70)
        print()
        
        return success

if __name__ == "__main__":
    try:
        success = asyncio.run(test_authenticated_extraction())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
