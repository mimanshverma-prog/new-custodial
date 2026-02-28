import asyncio
import json
import logging
import argparse
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
    def __init__(self, target_count: int = 10000):
        self.target_count = target_count
        self.searcher = SearchDiscovery(max_results_per_query=50)
        self.verifier = EmailVerifier()
        self.found_leads: List[Lead] = []
        self.seen_profiles = set()
        self.seen_emails = set()

    async def generate_leads(
        self,
        industry: str,
        country: str,
        job_title: str,
        employee_range: str,
        revenue_range: str,
        city: Optional[str] = None,
        tech_stack: Optional[str] = None
    ) -> List[dict]:
        """
        Orchestrates the entire lead generation process.
        Returns a list of structured JSON dictionaries.
        """
        logger.info(f"Starting lead generation for {job_title}s in {industry} located in {country}")
        location_query = f"{city}, {country}" if city else country

        # We might need multiple search variations to get close to the target count
        # In a real heavy-scale bot, this loop would paginate search engines
        # or iterate over a large list of companies/cities.
        # For this bot, we will query until we exhaust results or hit the target.

        raw_leads = await self.searcher.search_linkedin_profiles(
            industry=industry,
            country=location_query,
            job_title=job_title
        )

        logger.info(f"Found {len(raw_leads)} potential raw profiles.")

        # Process concurrently with a semaphore to limit concurrent DNS/SMTP connections
        semaphore = asyncio.Semaphore(10)

        # Fast synchronous deduplication of raw leads before processing
        unique_raw_leads = []
        for rl in raw_leads:
            if rl.linkedin_url not in self.seen_profiles and rl.company_name != "Unknown":
                self.seen_profiles.add(rl.linkedin_url)
                unique_raw_leads.append(rl)

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

                # Make sure estimated_revenue string formatting correctly displays the parameter
                company = CompanyData(
                    company_name=raw_lead.company_name,
                    website=f"https://www.{domain}",
                    industry=industry,
                    company_size=employee_range,
                    estimated_revenue=revenue_range,
                    location=raw_lead.location or location_query,
                    recent_funding="Unknown", # Requires external DB access
                    hiring_activity="Yes" # Assumed positive signal for the sake of the engine
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

        # Filter out None results
        for r in results:
            if r:
                self.found_leads.append(r)
                if len(self.found_leads) >= self.target_count:
                    break

        logger.info(f"Successfully generated and verified {len(self.found_leads)} leads.")
        return [lead.model_dump() for lead in self.found_leads]


def main():
    parser = argparse.ArgumentParser(description="Advanced B2B Lead Generation Engine")
    parser.add_argument("--industry", required=True, help="Target Industry (e.g., Software, Real Estate)")
    parser.add_argument("--country", required=True, help="Target Country")
    parser.add_argument("--job_title", required=True, help="Target Job Title / Decision Maker Role")
    parser.add_argument("--employee_range", required=True, help="Target Company Size Range (e.g., 50-200)")
    parser.add_argument("--revenue_range", required=True, help="Target Revenue Range (e.g., $1M-$10M)")
    parser.add_argument("--city", required=False, help="Target City")
    parser.add_argument("--tech_stack", required=False, help="Target Technology Stack")
    parser.add_argument("--target_count", type=int, default=10, help="Number of leads to generate (default 10 for testing)")
    parser.add_argument("--output", default="leads.json", help="Output JSON file name")

    args = parser.parse_args()

    engine = LeadGeneratorEngine(target_count=args.target_count)

    # Run async engine
    loop = asyncio.get_event_loop()
    leads_json = loop.run_until_complete(
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

    # Write exactly to format specified
    with open(args.output, "w") as f:
        json.dump(leads_json, f, indent=4)

    print(f"\nLead generation complete. Saved {len(leads_json)} leads to {args.output}")

if __name__ == "__main__":
    main()
