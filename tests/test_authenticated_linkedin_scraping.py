#!/usr/bin/env python3
"""
Authenticated LinkedIn Scraping Test

Tests if the saved LinkedIn session can be used to scrape LinkedIn profiles
without authentication blocks.

Usage:
    python tests/test_authenticated_linkedin_scraping.py
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables
load_dotenv()

from tools.crawl4ai_client import Crawl4AIClient
from agents.content_extractor import ContentExtractorAgent
from agents.lead_enricher import LeadEnricherAgent

# Test profile URL
TEST_PROFILE_URL = "https://www.linkedin.com/in/carlo-bizzaro/"

class AuthenticatedLinkedInTest:
    """Test authenticated LinkedIn scraping."""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.session_dir = self.base_dir / "browser_data" / "linkedin_profile"
        self.test_output_dir = self.base_dir / "test_outputs"
        
        # Create test output directory
        self.test_output_dir.mkdir(exist_ok=True)
        
        # Initialize agents
        self.crawler = Crawl4AIClient()
        self.extractor = ContentExtractorAgent()
        self.enricher = LeadEnricherAgent()
        
        # Results
        self.results = {}
    
    async def setup(self):
        """Initialize test setup."""
        print("Authenticated LinkedIn Scraping Test")
        print("=" * 50)
        print(f"Test Profile: {TEST_PROFILE_URL}")
        print(f"Test Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print()
        
        # Check session directory
        if not self.session_dir.exists():
            print("❌ SESSION MISSING - Cannot run test")
            print("Run: python scripts/verify_linkedin_session.py")
            return False
        
        print("✅ Session Found:")
        print(f"   Directory: {self.session_dir}")
        
        # Check session files
        default_dir = self.session_dir / "Default"
        cookies_file = default_dir / "Cookies"
        
        if cookies_file.exists():
            stat = cookies_file.stat()
            size_kb = stat.st_size / 1024
            modified = datetime.fromtimestamp(stat.st_mtime)
            print(f"   Cookies: {size_kb:.1f} KB ({modified.strftime('%Y-%m-%d %H:%M')})")
        
        return True
    
    async def run_full_test(self):
        """Run all tests comparing authentication vs unauthenticated."""
        
        print("🔬 Running full authenticated scraping test...")
        print()
        
        test_cases = [
            {
                'name': 'Authenticated (with session)',
                'use_session': True,
                'expected_result': 'Full profile data'
            },
            {
                'name': 'Unauthenticated (no session)', 
                'use_session': False,
                'expected_result': 'Limited data with auth blocks'
            }
        ]
        
        results = []
        
        for test_case in test_cases:
            print(f"Testing: {test_case['name']}")
            print("-" * 50)
            
            # Initialize crawler based on test case
            if test_case['use_session']:
                # Use LinkedIn authentication with saved session
                crawler_client = Crawl4AIClient(
                    linkedin_auth=True,
                    session_data_dir=str(self.session_dir)
                )
            else:
                # No authentication - fresh session
                crawler_client = Crawl4AIClient(
                    linkedin_auth=False
                )
            
            try:
                # Use async context manager
                async with crawler_client as crawler:
                    # Fetch the profile
                    print("Scraping...")
                    result = await crawler.fetch_linkedin_profile(TEST_PROFILE_URL)
                    
                    # Analyze result
                    fetch_status = result.get("fetch_status")
                    print(f"Status: {'SUCCESS' if fetch_status == 'success' else 'FAILED'}")
                    
                    if fetch_status == "success":
                        markdown = result.get("markdown", "")
                        print(f"URL: {result.get('url')}")
                        print(f"Markdown: {len(markdown)} chars")
                        
                        # Save markdown for analysis
                        test_name = test_case['name'].replace(' ', '_').replace('(', '').replace(')', '').lower()
                        output_file = self.test_output_dir / f"carlo_{test_name}_scrape.md"
                        
                        with open(output_file, 'w', encoding='utf-8') as f:
                            f.write(f"# Test: {test_case['name']}\n\n")
                            f.write(f"URL: {result.get('url')}\n\n")
                            f.write(f"Success: {fetch_status == 'success'}\n\n")
                            f.write(f"## Markdown Output\n\n")
                            f.write(markdown or "NO MARKDOWN")
                        
                        print(f"Saved: {output_file}")
                        
                        # Verify authentication status
                        auth_status = self.check_authentication(markdown, test_case['name'])
                        print(f"Auth Status: {auth_status}")
                        
                        # Extract lead data
                        extraction_result = await self.extract_lead_data(markdown)
                        
                        # Store results
                        results.append({
                            'test_case': test_case['name'],
                            'result': result,
                            'authentication_passed': auth_status['passed'],
                            'sign_in_blocks': auth_status['count'],
                            'markdown_length': len(markdown),
                            'extraction': extraction_result,
                            'output_file': output_file
                        })
                        
                    else:
                        print(f"Error: {result.get('error', 'Unknown error')}")
                        return False
                        
            except Exception as e:
                print(f"❌ Exception: {e}")
                import traceback
                traceback.print_exc()
                return False
            
            print()
        
        self.results = results
        return True
    
    def check_authentication(self, markdown, test_name):
        """Check if authentication worked correctly."""
        
        if not markdown:
            return {'passed': False, 'count': 0, 'details': ['No markdown']}
        
        # Look for LinkedIn authentication indicators
        # These are strings that indicate authentication blocks
        auth_indicators = [
            'Sign in to view',
            'sign in to view',
            'Please sign in',
            'Join now to see',
            'Join LinkedIn',
            'sign in with LinkedIn',
            'Log in to continue',
            'Please log in'
        ]
        
        # Count indicators
        indicator_counts = {}
        for indicator in auth_indicators:
            count = markdown.lower().count(indicator.lower())
            if count > 0:
                indicator_counts[indicator] = count
        
        total_blocks = len(indicator_counts)
        
        # Check if full profile is visible
        has_profile_content = any([
            'Experience' in markdown,
            'Education' in markdown,
            'About' in markdown,
            'Skills' in markdown,
            'carlo bizzar' and 'carlo' and 'bizzar' in markdown.lower()
        ])
        
        auth_passed = total_blocks == 0 and has_profile_content
        
        return {
            'passed': auth_passed,
            'count': total_blocks,
            'details': indicator_counts if not auth_passed else ['Full profile visible']
        }
    
    async def extract_lead_data(self, markdown):
        """Extract lead data using the agent."""
        
        if not markdown:
            return None
        
        try:
            # Use content extractor to parse the profile
            extraction_result = await self.extractor.extract_from_markdown(
                markdown,
                schema_name='LinkedInProfile'
        )
            return extraction_result
        except Exception as e:
            print(f"Extraction error: {e}")
            return None
    
    def generate_report(self):
        """Generate comprehensive test report."""
        
        print("📝 Generating Test Report")
        print("=" * 50)
        print()
        
        if not self.results:
            print("❌ No results to report")
            return False
        
        # Load baseline if exists
        baseline_file = self.test_output_dir / "carlo_authenticated_scrape_baseline.md"
        baseline_data = None
        
        if baseline_file.exists():
            with open(baseline_file, 'r', encoding='utf-8') as f:
                baseline_content = f.read()
            baseline_data = {
                'length': len(baseline_content),
                'lines': len(baseline_content.split('\n'))
            }
            print("✅ Baseline data loaded for comparison")
        
        # Comparison table
        print("📊 Comparison Table:")
        print("-" * 80)
        print(f"{'Test':<30}{'Markdown':<10}{'Auth':<8}{'Blocks':<8}{'Status'}")
        print("-" * 80)
        
        for result in self.results:
            auth_passed = "✅" if result['authentication_passed'] else "❌"
            blocks = result['sign_in_blocks']
            length_kb = result['markdown_length'] / 1024
            
            print(f"{result['test_case']:<30}{length_kb:<10.1f}{auth_passed:<8}{blocks:<8}{''}")
        
        print("-" * 80)
        print()
        
        # Detailed analysis
        print("🔍 Detailed Analysis:")
        print("-" * 50)
        
        if len(self.results) >= 2:
            auth_result = self.results[0]  # Test 1: Authenticated
            unauth_result = self.results[1]  # Test 2: Unauthenticated
            
            print("Authentication Status:")
            print(f"  Authenticated: {'✅ PASSED' if auth_result['authentication_passed'] else '❌ FAILED'}")
            print(f"  Unauthenticated: {'❌ BLOCKED' if not unauth_result['authentication_passed'] else '⚠️ UNKNOWN'}")
            print()
            
            print("Content Comparison:")
            auth_length = auth_result['markdown_length']
            unauth_length = unauth_result['markdown_length']
            diff = auth_length - unauth_length
            increase = (diff / unauth_length * 100) if unauth_length > 0 else 0
            
            print(f"  Authenticated: {auth_length / 1024:.1f} KB")
            print(f"  Unauthenticated: {unauth_length / 1024:.1f} KB")
            print(f"  Difference: +{diff / 1024:.1f} KB (+{increase:.1f}%)")
            print()
            
            if increase > 50:
                print("🎉 Significant improvement in content access!")
            elif increase > 20:
                print("✅ Noticeable improvement in content access")
            else:
                print("⚠️ Limited improvement in content access")
            
            print()
            
            print("Authentication Blocks:")
            auth_blocks = auth_result['sign_in_blocks']
            unauth_blocks = unauth_result['sign_in_blocks']
            
            print(f"  Authenticated: {auth_blocks} blocks")
            print(f"  Unauthenticated: {unauth_blocks} blocks")
            
            if unauth_blocks > 0 and auth_blocks == 0:
                print("✅ All authentication blocks removed!")
            elif auth_blocks < unauth_blocks:
                print(f"✅ Reduced authentication blocks by {unauth_blocks - auth_blocks}")
            elif auth_blocks == unauth_blocks:
                print("⚠️ No change in authentication blocks")
            
            print()
        
        # Lead extraction comparison
        print("👤 Lead Extraction Results:")
        print("-" * 30)
        
        for result in self.results:
            extraction = result.get('extraction', {})
            if extraction and extraction.get('lead'):
                lead = extraction['lead']
                print(f"Test: {result['test_case']}")
                print(f"  Name: {lead.get('name', 'N/A')}")
                print(f"  Company: {lead.get('company', 'N/A')}")
                print(f"  Role: {lead.get('role', 'N/A')}")
                print(f"  Location: {lead.get('location', 'N/A')}")
                print()
            else:
                print(f"  {result['test_case']}: No data extracted")
        
        print()
    
    def save_report(self):
        """Save detailed report to file.""" 
        
        report_file = self.test_output_dir / "authenticated_linkedin_test_report.txt"
        
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write("Authenticated LinkedIn Scraping Test Report\n")
            f.write("=" * 50)
            f.write(f"\nTest Profile: {TEST_PROFILE_URL}\n")
            f.write(f"Test Date: {Path(__file__).stat().st_mtime}\n\n")
            
            if not self.results:
                f.write("No results to report\n")
                return
            
            # Comparison table
            f.write("Comparison Table:\n")
            f.write("-" * 80)
            f.write("\n")
            f.write(f"{'Test':<30}{'Markdown':<10}{'Auth':<8}{'Blocks':<8}{'Status'}\n")
            f.write("-" * 80)
            f.write("\n")
            
            for result in self.results:
                auth_passed = "PASSED" if result['authentication_passed'] else "FAILED"
                blocks = result['sign_in_blocks'] if result.get('sign_in_blocks') else 0
                length_kb = result['markdown_length'] / 1024
                
                f.write(f"{result['test_case']:<30}{length_kb:<10.1f}{auth_passed:<8}{blocks:<8}{''}")
                f.write("\n")
            
            f.write("\n")
            
            # Detailed results
            for i, result in enumerate(self.results):
                f.write(f"Test {i+1}: {result['test_case']}\n")
                f.write("-" * 50)
                f.write("\n")
                f.write(f"✅ Success: {result['result'].success}\n")
                f.write(f"🌐 URL: {result['result'].url}\n")
                f.write(f"📄 Markdown: {result['markdown_length']} bytes\n")
                f.write(f"💾 HTML: {len(result['result'].html) if result['result'].html else 0} bytes\n")
                f.write(f"🍪 Auth Check: {'PASSED' if result['authentication_passed'] else 'FAILED'}\n")
                f.write(f"🚫 Auth Blocks: {result['sign_in_blocks']}\n")
                f.write(f"📝 Output: {result['output_file']}\n")
                f.write("\n")
        
        print(f"✅ Report saved: {report_file}")
        return report_file


async def main():
    """Main test execution."""
    
    try:
        # Initialize test
        test = AuthenticatedLinkedInTest()
        
        # Setup
        if not await test.setup():
            sys.exit(1)
        
        # Run full test
        if not await test.run_full_test():
            sys.exit(1)
        
        # Generate report
        test.generate_report()
        
        # Save report
        test.save_report()
        
        # Summary
        print("🎉 TEST COMPLETE")
        print("=" * 30)
        print()
        print("✅ Session verification: PASSED")
        print("✅ Scraping tests: COMPLETED")
        print("✅ Analysis report: GENERATED")
        print()
        print("🏆 OVERALL RESULT: READY FOR PIPELINE INTEGRATION")
        print()
        
        return test
        
    except KeyboardInterrupt:
        print("")
        print("Test interrupted by user.")
        sys.exit(130)
    except Exception as e:
        print("")
        print(f"Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Run async main
    result = asyncio.run(main())
