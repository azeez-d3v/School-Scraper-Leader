import asyncio
import logging
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

class PlaywrightManager:
    """A utility for handling browser-based scraping with Playwright.
    
    This class provides methods for navigating to pages and extracting HTML
    from modern, JavaScript-heavy websites that use loaders or other dynamic
    content loading methods.
    """
    
    def __init__(self):
        self.browser = None
        self.context = None
        self._is_initialized = False
    
    async def initialize(self):
        """Initialize the Playwright browser if not already initialized."""
        if not self._is_initialized:
            try:
                self.playwright = await async_playwright().start()
                self.browser = await self.playwright.webkit.launch(headless=False)
                self.context = await self.browser.new_context()
                self._is_initialized = True
                logger.info("Playwright browser initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Playwright browser: {e}")
                raise
    
    async def get_page_content(self, url, wait_for_selector=None, wait_time=5000):
        """
        Navigate to a URL and return the page content after JavaScript has loaded.
        
        Args:
            url (str): The URL to navigate to
            wait_for_selector (str, optional): CSS selector to wait for before extracting content
            wait_time (int, optional): Time to wait in milliseconds for the page to load
        
        Returns:
            str: The HTML content of the page after JavaScript has loaded
        """
        await self.initialize()
        
        try:
            page = await self.context.new_page()
            
            # Navigate to the URL
            await page.goto(url, wait_until="networkidle")
            
            # Wait for a specific selector if provided (used for pages with dynamic content)
            if wait_for_selector:
                try:
                    await page.wait_for_selector(wait_for_selector, timeout=wait_time)
                except Exception as e:
                    logger.warning(f"Selector '{wait_for_selector}' not found on page: {e}")
            else:
                # Otherwise just wait a moment for any animations/transitions
                await page.wait_for_timeout(2000)
            
            # Get the page content after waiting
            content = await page.content()
            
            # Close the page to free resources
            await page.close()
            
            return content
        
        except Exception as e:
            logger.error(f"Error fetching page with Playwright: {url}, error: {e}")
            raise
    
    async def close(self):
        """Close the browser and clean up resources."""
        if self._is_initialized:
            try:
                await self.context.close()
                await self.browser.close()
                await self.playwright.stop()
                self._is_initialized = False
                logger.info("Playwright browser closed")
            except Exception as e:
                logger.error(f"Error closing Playwright browser: {e}")
                raise