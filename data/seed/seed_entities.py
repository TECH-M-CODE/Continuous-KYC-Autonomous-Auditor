import os
import csv
import yaml
from app.models.base import Base, engine
from app.models.entities import Entity
from app.repositories.unit_of_work import UnitOfWork

CSV_PATH = "data/kyc_profiles/synthetic_kyc_dataset.csv"

def generate_mock_csv():
    # Make sure parent directory exists
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)
    
    headers = [
        "client_id", "client_name", "client_type", "country", 
        "sector", "sector_risk", "pep_flag", "sanctions_flag", "fatf_country_flag"
    ]
    
    # Generate 100 mock companies
    data = []
    sectors = ["Finance", "Real Estate", "Mining", "Tech", "Retail", "Energy"]
    sector_risks = {
        "Finance": "High",
        "Real Estate": "High",
        "Mining": "High",
        "Tech": "Medium",
        "Retail": "Low",
        "Energy": "Medium"
    }
    countries = ["US", "DE", "GB", "CH", "KY", "IR", "KP", "SG", "JP"]
    fatf_countries = ["KY", "IR", "KP"] # Cayman Islands, Iran, North Korea
    
    for i in range(1, 101):
        c_id = f"C_{i:04d}"
        sector = sectors[i % len(sectors)]
        sector_risk = sector_risks[sector]
        country = countries[i % len(countries)]
        fatf = 1 if country in fatf_countries else 0
        pep = 1 if i % 15 == 0 else 0
        sanctioned = 1 if i % 33 == 0 else 0
        name = f"Global {sector} Solutions {i}"
        client_type = "Corporate"
        if i % 10 == 0:
            client_type = "Financial Institution"
            
        data.append([c_id, name, client_type, country, sector, sector_risk, pep, sanctioned, fatf])
        
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        writer.writerows(data)
    print(f"Generated fallback mock KYC dataset with 100 records at {CSV_PATH}")

def seed():
    # Ensure database tables exist
    Base.metadata.create_all(bind=engine)
    
    # Check and generate fallback CSV if dataset is not found
    if not os.path.exists(CSV_PATH):
        generate_mock_csv()
        
    # Read policy weights from policy.yaml
    policy_path = "policy.yaml"
    pep_weight = 15
    fatf_weight = 10
    sector_risk_map = {"Low": 0, "Medium": 5, "High": 12}
    
    if os.path.exists(policy_path):
        with open(policy_path, "r") as f:
            policy = yaml.safe_load(f) or {}
            weights = policy.get("weights", {})
            pep_weight = weights.get("pep_flag", 15)
            fatf_weight = weights.get("fatf_country_flag", 10)
            sector_risk_map = policy.get("sector_risk", sector_risk_map)
            
    entities_to_add = []
    watched_count = 0
    
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            client_id = row["client_id"]
            name = row["client_name"]
            country = row["country"]
            sector = row["sector"]
            sector_risk = row["sector_risk"]
            pep_flag = int(row["pep_flag"])
            sanctions_flag = int(row["sanctions_flag"])
            fatf_country_flag = int(row["fatf_country_flag"])
            
            # Base risk score calculation
            base_score = pep_flag * pep_weight + fatf_country_flag * fatf_weight + sector_risk_map.get(sector_risk, 0)
            
            # Watched status rules: pep OR fatf OR sector_risk == 'High' (plus direct sanctions check)
            watched = (pep_flag == 1 or fatf_country_flag == 1 or sector_risk == "High" or sanctions_flag == 1)
            if watched:
                watched_count += 1
                
            risk_band = "LOW"
            if base_score >= 80:
                risk_band = "CRITICAL"
            elif base_score >= 60:
                risk_band = "HIGH"
            elif base_score >= 40:
                risk_band = "MEDIUM"
                
            status = "ACTIVE"
            if sanctions_flag == 1:
                status = "UNDER_INVESTIGATION"
                
            entity = Entity(
                id=client_id,
                name=name,
                jurisdiction=country,
                sector=sector,
                risk_score=float(base_score),
                risk_band=risk_band,
                status=status,
                watched=watched
            )
            entities_to_add.append(entity)
            
    # Persist via UnitOfWork context manager
    with UnitOfWork() as uow:
        # Clear existing entities to allow clean re-runs
        existing = uow.entities.list()
        for ext in existing:
            uow.session.delete(ext)
        uow.commit()
        
        for entity in entities_to_add:
            uow.entities.add(entity)
        uow.commit()
        
    print(f"Successfully seeded {len(entities_to_add)} entities into the database.")
    print(f"Watched entities count: {watched_count}")

if __name__ == "__main__":
    seed()
