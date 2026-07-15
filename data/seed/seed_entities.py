import os
import csv
import yaml
from app.models.base import Base, engine
from app.models.entities import Entity
from app.repositories.unit_of_work import UnitOfWork

CSV_PATH = "data/kyc_profiles/dataset_profiles.csv"

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
    
    if not os.path.exists(CSV_PATH):
        print(f"Dataset profiles not found at {CSV_PATH}. Please run generate_dataset_profiles.py first.")
        return
        
    entities_to_add = []
    watched_count = 0
    
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            client_id = row.get("customer_id")
            name = row.get("entity_name")
            country = row.get("country")
            sector = row.get("industry")
            
            # Use dynamic risk provided by the dataset generation initially, 
            # the pipeline will update this dynamically later.
            try:
                base_score = float(row.get("risk_score", 50))
            except ValueError:
                base_score = 50.0
                
            risk_band = row.get("risk_level", "MEDIUM").upper()
            status = row.get("kyc_status", "ACTIVE").upper()
            if status == "APPROVED":
                status = "ACTIVE"
            
            # Watch entities with adverse media or fraud
            fraud_count = int(row.get("financial_fraud_count", 0) or 0)
            adverse_media = int(row.get("adverse_media_count", 0) or 0)
            watched = (fraud_count > 0 or adverse_media > 0 or base_score >= 60)
            
            if watched:
                watched_count += 1
                
            entity = Entity(
                id=client_id,
                name=name,
                jurisdiction=country,
                sector=sector,
                risk_score=base_score,
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
        
    print(f"Successfully seeded {len(entities_to_add)} dataset-derived entities into the database.")
    print(f"Watched entities count: {watched_count}")

if __name__ == "__main__":
    seed()
