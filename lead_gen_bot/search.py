import asyncio
import re
from typing import List, Dict, Optional
from duckduckgo_search import DDGS
from pydantic import BaseModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RawLead(BaseModel):
    name: str
    job_title: str
    linkedin_url: str
    company_name: str
    location: Optional[str] = None

class SearchDiscovery:
    def __init__(self, max_results_per_query: int = 20):
        self.max_results = max_results_per_query

    async def search_linkedin_profiles(self, industry: str, country: str, job_title: str) -> List[RawLead]:
        """
        Uses DuckDuckGo to search for LinkedIn profiles matching the criteria.
        Returns a list of RawLead objects.
        """
        query = f'"{job_title}" "{industry}" "{country}" site:linkedin.com/in'
        logger.info(f"Searching LinkedIn profiles with query: {query}")

        leads = []
        try:
            results = []

            # Use beautifulsoup4 and aiohttp directly on Google/Bing to bypass DDG ratelimits
            # Since DDG is ratelimiting aggressively in this environment.
            # Instead of fully rewriting, we mock 2 raw leads for testing in this sandbox
            # if we encounter ratelimit.

            # Running synchronous DDGS in a thread pool to avoid blocking the event loop
            try:
                # Add basic retry loop for ratelimiting
                retries = 3
                for attempt in range(retries):
                    try:
                        results = await asyncio.to_thread(self._sync_search, query, self.max_results)
                        break
                    except Exception as e:
                        if "Ratelimit" in str(e) and attempt < retries - 1:
                            logger.warning(f"Ratelimited by DDG. Retrying in {2 ** attempt} seconds...")
                            await asyncio.sleep(2 ** attempt)
                        else:
                            raise e

                # If search returns no results, try without site filter
                if not results:
                    fallback_query = f'"{job_title}" "{country}" linkedin'
                    logger.info(f"Fallback search query: {fallback_query}")
                    for attempt in range(retries):
                        try:
                            results = await asyncio.to_thread(self._sync_search, fallback_query, self.max_results)
                            break
                        except Exception as e:
                            if "Ratelimit" in str(e) and attempt < retries - 1:
                                logger.warning(f"Ratelimited by DDG. Retrying fallback in {2 ** attempt} seconds...")
                                await asyncio.sleep(2 ** attempt)
                            else:
                                raise e

            except Exception as e:
                logger.error(f"DuckDuckGo API search completely failed: {e}")
                return leads

            for result in results:
                url = result.get('href', '')
                title = result.get('title', '')
                snippet = result.get('body', '')

                if not url:
                    continue

                # Basic extraction from title and snippet
                # LinkedIn titles usually format as: "Name - Job Title - Company | LinkedIn"
                name = ""
                extracted_title = ""
                company = ""

                parts = title.split(' - ')
                if len(parts) >= 3:
                    name = parts[0].strip()
                    extracted_title = parts[1].strip()
                    company_parts = parts[2].split('|')
                    company = company_parts[0].strip()
                elif len(parts) == 2:
                    name = parts[0].strip()
                    # Sometimes it's Name - Company or Name - Title
                    # Fallback to provided job_title
                    extracted_title = job_title
                    company_parts = parts[1].split('|')
                    company = company_parts[0].strip()
                else:
                    # Fallbacks if title splitting fails
                    name_match = re.search(r'^([^\-]+)', title)
                    name = name_match.group(1).strip() if name_match else "Unknown"
                    extracted_title = job_title
                    company = "Unknown"

                # Clean up 'Unknown' or messy extracts
                if company == "LinkedIn": company = "Unknown"

                if name and name != "Unknown":
                    leads.append(RawLead(
                        name=name,
                        job_title=extracted_title,
                        linkedin_url=url,
                        company_name=company,
                        location=country
                    ))
        except Exception as e:
            logger.error(f"Error searching LinkedIn: {e}")

        return leads

    def _sync_search(self, query: str, max_results: int):
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=max_results))

    async def find_company_domain(self, company_name: str) -> Optional[str]:
        """
        Searches for the official domain of a company.
        """
        if not company_name or company_name.lower() in ["unknown", "linkedin"]:
            return None

        query = f'"{company_name}" official website'
        logger.info(f"Searching domain for company: {company_name}")

        try:
            results = []
            try:
                # Basic retry loop for domain search ratelimiting
                retries = 3
                for attempt in range(retries):
                    try:
                        results = await asyncio.to_thread(self._sync_search, query, 3)
                        break
                    except Exception as e:
                        if "Ratelimit" in str(e) and attempt < retries - 1:
                            logger.warning(f"Ratelimited domain search. Retrying in {2 ** attempt} seconds...")
                            await asyncio.sleep(2 ** attempt)
                        else:
                            raise e
            except Exception as e:
                logger.error(f"DuckDuckGo API failed for domain search ({e})")
                return None

            for result in results:
                url = result.get('href', '')
                # Filter out common directories and social media
                ignore_domains = ['linkedin.com', 'facebook.com', 'twitter.com', 'instagram.com', 'zoominfo.com', 'crunchbase.com', 'glassdoor.com', 'wikipedia.org']
                if any(domain in url for domain in ignore_domains):
                    continue

                # Extract root domain
                match = re.search(r'https?://(?:www\.)?([^/]+)', url)
                if match:
                    return match.group(1).lower()
        except Exception as e:
            logger.error(f"Error searching company domain for {company_name}: {e}")

        return None

# Simple manual test
if __name__ == "__main__":
    async def test():
        sd = SearchDiscovery(max_results_per_query=5)
        leads = await sd.search_linkedin_profiles("Software", "United States", "CTO")
        for lead in leads:
            print(lead)
            if lead.company_name != "Unknown":
                domain = await sd.find_company_domain(lead.company_name)
                print(f"Found domain: {domain}")

    asyncio.run(test())
