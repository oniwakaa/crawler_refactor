import asyncio
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def setup_linkedin_auth():
    """
    Interactive script to set up LinkedIn authentication.
    Launches a visible browser for the user to log in and complete 2FA.
    Saves the session to a persistent context.
    """
    # Load environment variables
    load_dotenv()
    
    username = os.getenv("LINKEDIN_USERNAME")
    password = os.getenv("LINKEDIN_PASSWORD")
    
    if not username or not password:
        print("Error: LINKEDIN_USERNAME and LINKEDIN_PASSWORD must be set in .env file")
        return

    # Define persistent storage path
    # Using a directory within the project for portability, but gitignored
    base_dir = Path(__file__).parent.parent
    user_data_dir = base_dir / "browser_data" / "linkedin_profile"
    
    # Ensure directory exists
    os.makedirs(user_data_dir, exist_ok=True)
    
    print(f"Setting up LinkedIn authentication...")
    print(f"User data directory: {user_data_dir}")
    print("Launching browser... Please wait.")

    # Configure browser with persistent context
    browser_config = BrowserConfig(
        browser_type="chromium",
        headless=False,  # Visible for manual interaction
        verbose=True,
        use_persistent_context=True,
        user_data_dir=str(user_data_dir)
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        # Navigate to LinkedIn login
        print("Navigating to LinkedIn login page...")
        try:
            result = await crawler.arun(
                url="https://www.linkedin.com/login",
                config=CrawlerRunConfig(
                    cache_mode=CacheMode.BYPASS,
                    page_timeout=300000,  # 5 minutes timeout for login page
                    wait_for="input[id='username']"  # Wait for username field
                )
            )
            
            if not result.success:
                print(f"Failed to load login page: {result.error_message}")
                return
        except AttributeError as e:
            print(f"❌ API Error: {e}")
            print("This is likely due to Crawl4AI version mismatch.")
            print(f"Current Crawl4AI version: {crawl4ai.__version__}")
            print("Expected version: 0.7.x")
            print("\nMigration guide: https://docs.crawl4ai.com/core/cache-modes/")
            return
        except Exception as e:
            print(f"❌ Unexpected error navigating to LinkedIn: {e}")
            return

        print("Login page loaded.")
        
        # Attempt to fill credentials using JavaScript
        # We use the crawler's page execution capability
        # Note: In a real persistent context, if already logged in, we might be redirected to feed
        
        if "feed" in result.url:
            print("Already logged in! Session is valid.")
        else:
            print("Attempting to fill credentials...")
            
            # This is a bit tricky with Crawl4AI's abstraction, but we can try to use js_code
            # or just ask the user to log in manually since headless=False
            
            print("\n" + "="*50)
            print("PLEASE LOG IN MANUALLY IN THE BROWSER WINDOW")
            print("1. Enter your credentials if not filled")
            print("2. Complete any CAPTCHA or 2FA challenges")
            print("3. Wait until you are redirected to the LinkedIn Feed")
            print("="*50 + "\n")
            
            # We can try to fill it for them as a convenience
            fill_js = f"""
            document.getElementById('username').value = '{username}';
            document.getElementById('password').value = '{password}';
            """
            try:
                # Execute JS to fill fields (best effort)
                # Crawl4AI doesn't have a direct 'execute_script' on the crawler object easily exposed 
                # without running a crawl. 
                # But since we are in 'arun', the page is closed after the run unless we keep it open?
                # Actually, AsyncWebCrawler context manager keeps the browser open, but arun closes the page?
                # Let's check Crawl4AI behavior. 
                # With persistent context, the state is saved to disk.
                pass
            except Exception as e:
                print(f"Auto-fill failed: {e}")

        # Wait for user to complete login
        print("Waiting for successful login (checking for 'feed' in URL)...")
        
        # We'll poll for the URL change
        # Since we can't easily poll the *current* page with simple arun calls without re-navigating,
        # we will just wait for a fixed time or ask user to press Enter.
        # A better way with Crawl4AI might be to just keep the browser open.
        
        input("Press ENTER once you have successfully logged in and can see the LinkedIn Feed...")
        
        # Verify session by trying to access feed
        print("Verifying session...")
        verify_result = await crawler.arun(
            url="https://www.linkedin.com/feed/",
            config=CrawlerRunConfig(
                cache_mode=CacheMode.BYPASS,
                page_timeout=300000  # 5 minutes timeout for verification
            )
        )
        
        if "feed" in verify_result.url or "Feed" in verify_result.markdown:
            print("✅ Authentication successful! Session saved.")
            print(f"Session data stored in: {user_data_dir}")
        else:
            print("❌ Verification failed. You might not be logged in.")
            print(f"Current URL: {verify_result.url}")

if __name__ == "__main__":
    asyncio.run(setup_linkedin_auth())
