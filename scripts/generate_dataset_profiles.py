import asyncio
import csv
import json
import logging
import re
import os
import sys

# Add parent dir to path so we can import app modules if run from scripts/
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.infrastructure.llm_gateway import LLMGateway
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

async def extract_profiles_from_text(text: str) -> list[KYCProfile]:
    prompt = f"""
    Extract any prominent companies, organizations, or individuals mentioned in the following news excerpts.
    Generate a realistic KYC (Know Your Customer) profile for each unique entity you find.
    Focus on extracting the real names from the text. Infer reasonable defaults for missing fields like industry or country based on context.
    For risk_indicators, list any suspicious activity mentioned in the text (e.g. 'fraud', 'bribery').
    Assign higher adverse_media_count/financial_fraud_count if the text describes crimes.
    
    Text:
    {text}
    """
    try:
        # Using LLMGateway
        from app.infrastructure.nvidia_client import build_client
        gw = LLMGateway(client=build_client(), max_attempts_per_model=1)
        result = await gw.complete(prompt, schema=ProfileList, task_tag="extract_profiles")
        return result.unwrap().profiles
    except Exception as e:
        log.error(f"LLM extraction failed: {e}")
        return []

import random
import yaml
from datetime import datetime, timedelta

def load_policy_bands():
    try:
        with open("policy.yaml", "r") as f:
            policy = yaml.safe_load(f)
        return policy.get("bands", {"medium": 40, "high": 60, "critical": 80})
    except Exception:
        return {"medium": 40, "high": 60, "critical": 80}

def get_risk_level(score, bands):
    if score < bands.get("medium", 40):
        return "LOW"
    elif score < bands.get("high", 60):
        return "MEDIUM"
    elif score < bands.get("critical", 80):
        return "HIGH"
    else:
        return "CRITICAL"

def generate_synthetic_profiles(count: int) -> list[KYCProfile]:
    bands = load_policy_bands()
    medium_threshold = bands.get("medium", 40)
    high_threshold = bands.get("high", 60)
    critical_threshold = bands.get("critical", 80)
    
    profiles = []
    first_names = ["John", "Jane", "Alice", "Bob", "Charlie", "Diana", "Edward", "Fiona", "George", "Hannah", "Michael", "Sarah", "David", "Emma", "James", "Olivia"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Chen", "Lee", "Wong", "Kim"]
    company_prefixes = ["Global", "Apex", "Nova", "Quantum", "Nexus", "Stellar", "Pinnacle", "Vertex", "Horizon", "Zenith", "Meridian", "Alpha", "Omega"]
    company_suffixes = ["Solutions", "Technologies", "Holdings", "Group", "Partners", "Capital", "Logistics", "Energy", "Ventures", "Corp", "Inc"]
    industries = ["Finance", "Technology", "Real Estate", "Healthcare", "Energy", "Retail", "Manufacturing", "Logistics"]
    countries = ["US", "GB", "CA", "DE", "FR", "SG", "JP", "CH", "KY"]

    for _ in range(count):
        is_person = random.choice([True, False])
        if is_person:
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            entity_type = "Person"
            industry = random.choice(["Consulting", "Finance", "Legal", "Technology", "None"])
        else:
            name = f"{random.choice(company_prefixes)} {random.choice(company_suffixes)}"
            entity_type = "Organization"
            industry = random.choice(industries)
            
        country = random.choice(countries)
        
        # Risk score generation: skewed towards lower risks
        risk_score = random.choices(
            [random.randint(10, medium_threshold - 1), 
             random.randint(medium_threshold, high_threshold - 1), 
             random.randint(high_threshold, critical_threshold - 1),
             random.randint(critical_threshold, 99)], 
            weights=[0.4, 0.4, 0.15, 0.05]
        )[0]
        
        risk_level = get_risk_level(risk_score, bands)
        
        if risk_level == "LOW":
            adverse = 0
            fraud = 0
            sanc = 0
            mentions = random.randint(0, 1)
            indicators = ""
        elif risk_level == "MEDIUM":
            adverse = random.randint(0, 2)
            fraud = random.randint(0, 1)
            sanc = 0
            mentions = random.randint(1, 3)
            indicators = random.choice(["", "Suspicious transaction", "Unusual behavior"])
        elif risk_level == "HIGH":
            adverse = random.randint(1, 4)
            fraud = random.randint(0, 2)
            sanc = random.randint(0, 1)
            mentions = random.randint(2, 4)
            indicators = random.choice(["Fraud", "Money Laundering", "Multiple alerts"])
        else: # CRITICAL
            adverse = random.randint(2, 5)
            fraud = random.randint(1, 3)
            sanc = random.randint(0, 2)
            mentions = random.randint(3, 5)
            indicators = random.choice(["Sanctions Hit", "Severe Fraud", "Terrorist Financing Hit"])

        days_ago = random.randint(10, 500)
        incident_date = (datetime.now() - timedelta(days=days_ago)).strftime("%Y-%m-%d") if adverse > 0 else ""

        p = KYCProfile(
            customer_id="",
            entity_name=name,
            entity_type=entity_type,
            country=country,
            industry=industry,
            risk_score=risk_score,
            risk_level=risk_level,
            adverse_media_count=adverse,
            financial_fraud_count=fraud,
            sanctions_count=sanc,
            regulatory_mentions=mentions,
            risk_indicators=indicators,
            latest_incident_date=incident_date,
            monitoring_status="Active",
            kyc_status="Approved"
        )
        profiles.append(p)
    return profiles

async def main():
    fraud_file = "data/financial-data/fraud.csv"
    nonfraud_file = "data/financial-data/nonfraud.csv"
    output_file = "data/kyc_profiles/dataset_profiles.csv"
    
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    
    # We will sample texts to extract entities from
    samples = []
    try:
        with open(fraud_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                samples.append(row.get("title", "") + " " + row.get("summary", ""))
                count += 1
                if count >= 15: # Take 15 fraud articles
                    break
                    
        with open(nonfraud_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            count = 0
            for row in reader:
                samples.append(row.get("title", "") + " " + row.get("summary", ""))
                count += 1
                if count >= 10: # Take 10 non-fraud articles
                    break
    except Exception as e:
        log.error(f"Could not read datasets: {e}")
        return

    log.info(f"Loaded {len(samples)} news samples. Querying LLM to extract KYC profiles...")
    
    # Group samples to reduce API calls
    chunk_size = 5
    all_profiles = []
    
    for i in range(0, len(samples), chunk_size):
        chunk = " ".join(samples[i:i+chunk_size])
        log.info(f"Processing chunk {i//chunk_size + 1}...")
        profiles = await extract_profiles_from_text(chunk)
        all_profiles.extend(profiles)
        
    # Supplement with completely synthetic profiles not related to news (both org and person)
    log.info("Generating 50 synthetic KYC profiles (mixed risk levels, clean/dirty)...")
    synthetic_profiles = generate_synthetic_profiles(count=50)
    all_profiles.extend(synthetic_profiles)
        
    # Deduplicate by entity_name and normalize risk_levels based on policy.yaml
    seen = set()
    unique_profiles = []
    bands = load_policy_bands()
    for p in all_profiles:
        name = p.entity_name.strip().upper()
        if name not in seen and len(name) > 2:
            seen.add(name)
            p.customer_id = f"CUST-DS-{len(unique_profiles):04d}"
            p.risk_level = get_risk_level(p.risk_score, bands)
            unique_profiles.append(p)
            
    log.info(f"Generated {len(unique_profiles)} unique profiles total.")
    
    if not unique_profiles:
        log.error("No profiles extracted.")
        return
        
    # Save to CSV
    fieldnames = list(KYCProfile.model_fields.keys())
    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for p in unique_profiles:
            writer.writerow(p.model_dump())
            
    log.info(f"Successfully saved to {output_file}")

if __name__ == "__main__":
    asyncio.run(main())
