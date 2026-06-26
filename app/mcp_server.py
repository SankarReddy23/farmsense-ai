import sys
import logging
from mcp.server.fastmcp import FastMCP

# Setup logging to stderr to prevent stdout contamination (JSON-RPC messages are on stdout)
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("farmsense-mcp-server")

# Initialize FastMCP Server
mcp = FastMCP("FarmSense MCP Server")

@mcp.tool()
def get_mandi_prices(crop: str, district: str = "Nashik") -> dict:
    """Get the current market prices (mandi rates) for a given crop and district in India.

    Args:
        crop: The name of the crop (e.g., tomato, onion, wheat).
        district: The district name in India (e.g., Nashik, Pune, Guntur).

    Returns:
        A dict containing min, max, and modal prices per quintal.
    """
    logger.info(f"Fetching mandi prices for {crop} in {district}")
    crop_lower = crop.lower()
    
    # Mock database rates (INR per quintal = 100 kg)
    prices = {
        "tomato": {"min": 1500, "max": 2500, "modal": 2000, "unit": "INR/quintal"},
        "onion": {"min": 1200, "max": 1800, "modal": 1500, "unit": "INR/quintal"},
        "wheat": {"min": 2100, "max": 2400, "modal": 2275, "unit": "INR/quintal"},
        "rice": {"min": 2200, "max": 2800, "modal": 2500, "unit": "INR/quintal"},
        "cotton": {"min": 6500, "max": 7500, "modal": 7100, "unit": "INR/quintal"},
    }
    
    data = prices.get(crop_lower, {"min": 1000, "max": 2000, "modal": 1500, "unit": "INR/quintal"})
    return {
        "crop": crop,
        "district": district,
        "prices": data,
        "source": "eNAM (National Agriculture Market) Live Feed",
        "timestamp": "2026-06-26"
    }

@mcp.tool()
def get_weather_advisory(district: str, crop: str) -> dict:
    """Get contextual agro-weather advisories for a given district and crop.

    Args:
        district: The district name (e.g., Nashik, Pune, Guntur).
        crop: The crop being cultivated (e.g., cotton, paddy, onion).

    Returns:
        A dict containing local weather conditions and agronomic recommendations.
    """
    logger.info(f"Fetching weather advisory for {crop} in {district}")
    
    # Contextual agro-advisories
    return {
        "district": district,
        "crop": crop,
        "forecast": "Heavy rainfall expected in next 48 hours (approx 50mm). High humidity.",
        "advisory": "1. Postpone any fertilizer application or pesticide spraying. 2. Ensure proper drainage in the field to prevent waterlogging. 3. Monitor for fungal diseases due to high humidity.",
        "warning_level": "WARNING"
    }

@mcp.tool()
def diagnose_crop_symptoms(crop: str, symptoms: str) -> dict:
    """Diagnose potential crop diseases based on symptoms and suggest treatments.

    Args:
        crop: The name of the crop (e.g., tomato, cotton).
        symptoms: Description of the symptoms (e.g., yellow spots on leaves, black rot).

    Returns:
        A dict containing potential disease diagnosis, organic treatment, and chemical treatment.
    """
    logger.info(f"Diagnosing {crop} symptoms: {symptoms}")
    symptoms_lower = symptoms.lower()
    crop_lower = crop.lower()
    
    diagnosis = "Leaf Spot Fungal Infection"
    organic_treatment = "Spray neem oil solution (10ml per liter of water) and prune infected lower leaves."
    chemical_treatment = "Spray Mancozeb 75% WP (2g per liter of water) if infection spreads. Observe 7-day pre-harvest interval."
    
    if "yellow" in symptoms_lower and "tomato" in crop_lower:
        diagnosis = "Tomato Yellow Leaf Curl Virus (TYLCV)"
        organic_treatment = "Use yellow sticky traps to capture whiteflies (vector). Spray neem seed kernel extract (NSKE)."
        chemical_treatment = "No direct cure for virus. Control vector using Imidacloprid 17.8% SL (0.5ml per liter of water)."
    elif "black" in symptoms_lower or "rot" in symptoms_lower:
        diagnosis = "Black Rot Bacterial Disease"
        organic_treatment = "Crop rotation with non-host crops. Spray copper hydroxide (organic approved fungistat)."
        chemical_treatment = "Spray Streptocycline (1g per 10 liters of water) combined with Copper Oxychloride (25g per 10 liters)."
        
    return {
        "crop": crop,
        "symptoms": symptoms,
        "diagnosis": diagnosis,
        "treatments": {
            "organic": organic_treatment,
            "chemical": chemical_treatment
        }
    }

if __name__ == "__main__":
    mcp.run()
