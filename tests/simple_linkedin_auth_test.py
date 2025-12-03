#!/usr/bin/env python3
"""
Simple LinkedIn Authentication Test

Quick test to verify if the saved LinkedIn session works for authenticated scraping.

Usage:
    python tests/simple_linkedin_auth_test.py
"""

import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.async_crawl4ai_client import AsyncCrawl4AIClient

# Test profile URL
TEST_PROFILE_URL = "https://www.linkedin.com/in/carlo-bizzaro/"

async def main():
    """Main test execution."""
    
    print("LinkedIn Authentication Test")
    print("=" * 50)
    print(f"Test Profile: {TEST_PROFILE_URL}")
    print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()
    
    # Define session directory
    base_dir = Path(__file__).parent.parent
    session_dir = base_dir / "browser_data" / "linkedin_profile"
    
    print("📁 Session Configuration:")
    print(f"   Directory: {session_dir}")
    
    # Check if session exists
    if not session_dir.exists():
        print("❌ SESSION MISSING - Cannot run test")
        print()
        print("Run verification first:")
        print("python scripts/verify_linkedin_session.py")
        sys.exit(1)
    
    # Check session files
    default_dir = session_dir / "Default"
    cookies_file = default_dir / "Cookies"
    
    if cookies_file.exists():
        stat = cookies_file.stat()
        size_kb = stat.st_size / 1024
        modified = datetime.fromtimestamp(stat.st_mtime)
        print(f"   Cookies: {size_kb:.1f} KB ({modified.strftime('%Y-%m-%d %H:%M')})")
    else:
        print("❌ Cookies file missing")
        sys.exit(1)
    
    print()
    
    # Test 1: Authenticated scraping (with session)
    print("🔬 Test 1: Authenticated Scraping (with session)")
    print("-" * 50)
    
    try:
        async with AsyncCrawl4AIClient() as crawler:
            # Configure for authenticated scraping
            browser_config = {
                'headless': True,
                'use_persistent_context': True,
                'user_data_dir': str(session_dir),
                           'verbose': True,
                'viewport_width': 1920,
             'viewport_height': 1080
            }
            
            crawler_config = {
                'cache_mode': 'BYPASS',
                'page_timeout': 300000  # 5 minutes
            }
            
            print("🌐 Scraping profile...")
            result = await crawler.scrape_url(
                TEST_PROFILE_URL,
                browser_config=browser_config,
                **crawler_config
            )
            
            print(f"✅ Status: {'SUCCESS' if result.success else 'FAILED'}")
            
            if result.success:
                print(f"🌐 URL: {result.url}")
                print(f"📄 Markdown: {len(result.markdown) if result.markdown else 0} chars")
                print(f"💾 HTML: {len(result.html) if result.html else 0} chars")
                
                # Save markdown for analysis
                test_output_dir = base_dir / "test_outputs"
                test_output_dir.mkdir(exist_ok=True)
                
                filename = "carlo_linkedin_authenticated_scrape.md"
                output_file = test_output_dir / filename
                
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(f"# LinkedIn Profile - Carlo Bizzaro (Authenticated)\n\n")
                    f.write(f"URL: {result.url}\n")
                    f.write(f"Scraped: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"Success: {result.success}\n\n")
                    f.write("## Markdown Output\n\n")
                    f.write(result.markdown or "NO MARKDOWN")
                
                print(f"📝 Saved: {output_file}")
                print()
                
                # Verify authentication blocks
                if result.markdown:
                    markdown_lower = result.markdown.lower()
                    
                    # Check for authentication indicators
                    auth_indicators = [
                        'sign in to view',
                        'sign in to view',
                        'please sign in',
                        'join now to see',
                        'join linkedin',
                        'sign in with linkedin',
                        'log in to continue',
                        'please log in',
                        'you need to sign in',
                        'authentication required'
                    ]
                    
                    found_indicators = []
                    for indicator in auth_indicators:
                        if indicator in markdown_lower:
                            count = markdown_lower.count(indicator)
                            found_indicators.append(f"'{indicator}' x{count}")
                    
                    print("🛡️  Authentication Check:")
                    
                    if found_indicators:
                        print("❌ BLOCKED - Found authentication prompts:")
                        for ind in found_indicators:
                            print(f"   ⚠️  {ind}")
                        auth_passed = False
                    else:
                        print("✅ AUTHENTICATED - No authentication blocks found")
                        auth_passed = True
                    
                    # Check for profile content
                    content_indicators = [
                        'experience',
                        'education',
                        'about',
                        'skills',
                        'carlo bizzar'
                    ]
                    
                    found_content = []
                    for indicator in content_indicators:
                        if indicator in markdown_lower:
                            found_content.append(indicator)
                    
                    if found_content:
                        print(f"✅ CONTENT FOUND - Sections: {', '.join(found_content)}")
                    else:
                        print("⚠️  No profile content detected (may need better extraction)")
                    
                    print()
                    
                    # Overall assessment
                    print("📊 Summary:")
                    print("-" * 30)
                    
                    if auth_passed:
                        print("🎉 AUTHENTICATION: ✅ PASSED")
                        print("🏆 PROFILE ACCESS: ✅ FULL ACCESS")
                        print("✅ STATUS: SESSION WORKING - Full profile visible\n")
                    else:
                        print("❌ AUTHENTICATION: ⚠️ PRESENT")
                        print("❌ PROFILE ACCESS: ⚠️ LIMITED")
                        print("⚠️ STATUS: Session may not be working\n")
                    
                    return result, auth_passed
                
            else:
                print(f"❌ Error: {result.error_message}")
                return result, False
        
    except Exception as e:
        print(f"❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        return None, False

if __name__ == "__main__":
    asyncio.run(main())
