import asyncio
import csv
import json
import logging
import re
import os
import sys

# Append the project root inside container
sys.path.insert(0, "/workspace")

from app.infrastructure.llm_gateway import LLMGateway
from app.infrastructure.nvidia_client import build_client
from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

class KYCProfile(BaseModel):
    customer_id: str
    entity_name: str
    entity_type: str = Field(description="'Organization' or 'Person'")
    country: str
    industry: str
    executives: str = ""
    beneficial_owners: str = ""
    registration_country: str = ""
    countries_of_operation: str = ""
    risk_score: int = 50
    risk_level: str = "Medium"
    adverse_media_count: int = 0
    financial_fraud_count: int = 0
    sanctions_count: int = 0
    regulatory_mentions: int = 0
    latest_incident_date: str = ""
    existing_alerts: str = ""
    risk_indicators: str = ""
    last_review_date: str = ""
    monitoring_status: str = "Active"
    kyc_status: str = "Approved"

class ProfileList(BaseModel):
    profiles: list[KYCProfile]

async def extract_profiles_from_text(text: str, gateway: LLMGateway) -> list[KYCProfile]:
    prompt = f"""
    Extract any prominent companies, organizations, or individuals mentioned in the following news excerpts.
    Generate a realistic KYC (Know Your Customer) profile for each unique entity you find.
    Focus on extracting the real names from the text. Infer reasonable defaults for missing fields like industry or country based on context.
    For risk_indicators, list any suspicious activity mentioned in the text (e.g. 'fraud', 'bribery').
    Assign higher adverse_media_count/financial_fraud_count if the text describes crimes.
    Output MUST be valid JSON matching the ProfileList schema.
    
    Text:
    {text}
    """
    try:
        result = await gateway.complete(prompt, schema=ProfileList, task_tag="extract_profiles")
        if not result.ok or result.degraded:
            log.warning(f"Gateway failed: {result.error}")
            return []
        return result.data.profiles
    except Exception as e:
        log.error(f"LLM extraction failed: {e}")
        return []

async def main():
    fraud_file = "/workspace/data/financial-data/fraud.csv"
    nonfraud_file = "/workspace/data/financial-data/nonfraud.csv"
    output_file = "/workspace/data/kyc_profiles/dataset_profiles.csv"
    
    client = build_client()
    gateway = LLMGateway(client=client)
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    samples = []
    try:
        with open(fraud_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                samples.append(row.get("title", "") + " " + row.get("summary", ""))
                count += 1
                if count >= 10:
                    break
                    
        with open(nonfraud_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                samples.append(row.get("title", "") + " " + row.get("summary", ""))
                count += 1
                if count >= 5:
                    break
    except Exception as e:
        log.error(f"Could not read datasets: {e}")
        return

    log.info(f"Loaded {len(samples)} news samples. Querying LLM...")
    
    chunk_size = 5
    all_profiles = []
    
    for i in range(0, len(samples), chunk_size):
        chunk = " ".join(samples[i:i+chunk_size])
        log.info(f"Processing chunk {i//chunk_size + 1}...")
        profiles = await extract_profiles_from_text(chunk, gateway)
        all_profiles.extend(profiles)
        
    seen = set()
    unique_profiles = []
    for p in all_profiles:
        name = p.entity_name.strip().upper()
        if name not in seen and len(name) > 2:
            seen.add(name)
            p.customer_id = f"CUST-DS-{len(unique_profiles):04d}"
            unique_profiles.append(p)
            
    log.info(f"Extracted {len(unique_profiles)} unique profiles.")
    
    if not unique_profiles:
        log.error("No profiles extracted.")
        return
        
    fieldnames = list(KYCProfile.model_fields.keys())
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in unique_profiles:
            writer.writerow(p.model_dump())
            
    log.info(f"Successfully saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
