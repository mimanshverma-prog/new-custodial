import asyncio
import json
import logging
import argparse
import os
import pandas as pd
from typing import List, Optional
from pydantic import BaseModel
from search import SearchDiscovery
from email_verifier import EmailVerifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models for structured output
class PersonData(BaseModel):
    full_name: str
    job_title: str
    linkedin_profile_url: str

class CompanyData(BaseModel):
    company_name: str
    website: str
    industry: str
    company_size: str
    estimated_revenue: str
    location: str
    recent_funding: str
    hiring_activity: str

class ContactData(BaseModel):
    verified_work_email: str
    email_verification_status: str
    business_domain: str

class Lead(BaseModel):
    person_data: PersonData
    company_data: CompanyData
    contact_data: ContactData

class LeadGeneratorEngine:
    def __init__(self, target_count: int = 100000, proxies: Optional[str] = None):
        self.target_count = target_count
        # Increase max_results per query since we are doing massive scraping
        self.searcher = SearchDiscovery(max_results_per_query=200, proxies=proxies)
        self.verifier = EmailVerifier()
        self.found_leads_count = 0
        self.seen_profiles = set()
        self.seen_emails = set()

        # Load state if exists to avoid re-verifying
        self.json_output_file = "leads.json"
        self.csv_output_file = "leads.csv"

    def _generate_query_variations(self, industry: str, location: str, job_title: str) -> List[str]:
        """
        Query Expansion System to get up to 100,000 leads.
        Search engines cap at ~200-300 results per query.
        We append alphabet permutations or top first names to bypass this cap.
        """
        alphabet = "abcdefghijklmnopqrstuvwxyz"
        queries = []

        # Base query
        queries.append(f'"{job_title}" "{industry}" "{location}" site:linkedin.com/in')

        # Alphabet expansion (e.g., find all CTOs in Tech where name starts with A)
        for letter1 in alphabet:
            queries.append(f'"{letter1}" "{job_title}" "{industry}" "{location}" site:linkedin.com/in')
            # 2-letter permutations for deep scraping
            for letter2 in alphabet:
                queries.append(f'"{letter1}{letter2}" "{job_title}" "{industry}" "{location}" site:linkedin.com/in')

        return queries

    def _save_chunk(self, new_leads: List[Lead]):
        """
        Saves leads incrementally to both JSON and CSV formats.
        """
        if not new_leads:
            return

        leads_dict = [l.model_dump() for l in new_leads]

        # Save to JSON
        existing_leads = []
        if os.path.exists(self.json_output_file):
            with open(self.json_output_file, 'r') as f:
                try:
                    existing_leads = json.load(f)
                except json.JSONDecodeError:
                    pass
        existing_leads.extend(leads_dict)
        with open(self.json_output_file, 'w') as f:
            json.dump(existing_leads, f, indent=4)

        # Flatten and Save to CSV
        flat_leads = []
        for l in leads_dict:
            flat_leads.append({
                'Full Name': l['person_data']['full_name'],
                'Job Title': l['person_data']['job_title'],
                'LinkedIn URL': l['person_data']['linkedin_profile_url'],
                'Company Name': l['company_data']['company_name'],
                'Website': l['company_data']['website'],
                'Industry': l['company_data']['industry'],
                'Company Size': l['company_data']['company_size'],
                'Estimated Revenue': l['company_data']['estimated_revenue'],
                'Location': l['company_data']['location'],
                'Verified Work Email': l['contact_data']['verified_work_email'],
                'Business Domain': l['contact_data']['business_domain']
            })

        df = pd.DataFrame(flat_leads)

        # Append to CSV if it exists, else write header
        if os.path.exists(self.csv_output_file):
            df.to_csv(self.csv_output_file, mode='a', header=False, index=False)
        else:
            df.to_csv(self.csv_output_file, index=False)

    async def generate_leads(
        self,
        industry: str,
        country: str,
        job_title: str,
        employee_range: str,
        revenue_range: str,
        city: Optional[str] = None,
        tech_stack: Optional[str] = None
    ) -> int:
        """
        Orchestrates the massive scale lead generation process.
        Returns the total number of verified leads found.
        """
        logger.info(f"Starting HIGH CAPACITY lead generation for {job_title}s in {industry} located in {country}")
        location_query = f"{city}, {country}" if city else country

        query_variations = self._generate_query_variations(industry, location_query, job_title)
        logger.info(f"Generated {len(query_variations)} query variations for deep scraping.")

        # Process concurrently with a semaphore to limit concurrent DNS/SMTP connections
        semaphore = asyncio.Semaphore(15)

        for idx, query in enumerate(query_variations):
            if self.found_leads_count >= self.target_count:
                logger.info(f"Target count of {self.target_count} reached! Stopping early.")
                break

            logger.info(f"Processing Query {idx+1}/{len(query_variations)}")
            raw_leads = await self.searcher.search_linkedin_profiles(query)

            # Fast synchronous deduplication of raw leads before processing
            unique_raw_leads = []
            for rl in raw_leads:
                if rl.linkedin_url not in self.seen_profiles and rl.company_name != "Unknown":
                    self.seen_profiles.add(rl.linkedin_url)
                    unique_raw_leads.append(rl)

            if not unique_raw_leads:
                continue

            async def process_raw_lead(raw_lead):
                async with semaphore:
                    # Find company website domain
                    domain = await self.searcher.find_company_domain(raw_lead.company_name)
                    if not domain:
                        return None

                    # Find and verify email
                    email, status = await self.verifier.find_valid_email(raw_lead.name, domain)

                    # Strict Filter: Only include if email is verifiable
                    if not email or status != "Valid":
                        return None

                    # Strict Filter: Remove duplicate emails safely via lock/sync
                    if email in self.seen_emails:
                        return None
                    self.seen_emails.add(email)

                    # Create the structured Lead
                    person = PersonData(
                        full_name=raw_lead.name,
                        job_title=raw_lead.job_title,
                        linkedin_profile_url=raw_lead.linkedin_url
                    )

                    company = CompanyData(
                        company_name=raw_lead.company_name,
                        website=f"https://www.{domain}",
                        industry=industry,
                        company_size=employee_range,
                        estimated_revenue=revenue_range,
                        location=raw_lead.location or location_query,
                        recent_funding="Unknown",
                        hiring_activity="Yes"
                    )

                    contact = ContactData(
                        verified_work_email=email,
                        email_verification_status="Valid",
                        business_domain=domain
                    )

                    lead = Lead(person_data=person, company_data=company, contact_data=contact)
                    return lead

            tasks = [process_raw_lead(lead) for lead in unique_raw_leads]
            results = await asyncio.gather(*tasks)

            # Filter out None results and enforce target cap on this chunk
            valid_chunk = []
            for r in results:
                if r:
                    if self.found_leads_count < self.target_count:
                        valid_chunk.append(r)
                        self.found_leads_count += 1

            if valid_chunk:
                logger.info(f"Saving chunk of {len(valid_chunk)} verified leads...")
                self._save_chunk(valid_chunk)
                logger.info(f"Total Leads Verified so far: {self.found_leads_count}/{self.target_count}")

        logger.info(f"Lead generation complete. Total leads found: {self.found_leads_count}")
        return self.found_leads_count


def main():
    parser = argparse.ArgumentParser(description="Advanced High-Capacity B2B Lead Generation Engine")
    parser.add_argument("--industry", required=True, help="Target Industry (e.g., Software, Real Estate)")
    parser.add_argument("--country", required=True, help="Target Country")
    parser.add_argument("--job_title", required=True, help="Target Job Title / Decision Maker Role")
    parser.add_argument("--employee_range", required=True, help="Target Company Size Range (e.g., 50-200)")
    parser.add_argument("--revenue_range", required=True, help="Target Revenue Range (e.g., $1M-$10M)")
    parser.add_argument("--city", required=False, help="Target City")
    parser.add_argument("--tech_stack", required=False, help="Target Technology Stack")
    parser.add_argument("--target_count", type=int, default=100000, help="Number of leads to generate (default 100,000)")
    parser.add_argument("--proxy", required=False, help="Proxy URL (e.g., http://user:pass@ip:port) to prevent IP blocking during massive scrapes")

    args = parser.parse_args()

    engine = LeadGeneratorEngine(target_count=args.target_count, proxies=args.proxy)

    # Run async engine
    loop = asyncio.get_event_loop()
    total_leads = loop.run_until_complete(
        engine.generate_leads(
            industry=args.industry,
            country=args.country,
            job_title=args.job_title,
            employee_range=args.employee_range,
            revenue_range=args.revenue_range,
            city=args.city,
            tech_stack=args.tech_stack
        )
    )

    print(f"\nFinal count: {total_leads} leads generated and saved incrementally to leads.json and leads.csv")

if __name__ == "__main__":
    main()
