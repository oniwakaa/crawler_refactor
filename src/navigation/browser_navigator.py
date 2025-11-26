"""
Browser navigation agent using browser_use for web scraping.

This module provides the WebNavigator agent that handles browsing,
HTML extraction, and content preprocessing for LangExtract.
"""

import asyncio
import logging
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path

try:
    from browser_use import browser_use
    from browser_use import BrowserConfig, BrowserAction
    BROWSER_AVAILABLE = True
except ImportError:
    BROWSER_AVAILABLE = False
    logging.warning("browser_use not available. Browser navigation will not work.")


@dataclass
class NavigationResult:
    """Result from browser navigation."""
    url: str
    content: str  # Cleaned text content
    raw_html: str  # Raw HTML for reference
    title: Optional[str] = None
    links: List[str] = None
    forms: List[Dict[str, Any]] = None
    success: bool = False
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class BrowserNavigator:
    """
    Browser-based navigation and content extraction agent.
    
    This agent handles:
    1. Navigating to websites
    2. Extracting clean text content
    3. Capturing HTML structure
    4. Finding relevant links and forms
    5. Providing content to LangExtract for structured extraction
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__)
        
        if not BROWSER_AVAILABLE:
            raise ImportError("browser_use is required for BrowserNavigator")
    
    async def navigate_to_page(self, url: str, wait_for_load: bool = True) -> NavigationResult:
        """
        Navigate to a specific URL and extract content.
        
        Args:
            url: URL to navigate to
            wait_for_load: Whether to wait for page to fully load
            
        Returns:
            NavigationResult with extracted content
        """
        try:
            self.logger.info(f"Navigating to: {url}")
            
            # Configure browser
            browser_config = BrowserConfig(
                headless=self.config.get('headless', True),
                viewport_size=self.config.get('viewport_size', {'width': 1920, 'height': 1080}),
                user_agent=self.config.get('user_agent'),
                delay=self.config.get('delay', 2)  # Wait time between actions
            )
            
            # Navigate to URL
            result = await browser_use.navigate(
                url=url,
                config=browser_config,
                wait_for_load=wait_for_load
            )
            
            if not result.success:
                return NavigationResult(
                    url=url,
                    content="",
                    raw_html="",
                    success=False,
                    error_message=result.error
                )
            
            # Extract content
            content = await self._extract_content(result.page)
            raw_html = await self._extract_html(result.page)
            title = await self._extract_title(result.page)
            links = await self._extract_links(result.page)
            forms = await self._extract_forms(result.page)
            
            return NavigationResult(
                url=url,
                content=content,
                raw_html=raw_html,
                title=title,
                links=links,
                forms=forms,
                success=True,
                metadata={
                    'page_url': result.current_url,
                    'title': title,
                    'content_length': len(content),
                    'extraction_timestamp': asyncio.get_event_loop().time()
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error navigating to {url}: {e}")
            return NavigationResult(
                url=url,
                content="",
                raw_html="",
                success=False,
                error_message=str(e)
            )
    
    async def search_and_extract(self, query: str, search_engine: str = "google") -> List[NavigationResult]:
        """
        Perform a web search and extract content from results.
        
        Args:
            query: Search query
            search_engine: Search engine to use ("google", "bing", "duckduckgo")
            
        Returns:
            List of NavigationResults from search results
        """
        try:
            # Generate search URL
            search_url = self._generate_search_url(query, search_engine)
            
            # Navigate to search results
            result = await self.navigate_to_page(search_url)
            
            if not result.success:
                return []
            
            # Extract result links
            result_links = await self._extract_search_results(result.page, search_engine)
            
            # Navigate to each result and extract content
            navigation_results = []
            for link in result_links[:10]:  # Limit to top 10 results
                try:
                    nav_result = await self.navigate_to_page(link)
                    if nav_result.success:
                        navigation_results.append(nav_result)
                except Exception as e:
                    self.logger.warning(f"Failed to extract from {link}: {e}")
                    continue
            
            return navigation_results
            
        except Exception as e:
            self.logger.error(f"Search and extract failed for query '{query}': {e}")
            return []
    
    async def extract_from_multiple_pages(self, urls: List[str]) -> List[NavigationResult]:
        """
        Extract content from multiple URLs in parallel.
        
        Args:
            urls: List of URLs to extract from
            
        Returns:
            List of NavigationResults
        """
        tasks = [self.navigate_to_page(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        navigation_results = []
        for result in results:
            if isinstance(result, Exception):
                self.logger.error(f"Error in batch extraction: {result}")
                continue
            
            navigation_results.append(result)
        
        return navigation_results
    
    async def find_contact_pages(self, base_url: str) -> List[NavigationResult]:
        """
        Find and extract content from contact pages.
        
        Args:
            base_url: Base URL to search for contact pages
            
        Returns:
            List of NavigationResults from contact-related pages
        """
        try:
            # Start with the main page
            main_result = await self.navigate_to_page(base_url)
            if not main_result.success:
                return []
            
            # Look for contact links
            contact_links = await self._find_contact_links(main_result.page, base_url)
            
            # Add the main page to results
            all_pages = [base_url] + contact_links
            
            # Extract content from all pages
            results = await self.extract_from_multiple_pages(all_pages)
            
            # Filter for contact-related content
            contact_results = []
            for result in results:
                if self._is_contact_content(result.content, result.title):
                    contact_results.append(result)
            
            return contact_results
            
        except Exception as e:
            self.logger.error(f"Failed to find contact pages for {base_url}: {e}")
            return []
    
    async def find_about_pages(self, base_url: str) -> List[NavigationResult]:
        """
        Find and extract content from about pages.
        
        Args:
            base_url: Base URL to search for about pages
            
        Returns:
            List of NavigationResults from about-related pages
        """
        try:
            # Start with the main page
            main_result = await self.navigate_to_page(base_url)
            if not main_result.success:
                return []
            
            # Look for about links
            about_links = await self._find_about_links(main_result.page, base_url)
            
            # Add the main page to results
            all_pages = [base_url] + about_links
            
            # Extract content from all pages
            results = await self.extract_from_multiple_pages(all_pages)
            
            # Filter for about-related content
            about_results = []
            for result in results:
                if self._is_about_content(result.content, result.title):
                    about_results.append(result)
            
            return about_results
            
        except Exception as e:
            self.logger.error(f"Failed to find about pages for {base_url}: {e}")
            return []
    
    def _generate_search_url(self, query: str, search_engine: str) -> str:
        """Generate search URL for the given query and engine."""
        query_encoded = query.replace(' ', '+')
        
        search_engines = {
            "google": f"https://www.google.com/search?q={query_encoded}",
            "bing": f"https://www.bing.com/search?q={query_encoded}",
            "duckduckgo": f"https://duckduckgo.com/?q={query_encoded}"
        }
        
        return search_engines.get(search_engine, search_engines["google"])
    
    async def _extract_content(self, page) -> str:
        """Extract clean text content from the page."""
        try:
            # Get page text content
            content = await page.evaluate("""
                () => {
                    // Remove script and style elements
                    const scripts = document.querySelectorAll('script, style, nav, footer, header');
                    scripts.forEach(el => el.remove());
                    
                    // Get main content
                    const main = document.querySelector('main, article, .main, .content, body');
                    const text = main ? main.innerText : document.body.innerText;
                    
                    // Clean up whitespace
                    return text.replace(/\\s+/g, ' ').trim();
                }
            """)
            
            return content or ""
        except Exception as e:
            self.logger.warning(f"Error extracting content: {e}")
            return ""
    
    async def _extract_html(self, page) -> str:
        """Extract raw HTML from the page."""
        try:
            return await page.content()
        except Exception as e:
            self.logger.warning(f"Error extracting HTML: {e}")
            return ""
    
    async def _extract_title(self, page) -> str:
        """Extract page title."""
        try:
            return await page.title()
        except Exception as e:
            self.logger.warning(f"Error extracting title: {e}")
            return ""
    
    async def _extract_links(self, page) -> List[str]:
        """Extract all links from the page."""
        try:
            links = await page.evaluate("""
                () => {
                    const anchors = document.querySelectorAll('a[href]');
                    return Array.from(anchors)
                        .map(a => a.href)
                        .filter(href => href.startsWith('http'));
                }
            """)
            return links or []
        except Exception as e:
            self.logger.warning(f"Error extracting links: {e}")
            return []
    
    async def _extract_forms(self, page) -> List[Dict[str, Any]]:
        """Extract forms from the page."""
        try:
            forms = await page.evaluate("""
                () => {
                    const formElements = document.querySelectorAll('form');
                    return Array.from(formElements).map(form => ({
                        action: form.action,
                        method: form.method,
                        inputs: Array.from(form.querySelectorAll('input[name], textarea[name], select[name]'))
                            .map(input => ({
                                name: input.name,
                                type: input.type || input.tagName.toLowerCase(),
                                required: input.required
                            }))
                    }));
                }
            """)
            return forms or []
        except Exception as e:
            self.logger.warning(f"Error extracting forms: {e}")
            return []
    
    async def _extract_search_results(self, page, search_engine: str) -> List[str]:
        """Extract search result links from search engine page."""
        try:
            selectors = {
                "google": "div.g a[href^='/url']",
                "bing": "li.b_algo a[href^='http']",
                "duckduckgo": "div.result a.result__a[href^='http']"
            }
            
            selector = selectors.get(search_engine, selectors["google"])
            links = await page.evaluate(f"""
                () => {{
                    const elements = document.querySelectorAll('{selector}');
                    return Array.from(elements)
                        .map(el => el.href)
                        .filter(href => href.startsWith('http') && !href.includes('google') && !href.includes('bing') && !href.includes('duckduckgo'));
                }}
            """)
            
            return links or []
        except Exception as e:
            self.logger.warning(f"Error extracting search results: {e}")
            return []
    
    async def _find_contact_links(self, page, base_url: str) -> List[str]:
        """Find contact-related links on the page."""
        try:
            contact_patterns = [
                'contact', 'contact-us', 'get-in-touch', 'reach-us',
                'support', 'help', 'info', 'about'
            ]
            
            links = await page.evaluate(f"""
                () => {{
                    const anchors = document.querySelectorAll('a[href]');
                    const base = new URL('{base_url}');
                    const contactLinks = [];
                    
                    Array.from(anchors).forEach(a => {{
                        const href = a.href.toLowerCase();
                        const text = a.innerText.toLowerCase();
                        
                        if ({str(contact_patterns)}.some(pattern => 
                            href.includes(pattern) || text.includes(pattern)
                        )) {{
                            // Convert relative URLs to absolute
                            try {{
                                const url = new URL(a.href, base);
                                contactLinks.push(url.href);
                            }} catch (e) {{
                                // Invalid URL, skip
                            }}
                        }}
                    }});
                    
                    return contactLinks;
                }}
            """)
            
            return links or []
        except Exception as e:
            self.logger.warning(f"Error finding contact links: {e}")
            return []
    
    async def _find_about_links(self, page, base_url: str) -> List[str]:
        """Find about-related links on the page."""
        try:
            about_patterns = ['about', 'about-us', 'company', 'team', 'story']
            
            links = await page.evaluate(f"""
                () => {{
                    const anchors = document.querySelectorAll('a[href]');
                    const base = new URL('{base_url}');
                    const aboutLinks = [];
                    
                    Array.from(anchors).forEach(a => {{
                        const href = a.href.toLowerCase();
                        const text = a.innerText.toLowerCase();
                        
                        if ({str(about_patterns)}.some(pattern => 
                            href.includes(pattern) || text.includes(pattern)
                        )) {{
                            try {{
                                const url = new URL(a.href, base);
                                aboutLinks.push(url.href);
                            }} catch (e) {{
                                // Invalid URL, skip
                            }}
                        }}
                    }});
                    
                    return aboutLinks;
                }}
            """)
            
            return links or []
        except Exception as e:
            self.logger.warning(f"Error finding about links: {e}")
            return []
    
    def _is_contact_content(self, content: str, title: str) -> bool:
        """Check if content appears to be contact-related."""
        if not content:
            return False
        
        title_lower = title.lower() if title else ""
        content_lower = content.lower()
        
        contact_keywords = [
            'contact', 'phone', 'email', 'address', 'location',
            'support', 'help', 'reach', 'get in touch', 'call us'
        ]
        
        return any(keyword in title_lower or keyword in content_lower 
                  for keyword in contact_keywords)
    
    def _is_about_content(self, content: str, title: str) -> bool:
        """Check if content appears to be about/company-related."""
        if not content:
            return False
        
        title_lower = title.lower() if title else ""
        content_lower = content.lower()
        
        about_keywords = [
            'about', 'company', 'mission', 'vision', 'story',
            'team', 'who we are', 'our story', 'history'
        ]
        
        return any(keyword in title_lower or keyword in content_lower 
                  for keyword in about_keywords)