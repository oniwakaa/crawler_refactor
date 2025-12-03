# Crawl4AI 0.7.7 API Changes

## Overview
This document summarizes the API changes from Crawl4AI that affect the LinkedIn authentication script.

## Deprecated Parameters

### CrawlerRunConfig
The following parameter has been **deprecated** and should **not** be used in version 0.7.7:


| Old Parameter | Status | Error Message |
|--------------|--------|---------------|
| `bypass_cache=True` | ❌ **DEPRECATED** | `AttributeError: Setting 'bypass_cache' is deprecated. Instead, use cache_mode=CacheMode.BYPASS` |

## Replacement Syntax

### Using CacheMode Enum

The old boolean flag `bypass_cache=True` has been replaced with the `cache_mode` parameter using the `CacheMode` enum.

#### Import Required
```python
from crawl4ai import CacheMode
from crawl4ai.async_configs import CrawlerRunConfig
```

#### Old Syntax (DEPRECATED)
```python
config = CrawlerRunConfig(bypass_cache=True)
```

#### New Syntax (CORRECT for 0.7.7)
```python
config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS)
```

## CacheMode Enum Values

The `CacheMode` enum provides five options for controlling cache behavior:

| CacheMode | Description | Use Case |
|-----------|-------------|----------|
| `CacheMode.ENABLED` | Normal caching (read/write) | Default behavior - cache is fully functional |
| `CacheMode.DISABLED` | No caching at all | Completely disable cache for all operations |
| `CacheMode.READ_ONLY` | Only read from cache | Use existing cache but don't write new entries |
| `CacheMode.WRITE_ONLY` | Only write to cache | Populate cache without reading existing entries |
| `CacheMode.BYPASS` | Skip cache for this operation | Bypass cache for a single operation |

## Migration Patterns

### Common Use Cases

| Old Flag | New Mode | When to Use |
|----------|----------|-------------|
| `bypass_cache=True` | `cache_mode=CacheMode.BYPASS` | Skip cache for single operation |
| `disable_cache=True` | `cache_mode=CacheMode.DISABLED` | Disable cache completely |
| `no_cache_read=True` | `cache_mode=CacheMode.WRITE_ONLY` | Write only, don't read cache |
| `no_cache_write=True` | `cache_mode=CacheMode.READ_ONLY` | Read only, don't write cache |

## Example Usage

```python
import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import CrawlerRunConfig

async def example():
    # Browser configuration
    browser_config = BrowserConfig(
        browser_type="chromium",
        headless=False,
        verbose=True
    )
    
    # Crawler configuration with cache mode
    crawler_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,  # Use this instead of bypass_cache
        wait_for="input[id='username']"  # Other parameters remain valid
    )
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        result = await crawler.arun(
            url="https://www.linkedin.com/login",
            config=crawler_config
        )
        
        if result.success:
            print("Page loaded successfully")
        else:
            print(f"Failed: {result.error_message}")

if __name__ == "__main__":
    asyncio.run(example())
```

## Recommended Parameters for LinkedIn Authentication

For the LinkedIn authentication script, use the following configuration for optimal results:

```python
config = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,  # Skip cache to ensure fresh login page
    wait_for="input[id='username']"  # Wait for username field to be ready
)
```

## Verification

To verify the correct API usage:
1. Check that `CacheMode` is imported: `from crawl4ai import CacheMode`
2. Verify `cache_mode` parameter is used instead of `bypass_cache`
3. Ensure no `AttributeError` about deprecated parameters is raised

## Documentation Reference

- **Crawl4AI Docs**: https://docs.crawl4ai.com/core/cache-modes/
- **Cache Mode Documentation**: https://docs.crawl4ai.com/core/cache-modes/
- **SDK Reference**: https://docs.crawl4ai.com/complete-sdk-reference/
- **Migration Guide**: https://docs.crawl4ai.com/core/cache-modes/#old-vs-new-approach

## Version Information

- **Crawl4AI Version Tested**: 0.7.7
- **Python Version**: 3.11.14
- **Platform**: macOS
- **Date**: 2024-12-01

## Additional Notes

- The `CacheMode` enum simplifies cache control by replacing multiple boolean flags with a single, intuitive parameter
- Always check the Crawl4AI documentation for any breaking changes when upgrading versions
- The error message "Setting 'bypass_cache' is deprecated" indicates usage of the old API
- Contact the Crawl4AI team at https://crawl4ai.com/ for further support
