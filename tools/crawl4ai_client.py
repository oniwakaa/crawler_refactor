import asyncio
import time
import random
import os
from typing import List, Dict, Optional, Any
import structlog
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from utils.url_utils import normalize_linkedin_url

from crawl4ai.content_filter_strategy import PruningContentFilter
from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

logger = structlog.get_logger()

class Crawl4AIClient:
    """
    Client for Crawl4AI to handle web crawling and content extraction.
    Uses AsyncWebCrawler with resource-aware batch processing.
    """
    
    def __init__(
        self, 
        browser_config: Optional[BrowserConfig] = None,
        linkedin_auth: bool = False,
        session_data_dir: Optional[str] = None,
        settings: Dict = None
    ):
        """
        Initialize Crawl4AI client.
        
        Args:
            browser_config: BrowserConfig for crawler initialization.
                           If None, uses default config.
            linkedin_auth: If True, uses persistent browser context with saved session.
            session_data_dir: Directory containing browser session data.
                            Defaults to "browser_data/linkedin_profile" if linkedin_auth is True.
            settings: Configuration dictionary (from settings.yaml).
        """
        self.settings = settings or {}
        self.linkedin_config = self.settings.get("linkedin", {})
        self.linkedin_auth = linkedin_auth
        
        # Rate limiting settings
        self.rate_limit_config = self.linkedin_config.get("rate_limiting", {})
        self.rate_limit_enabled = self.rate_limit_config.get("enabled", True)
        self.base_delay = self.rate_limit_config.get("delay_between_requests", 4)
        self.randomize_delay = self.rate_limit_config.get("randomize_delay", True)
        self.min_delay = self.rate_limit_config.get("min_delay", 3)
        self.max_delay = self.rate_limit_config.get("max_delay", 6)
        
        # Session rate limiting
        self.linkedin_request_count = 0
        self.requests_before_long_pause = self.rate_limit_config.get("requests_before_long_pause", 25)
        self.long_pause_duration = self.rate_limit_config.get("long_pause_duration", 60)
        
        if linkedin_auth and browser_config is None:
            # Use persistent context with saved LinkedIn session
            if session_data_dir is None:
                session_data_dir = self.linkedin_config.get("session_data_dir", "browser_data/linkedin_profile")
            
            # Ensure absolute path
            if not os.path.isabs(session_data_dir):
                session_data_dir = os.path.abspath(session_data_dir)
            
            logger.info("Initializing with LinkedIn authentication", session_dir=session_data_dir)
            
            # Determine headless mode
            # 1. Check env var (highest priority for debugging)
            # 2. Check settings.yaml
            # 3. Default to True (production safe)
            env_headless = os.getenv("LINKEDIN_HEADLESS")
            if env_headless is not None:
                is_headless = env_headless.lower() == "true"
            else:
                is_headless = self.linkedin_config.get("headless", True)
                
            logger.info(f"Crawl4AI browser mode: {'headless' if is_headless else 'visible (debugging)'}")
            
            self.browser_config = BrowserConfig(
                browser_type="chromium",
                headless=is_headless,
                use_persistent_context=True,
                user_data_dir=session_data_dir,
                viewport_width=1920,
                viewport_height=1080,
                verbose=True  # Enable verbose logging for debugging
            )
        else:
            self.browser_config = browser_config or BrowserConfig(
                browser_type="chromium",
                headless=True,
                verbose=False
            )
        
        self.crawler: Optional[AsyncWebCrawler] = None
        self.retry_attempts = 3
        self.retry_delay = 1.0  # Initial delay in seconds
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.crawler = AsyncWebCrawler(config=self.browser_config)
        await self.crawler.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.crawler:
            await self.crawler.close()
            self.crawler = None

    async def _restart_browser(self):
        """
        Restart the browser instance after a crash.
        Includes robust cleanup of lock files and retry logic.
        """
        logger.warning("♻️ Restarting browser context due to connection failure...")
        print("DEBUG: Restarting browser context...")
        
        # 1. Close existing crawler
        try:
            if self.crawler:
                await self.crawler.close()
        except Exception as e:
            logger.warning(f"Error closing crawler during restart: {e}")
            
        # 2. Wait for process cleanup
        await asyncio.sleep(2.0)
        
        # 3. Clean up lock file if it exists (defensive)
        if self.browser_config and self.browser_config.user_data_dir:
            lock_file = os.path.join(self.browser_config.user_data_dir, "SingletonLock")
            if os.path.exists(lock_file):
                try:
                    logger.warning(f"Found stale SingletonLock, removing: {lock_file}")
                    os.remove(lock_file)
                except Exception as e:
                    logger.error(f"Failed to remove lock file: {e}")
        
        # 4. Attempt to start with retries
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self.crawler = AsyncWebCrawler(config=self.browser_config)
                await self.crawler.start()
                logger.info("✅ Browser context restarted successfully")
                print("DEBUG: Browser context restarted")
                return
            except Exception as e:
                logger.error(f"Browser restart attempt {attempt+1}/{max_retries} failed: {e}")
                if "SingletonLock" in str(e):
                    # Try to remove lock again
                    if self.browser_config and self.browser_config.user_data_dir:
                        lock_file = os.path.join(self.browser_config.user_data_dir, "SingletonLock")
                        if os.path.exists(lock_file):
                            try:
                                os.remove(lock_file)
                            except:
                                pass
                
                await asyncio.sleep(3.0 * (attempt + 1))
        
        raise RuntimeError("Failed to restart browser after multiple attempts")
            
    async def batch_fetch(self, urls: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch multiple URLs using Crawl4AI's arun method with retry logic.
        Includes rate limiting and session management for LinkedIn URLs.
        
        Args:
            urls: List of URLs to fetch
            
        Returns:
            List of dictionaries containing fetched content and metadata
        """
        if not self.crawler:
            raise RuntimeError("Crawler not initialized. Use async context manager.")
            
        if not urls:
            logger.warning("No URLs provided for batch fetch")
            return []
            
        log = logger.bind(url_count=len(urls))
        log.info("🚀 Starting batch fetch")
        print(f"DEBUG: batch_fetch called with {len(urls)} URLs")
        
        # Pre-validate session if configured
        if self.linkedin_auth and self.linkedin_config.get("session_management", {}).get("validate_before_scraping", True):
            print("DEBUG: Starting session validation before scraping...")
            logger.info("📋 Starting session validation before scraping")
            await self.validate_session_before_scraping()
            print("DEBUG: Session validation complete")
            logger.info("✅ Session validation complete")
        
        results = []
        batch_start_time = time.time()
        
        # Process URLs with retry logic and rate limiting
        for i, url in enumerate(urls):
            url_start_time = time.time()
            
            # Apply session-level rate limiting (long pause)
            if "linkedin.com" in url and self.rate_limit_enabled:
                self.linkedin_request_count += 1
                if self.linkedin_request_count >= self.requests_before_long_pause:
                    logger.info(f"Rate limit threshold reached ({self.requests_before_long_pause}), taking {self.long_pause_duration}s break")
                    await asyncio.sleep(self.long_pause_duration)
                    self.linkedin_request_count = 0
            
            # Fetch URL
            # Defensive normalization
            if "linkedin.com" in url:
                normalized_url = normalize_linkedin_url(url)
                if normalized_url != url:
                    logger.info(f"Normalized URL in client: {url} -> {normalized_url}")
                    url = normalized_url
            
            print(f"DEBUG: About to fetch URL: {url}")
            logger.info(f"🌐 Fetching URL: {url}")
            
            try:
                result = await self._fetch_with_retry(url)
                print(f"DEBUG: Fetch completed for {url}, status: {result.get('fetch_status')}")
                logger.info(f"✅ Fetch result: {result.get('fetch_status')}", url=url)
                
                # Check for 404 or other specific errors in the result
                if result.get("fetch_status") == "failed":
                    error_msg = result.get("error", "")
                    if "404" in str(error_msg) or "status code 404" in str(error_msg).lower():
                        logger.warning(f"404 Not Found: {url} - URL may be invalid or profile deleted")
                    elif "403" in str(error_msg) or "status code 403" in str(error_msg).lower():
                        logger.warning(f"403 Forbidden: {url} - Access denied")
                
                # Check for logout (only for LinkedIn URLs)
                if "linkedin.com" in url and self.linkedin_auth:
                    if self._is_logged_out(result.get("markdown", ""), result.get("url", "")):
                        logger.warning("LinkedIn logout detected, triggering re-authentication")
                        
                        # Attempt re-authentication
                        if await self._reauth_linkedin():
                            # Retry the current URL
                            logger.info("Retrying URL after re-authentication")
                            result = await self._fetch_with_retry(url)
                        else:
                            logger.error("Re-authentication failed, skipping retry")
                
                fetch_duration = time.time() - url_start_time
                result["fetch_duration"] = fetch_duration
                results.append(result)
                
            except Exception as e:
                logger.error(f"Unexpected error fetching {url}: {e}")
                # Create error result
                results.append({
                    "url": url,
                    "markdown": "",
                    "html": "",
                    "fetch_status": "failed",
                    "error": str(e),
                    "timestamp": time.time(),
                    "fetch_duration": time.time() - url_start_time
                })
            
            # Add delay after each LinkedIn URL (except last)
            if i < len(urls) - 1 and "linkedin.com" in url and self.rate_limit_enabled:
                if self.randomize_delay:
                    delay = random.uniform(self.min_delay, self.max_delay)
                else:
                    delay = self.base_delay
                
                logger.debug(f"Waiting {delay:.1f}s before next LinkedIn request")
                await asyncio.sleep(delay)
        
        total_duration = time.time() - batch_start_time
        success_count = len([r for r in results if r["fetch_status"] == "success"])
        
        log.info(
            "Batch fetch completed",
            success_count=success_count,
            total_count=len(results),
            total_duration=total_duration
        )
        
        return results
    
    async def _fetch_with_retry(self, url: str, wait_until: Optional[str] = None, bypass_delay: bool = False) -> Dict[str, Any]:
        """
        Fetch a single URL with exponential backoff retry logic.
        
        Args:
            url: URL to fetch
            wait_until: Optional wait condition override
            bypass_delay: If True, skip the delay_before_return_html
            
        Returns:
            Dictionary containing fetched content and metadata
        """
        log = logger.bind(url=url)
        last_error = None
        
        for attempt in range(self.retry_attempts):
            try:
                # Configure crawl settings
                # Use specific settings for LinkedIn if applicable
                if "linkedin.com" in url:
                    page_load_config = self.linkedin_config.get("page_load", {})
                    # Use provided wait_until or default from config
                    wait_condition = wait_until or page_load_config.get("wait_until", "networkidle")
                    
                    # Determine delay
                    delay = 0 if bypass_delay else page_load_config.get("delay_after_load", 2000)
                    
                    logger.info(f"⚙️ LinkedIn fetch config: wait_until={wait_condition}, delay={delay}ms", url=url)
                    print(f"DEBUG: LinkedIn config - wait_until={wait_condition}, delay_before_return_html={delay}ms")
                    
                    # Configure pruning filter for LinkedIn
                    pruning_filter = PruningContentFilter(
                        threshold=0.2, 
                        threshold_type="fixed", 
                        min_word_threshold=0
                    )
                    
                    # Create markdown generator with filter
                    md_generator = DefaultMarkdownGenerator(content_filter=pruning_filter)
                    
                    crawl_config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        word_count_threshold=10,
                        wait_until=wait_condition,
                        page_timeout=page_load_config.get("timeout", 30000),
                        delay_before_return_html=delay,
                        markdown_generator=md_generator
                    )
                else:
                    crawl_config = CrawlerRunConfig(
                        cache_mode=CacheMode.BYPASS,
                        word_count_threshold=10,
                        wait_until=wait_until or "domcontentloaded"
                    )
                
                print(f"DEBUG: Calling crawler.arun for {url}...")
                logger.info("🔄 Calling crawler.arun", url=url)
                
                # Wrap in timeout to prevent indefinite hanging
                try:
                    result = await asyncio.wait_for(
                        self.crawler.arun(url=url, config=crawl_config),
                        timeout=60.0  # 60 second timeout as safety net
                    )
                except asyncio.TimeoutError:
                    logger.error(f"⏰ Timeout after 60s waiting for crawler.arun", url=url)
                    print(f"DEBUG: TIMEOUT - crawler.arun exceeded 60 seconds for {url}")
                    raise RuntimeError(f"Crawler timeout after 60s for {url}")
                
                print(f"DEBUG: crawler.arun returned, success={result.success}")
                logger.info(f"📥 Crawler returned: success={result.success}", url=url)
                
                if result.success:
                    markdown_len = len(getattr(result, 'markdown', ''))
                    fit_markdown_len = len(getattr(result, 'fit_markdown', ''))
                    print(f"DEBUG: Extracting content, markdown length: {markdown_len}, fit_markdown: {fit_markdown_len}")
                    logger.info(f"📄 Extracting content: markdown={markdown_len} chars", url=url)
                    
                    return {
                        "url": url,
                        "markdown": getattr(result, 'markdown', ''),
                        "fit_markdown": getattr(result, 'fit_markdown', ''),
                        "html": getattr(result, 'html', ''),
                        "fetch_status": "success",
                        "timestamp": time.time(),
                        "error": None
                    }
                else:
                    last_error = result.error_message
                    log.warning(
                        "Fetch attempt failed",
                        attempt=attempt + 1,
                        error=result.error_message
                    )
                    
            except Exception as e:
                error_msg = str(e)
                last_error = error_msg
                
                # Check for critical browser failures
                is_browser_crash = any(err in error_msg for err in [
                    "Connection closed", 
                    "Target closed", 
                    "Reading from the driver",
                    "Navigating ACS-GOTO"
                ])
                
                if is_browser_crash:
                    logger.error(f"💥 Browser connection error: {error_msg}")
                    print(f"DEBUG: Critical browser error detected: {error_msg}")
                    await self._restart_browser()
                
                log.warning(
                    "Fetch attempt failed with exception",
                    attempt=attempt + 1,
                    error=error_msg
                )
            
            # Wait before retry (exponential backoff)
            if attempt < self.retry_attempts - 1:
                delay = self.retry_delay * (2 ** attempt)
                log.debug("Retrying after delay", delay=delay)
                await asyncio.sleep(delay)
        
        # All attempts failed
        log.error("All fetch attempts failed", attempts=self.retry_attempts)
        return {
            "url": url,
            "markdown": "",
            "html": "",
            "fetch_status": "failed",
            "timestamp": time.time(),
            "error": last_error
        }

    async def fetch_linkedin_profile(self, linkedin_url: str) -> Dict[str, Any]:
        """
        Fetch a LinkedIn profile URL.
        
        Args:
            linkedin_url: LinkedIn profile URL
            
        Returns:
            Dictionary with fetch results
        """
        log = logger.bind(url=linkedin_url, authenticated=self.linkedin_auth)
        
        if self.linkedin_auth:
            log.info("Fetching LinkedIn profile with authenticated session")
        
        return await self._fetch_with_retry(linkedin_url)
    
    async def validate_linkedin_session(self) -> bool:
        """
        Validate that LinkedIn session is still active by checking LinkedIn feed.
        
        Returns:
            True if session is valid, False otherwise
        """
        if not self.linkedin_auth:
            logger.warning("Session validation called but linkedin_auth is False")
            return False
        
        logger.info("Validating LinkedIn session")
        
        # Try to fetch LinkedIn feed to check if authenticated
        result = await self._fetch_with_retry(
            "https://www.linkedin.com/feed/", 
            wait_until="domcontentloaded",
            bypass_delay=True
        )
        
        if result["fetch_status"] != "success":
            logger.error("Session validation failed - could not fetch feed")
            return False
        
        # Check for signs of being logged in vs logged out
        markdown = result.get("markdown", "").lower()
        url = result.get("url", "")
        
        if self._is_logged_out(markdown, url):
            logger.error("Session validation failed - appears to be logged out")
            return False
        
        logger.info("Session validation passed - LinkedIn session is active")
        return True

    def _is_logged_out(self, markdown: str, url: str) -> bool:
        """
        Detect if LinkedIn page indicates user is logged out.
        
        Args:
            markdown: Page content in markdown
            url: Current URL
            
        Returns:
            True if logged out, False otherwise
        """
        # Primary check: URL-based detection (most reliable)
        # If redirected to authwall or login, definitely logged out
        if "/authwall" in url or "/login" in url or "/signup" in url:
            return True
        
        # Secondary check: Very specific logout indicators only
        # Only check for strong indicators to avoid false positives
        markdown_lower = markdown.lower()
        
        # Only flag as logged out if we see BOTH:
        # 1. Sign in prompt AND
        # 2. No logged-in content markers
        has_signin_prompt = "sign in to linkedin" in markdown_lower or "welcome back" in markdown_lower
        has_logged_in_markers = "notifications" in markdown_lower or "messaging" in markdown_lower
        
        # If we see sign-in prompts but NO logged-in markers, likely logged out
        if has_signin_prompt and not has_logged_in_markers:
            return True
        
        return False

    async def _reauth_linkedin(self) -> bool:
        """
        Attempt automatic re-authentication to LinkedIn via Google SSO.
        
        Returns:
            True if successful, False otherwise
        """
        logger.info("Attempting automatic LinkedIn re-authentication...")
        
        try:
            # Navigate to LinkedIn login
            login_url = "https://www.linkedin.com/login"
            await self.crawler.page.goto(login_url, wait_until="domcontentloaded")
            
            # Wait for Google SSO button or pre-filled login
            await asyncio.sleep(3)
            
            # Check if already logged in (redirect to feed)
            if "feed" in self.crawler.page.url:
                logger.info("Already logged in after navigation")
                return True
            
            # Check for Google "Continue as" button
            # Try multiple selectors
            selectors = [
                'button:has-text("Continue as")',
                'iframe[title="Sign in with Google Button"]',
                '#google-auth-button'
            ]
            
            google_btn = None
            for selector in selectors:
                try:
                    google_btn = await self.crawler.page.query_selector(selector)
                    if google_btn:
                        break
                except:
                    continue
            
            if google_btn:
                logger.info("Google SSO detected, clicking continue")
                await google_btn.click()
                
                # Wait for navigation to feed
                try:
                    await self.crawler.page.wait_for_url("**/feed/**", timeout=30000)
                    logger.info("Re-authentication successful via Google SSO")
                    return True
                except Exception:
                    logger.warning("Clicked Google SSO but didn't redirect to feed")
            
            # Fallback: Check if we are logged in anyway
            if "feed" in self.crawler.page.url:
                return True
                
            # If automatic re-auth not possible, log error
            logger.error(
                "LinkedIn session expired and automatic re-authentication failed.\n"
                "Please re-authenticate manually:\n"
                "  python scripts/setup_linkedin_auth.py\n"
                "Then restart the pipeline."
            )
            return False
            
        except Exception as e:
            logger.error(f"Re-authentication error: {e}")
            return False

    async def validate_session_before_scraping(self):
        """Validate LinkedIn session before starting scrape operations."""
        print("DEBUG: validate_session_before_scraping called")
        logger.info("🔐 Validating LinkedIn session...")
        
        # Test with LinkedIn feed URL using lighter wait condition
        print("DEBUG: Fetching feed to validate session...")
        test_result = await self._fetch_with_retry(
            "https://www.linkedin.com/feed/", 
            wait_until="domcontentloaded",
            bypass_delay=True  # Skip delay for validation
        )
        
        print(f"DEBUG: Feed fetch complete, checking logout status...")
        final_url = test_result.get("url", "")
        
        # Simplified validation: If URL didn't redirect to login/authwall, session is valid
        # This is more reliable than parsing page content
        if "/authwall" in final_url or "/login" in final_url or "/signup" in final_url:
            logger.warning("⚠️ Session invalid (redirected to login), attempting re-authentication")
            print(f"DEBUG: Session invalid - URL redirected to: {final_url}")
            await self._reauth_linkedin()
        elif test_result.get("fetch_status") != "success":
            logger.warning("⚠️ Session validation failed (fetch error)")
            print("DEBUG: Feed fetch failed, session may be invalid")
        else:
            logger.info("✅ LinkedIn session valid and active")
            print("DEBUG: Session is valid - feed accessed successfully")