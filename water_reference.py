#!/usr/bin/env python3
"""
Reference tables and lightweight interpreters for Northern Health water data.

The constants here preserve source terminology while making bacteriological
codes and chemical guideline rows available to downstream analysis code.
"""

import re


REFERENCE_SOURCES = [
    {
        "name": "Northern Health Authority Chemical Samples & Results",
        "url": "https://www.healthspace.ca/Clients/NHA/NHA_Website.nsf/Water-Samples-Frameset?OpenPage",
        "notes": "Quick-reference table last updated September 2019.",
    },
    {
        "name": "Health Canada Guidelines for Canadian Drinking Water Quality - Summary Tables",
        "url": "https://www.canada.ca/en/health-canada/services/environmental-workplace-health/reports-publications/water-quality/guidelines-canadian-drinking-water-quality-summary-table.html",
        "notes": "Used for scraped parameters missing from the Northern Health quick-reference table.",
    },
]


BACTERIOLOGICAL_DEFINITIONS = {
    "total_coliforms": (
        "Total coliforms are organisms found in the environment, including on "
        "plants, animals, and humans. Northern Health uses them as indicator "
        "organisms; if present, other organisms may also be present."
    ),
    "fecal_coliforms": "Bacterial contamination from human or animal waste (feces).",
    "escherichia_coli": "Bacterial contamination from human or animal waste (feces).",
}


BACTERIOLOGICAL_CODES = {
    "A": {
        "meaning": "Not tested; likely sample is too long in transit to the lab.",
        "status": "not_tested",
    },
    "BG": {
        "meaning": "Non-coliform background bacteria colonies.",
        "status": "background_growth",
    },
    "B#": {
        "meaning": "Number of non-coliform background bacteria colonies; high numbers (>200) may indicate deteriorating water quality.",
        "status": "background_growth",
    },
    "CFU": {
        "meaning": "Colony forming units.",
        "status": "unit",
    },
    "E. COLI": {
        "meaning": "Escherichia coli.",
        "status": "organism",
    },
    "EST": {
        "meaning": "Estimated count.",
        "status": "estimated",
    },
    "L1": {
        "meaning": "Less than 1 (<1), essentially 0. Satisfactory.",
        "status": "satisfactory",
    },
    "LT1": {
        "meaning": "Less than 1 (<1), essentially 0. Satisfactory.",
        "status": "satisfactory",
    },
    "OG": {
        "meaning": "Overgrowth of bacterial colonies; not possible to count coliform bacteria.",
        "status": "unsatisfactory",
    },
    "R": {
        "meaning": "Not tested; resample is likely required.",
        "status": "resample_required",
    },
    "T": {
        "meaning": "Not tested; likely sample is too long in transit to the lab.",
        "status": "not_tested",
    },
    "TNTC": {
        "meaning": "Too numerous to count; similar to OG.",
        "status": "unsatisfactory",
    },
}


BACTERIOLOGICAL_GUIDELINES = [
    {
        "parameter": "E.Coli",
        "result": "< 1",
        "description": (
            "If exceeded, water is unsafe to use for drinking, washing vegetables, "
            "or oral hygiene."
        ),
    },
    {
        "parameter": "Total Coliform",
        "result": "< 1",
        "description": (
            "If exceeded, water is suspect and further investigation is needed to "
            "determine safety of water system."
        ),
    },
    {
        "parameter": "Background Growth",
        "result": "> 200",
        "description": (
            "Although not pathogenic, exceedance suggests flushing/disinfection of "
            "distribution system."
        ),
    },
]


CHEMICAL_PARAMETER_GUIDELINES = [
    {"parameter": "Alkalinity", "result": "No limit", "description": "Affects water treatment"},
    {
        "parameter": "Aluminum",
        "result": "No limit",
        "description": "Affects water treatment coagulation",
    },
    {"parameter": "Ammonia", "result": "No limit", "description": "Aesthetic objective"},
    {"parameter": "Antimony", "result": "0.006 mg/L", "description": "Significant health risk"},
    {
        "parameter": "Arsenic",
        "result": "0.01 mg/L",
        "description": "High health risk (ALARA - as low as reasonably achievable)",
    },
    {"parameter": "Barium", "result": "1 mg/L", "description": "Low health risk"},
    {"parameter": "Benzene", "result": "0.005 mg/L", "description": "High health risk"},
    {"parameter": "Boron", "result": "5 mg/L", "description": "Low health risk"},
    {"parameter": "Cadmium", "result": "0.005 mg/L", "description": "Low health risk"},
    {"parameter": "Calcium", "result": "No limit", "description": "Contributes to hardness"},
    {"parameter": "Chloride", "result": "<= 250 mg/L", "description": "Aesthetic objective"},
    {"parameter": "Chromium", "result": "0.05 mg/L", "description": "Low health risk"},
    {"parameter": "Colour", "result": "<= 5 TCU", "description": "Aesthetic objective"},
    {"parameter": "Conductivity", "result": "No limit", "description": ""},
    {
        "parameter": "Copper",
        "result": "<= 1.0 mg/L",
        "description": "Aesthetic objective. Causes green staining of laundry and plumbing fixtures",
    },
    {
        "parameter": "Corrosivity",
        "result": "No limit",
        "description": "Risk from dissolution of heavy metals, especially lead and copper",
    },
    {"parameter": "Ethylbenzene", "result": "<= 0.14 mg/L", "description": "Aesthetic objective"},
    {"parameter": "Fluoride", "result": "1.5 mg/L", "description": "0.8-1.0 mg/L recommended"},
    {"parameter": "Hardness", "result": "80-100 mg/L", "description": "Aesthetic objective"},
    {
        "parameter": "Iron",
        "result": "<= 0.3 mg/L",
        "description": "Undesirable tastes, stains laundry and plumbing fixtures.",
    },
    {
        "parameter": "Langelier Saturation Index",
        "result": "No Health Canada limit",
        "description": "Operational scaling indicator described in the Health Canada pH technical document; not a corrosion index and not assigned a drinking-water limit.",
    },
    {
        "parameter": "Lead",
        "result": "0.005 mg/L",
        "description": "Chronic health effects (ALARA - as low as reasonably achievable)",
    },
    {
        "parameter": "Bromide",
        "result": "No Health Canada limit",
        "description": "NOM/DBP operational monitoring parameter; Health Canada discusses bromide as affecting disinfection by-product formation, but does not establish a direct bromide guideline value.",
    },
    {
        "parameter": "Chlorine Demand",
        "result": "No Health Canada limit",
        "description": "Operational indicator used to assess NOM character and disinfectant demand; no numeric Health Canada drinking-water limit.",
    },
    {
        "parameter": "Lignin",
        "result": "No Health Canada limit",
        "description": "Natural organic matter component and disinfection by-product precursor; no numeric Health Canada drinking-water limit.",
    },
    {"parameter": "Magnesium", "result": "No limit", "description": ""},
    {"parameter": "Manganese", "result": "<= 0.12 mg/L", "description": "Health risk"},
    {
        "parameter": "Mercury",
        "result": "0.001 mg/L",
        "description": "Health Canada MAC. Health basis: irreversible neurological symptoms.",
    },
    {"parameter": "Molybdenum", "result": "No limit", "description": ""},
    {"parameter": "Nickel", "result": "No limit", "description": ""},
    {
        "parameter": "Nitrate NO3",
        "result": "45 mg/L",
        "description": (
            "Some labs report as N, which is equal to 10 mg/L as nitrate-nitrogen"
        ),
    },
    {
        "parameter": "Nitrite NO2",
        "result": "3.2 mg/L",
        "description": (
            "Some labs report as N, which is equal to 1 mg/L as nitrite-nitrogen"
        ),
    },
    {"parameter": "Nitrogen, organic", "result": "No limit", "description": ""},
    {
        "parameter": "Nitrogen",
        "result": "No Health Canada limit",
        "description": "Generic nitrogen result; Health Canada guideline values apply to nitrate and nitrite separately.",
    },
    {
        "parameter": "pH",
        "result": "7.0-10.5",
        "description": (
            "Goal is to produce water in which corrosion and incrustation are minimized"
        ),
    },
    {"parameter": "Phosphorus", "result": "No limit", "description": ""},
    {"parameter": "Potassium", "result": "No limit", "description": ""},
    {"parameter": "Selenium", "result": "0.01 mg/L", "description": "Nutritional considerations"},
    {
        "parameter": "Silica",
        "result": "No Health Canada limit",
        "description": "No Health Canada drinking-water guideline value identified.",
    },
    {"parameter": "Silver", "result": "No limit", "description": ""},
    {
        "parameter": "Sodium",
        "result": "<= 200 mg/L",
        "description": "Aesthetic objective. Tastes are offensive, diets may be sodium restricted",
    },
    {
        "parameter": "Strontium",
        "result": "7.0 mg/L",
        "description": "Health Canada MAC. Health basis: bone effects.",
    },
    {
        "parameter": "Solids - Suspended",
        "result": "No Health Canada limit",
        "description": "No Health Canada drinking-water guideline value identified; turbidity is the related guideline parameter, but TSS is not equivalent.",
    },
    {
        "parameter": "Tannins",
        "result": "No Health Canada limit",
        "description": "Natural organic matter component and disinfection by-product precursor; no numeric Health Canada drinking-water limit.",
    },
    {
        "parameter": "Sulphate",
        "result": "<= 500 mg/L",
        "description": "Aesthetic objective. May have laxative effect",
    },
    {"parameter": "Sulphide", "result": "<= 0.05 mg/L", "description": "Disagreeable tastes and odours."},
    {"parameter": "Toluene", "result": "<= 0.06 mg/L", "description": "Health risk"},
    {
        "parameter": "Total Dissolved Solids",
        "result": "<= 500 mg/L",
        "description": (
            "Aesthetic objective. At higher levels, excessive hardness, unpalatability, "
            "mineral deposition and corrosion may occur"
        ),
    },
    {
        "parameter": "Total Organic Carbon",
        "result": "No limit",
        "description": "Degree of carbon loading for treatment considerations",
    },
    {"parameter": "Turbidity", "result": "<= 1 NTU", "description": "Limits effectiveness of UV disinfection"},
    {
        "parameter": "Haloacetic Acids",
        "result": "0.08 mg/L",
        "description": "Health Canada MAC for total HAAs, expressed as a locational running annual average of quarterly samples.",
    },
    {
        "parameter": "Bromochloroacetic Acid",
        "result": "No current Health Canada limit",
        "description": "Haloacetic acid component. Health Canada has proposed including bromochloroacetic acid in HAA6, but the current established guideline is for total HAAs/HAA5.",
    },
    {
        "parameter": "Tribromoacetic Acid",
        "result": "No current Health Canada limit",
        "description": "Haloacetic acid component without a current individual Health Canada drinking-water guideline value.",
    },
    {
        "parameter": "Bromodichloracetic Acid",
        "result": "No current Health Canada limit",
        "description": "Haloacetic acid component without a current individual Health Canada drinking-water guideline value.",
    },
    {
        "parameter": "Chlorodibromoacetic Acid",
        "result": "No current Health Canada limit",
        "description": "Haloacetic acid component without a current individual Health Canada drinking-water guideline value.",
    },
    {
        "parameter": "Trihalomethanes",
        "result": "0.1 mg/L",
        "description": "Health Canada MAC for total THMs, expressed as a locational running annual average of quarterly samples.",
    },
    {
        "parameter": "Odour",
        "result": "Inoffensive",
        "description": "Health Canada aesthetic objective.",
    },
    {
        "parameter": "Dalapon",
        "result": "No Health Canada limit",
        "description": "No current Health Canada drinking-water guideline value identified.",
    },
    {
        "parameter": "Styrene",
        "result": "No Health Canada limit",
        "description": "No current Health Canada drinking-water guideline value identified.",
    },
    {
        "parameter": "Giardia",
        "result": "Minimum 3 log removal/inactivation",
        "description": "Health Canada treatment goal for enteric protozoa.",
    },
    {
        "parameter": "Cryptosporidium",
        "result": "Minimum 3 log removal/inactivation",
        "description": "Health Canada treatment goal for enteric protozoa.",
    },
    {
        "parameter": "Uranium",
        "result": "0.02 mg/L",
        "description": "Health Canada MAC. Health basis: kidney effects.",
    },
    {
        "parameter": "Silicon",
        "result": "No Health Canada limit",
        "description": "No Health Canada drinking-water guideline value identified.",
    },
    {
        "parameter": "Vanadium",
        "result": "No Health Canada limit",
        "description": "Listed by Health Canada for guideline prioritization, but no current drinking-water guideline value identified.",
    },
    {
        "parameter": "2,3-Dibromopropionic acid",
        "result": "No Health Canada limit",
        "description": "No current Health Canada drinking-water guideline value identified.",
    },
    {
        "parameter": "Bromofluorobenzene",
        "result": "No Health Canada limit",
        "description": "Laboratory surrogate/recovery compound; no Health Canada drinking-water guideline value identified.",
    },
    {
        "parameter": "Dibromofluoromethane",
        "result": "No Health Canada limit",
        "description": "Laboratory surrogate/recovery compound; no Health Canada drinking-water guideline value identified.",
    },
    {
        "parameter": "Toluene-d8",
        "result": "No Health Canada limit",
        "description": "Laboratory surrogate/recovery compound; no Health Canada drinking-water guideline value identified.",
    },
    {
        "parameter": "UV Transmittance",
        "result": "Min 85%",
        "description": (
            "Ultimately depends on the manufacturer specification of certified (NSF) model. "
            "Low UV Transmittance limits effectiveness of UV disinfection"
        ),
    },
    {"parameter": "Xylene (total)", "result": "<= 0.09 mg/L", "description": "Health risk"},
    {"parameter": "Zinc", "result": "<= 5.0 mg/L", "description": "Undesirable astringent taste"},
]


def normalize_parameter_name(value):
    value = value or ""
    without_parentheses = re.sub(r"\([^)]*\)", "", value)
    normalized = re.sub(r"\s+", " ", without_parentheses).strip().lower()
    aliases = {
        "color true": "colour",
        "electrical conductivity": "conductivity",
        "nitrogen - ammonia": "ammonia",
        "nitrogen - nitrate": "nitrate no3",
        "nitrogen - nitrite": "nitrite no2",
        "nitrogen - organic": "nitrogen, organic",
        "solids - suspended": "solids - suspended",
        "organic carbon": "total organic carbon",
        "solids - dissolved": "total dissolved solids",
        "crypto": "cryptosporidium",
        "haloacetic acid": "haloacetic acids",
        "haloacetic acids": "haloacetic acids",
        "trihalomethanes": "trihalomethanes",
        "trihalomethanes total": "trihalomethanes",
        "trihalomethanes total total": "trihalomethanes",
        "bromodichloromethane": "trihalomethanes",
        "bromoform": "trihalomethanes",
        "chloroform": "trihalomethanes",
        "dibromochloromethane": "trihalomethanes",
        "dibromoacetic acid": "haloacetic acids",
        "dichloroacetic acid": "haloacetic acids",
        "monobromoacetic acid": "haloacetic acids",
        "monochloracetic acid": "haloacetic acids",
        "trichloroacetic acid": "haloacetic acids",
        "bromochloroacetic acid": "bromochloroacetic acid",
        "tribromoacetic acid": "tribromoacetic acid",
        "bromodichloracetic acid": "bromodichloracetic acid",
        "chlorodibromoacetic acid": "chlorodibromoacetic acid",
        "si - silicon total": "silicon",
        "v - vanadium total": "vanadium",
        "etoluene": "toluene",
        "sr - strontium total": "strontium",
        "xylene-o": "xylene",
        "xylene; m & p-": "xylene",
        "xylene total": "xylene",
        "xylenes": "xylene",
    }
    if normalized in aliases:
        return aliases[normalized]
    if normalized == "total dissolved solids":
        return normalized
    normalized = re.sub(r"\bdissolved\b", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return aliases.get(normalized, normalized)


CHEMICAL_GUIDELINES_BY_PARAMETER = {
    normalize_parameter_name(row["parameter"]): row for row in CHEMICAL_PARAMETER_GUIDELINES
}


def interpret_bacteriological_code(value):
    raw = (value or "").strip()
    code = raw.upper().replace("<", "L").replace(" ", "")
    code = code.replace("L!", "L1")
    if not raw:
        return {"raw": raw, "status": "blank", "meaning": ""}
    if code in {"ABSENT", "L0", "L1", "LT1"}:
        return {
            "raw": raw,
            "status": "satisfactory",
            "meaning": "Less than 1 (<1), essentially 0. Satisfactory.",
        }
    if code in {"P", "PRESENT"}:
        return {
            "raw": raw,
            "status": "unsatisfactory",
            "meaning": "Bacteria present; exceeds the <1 guideline.",
        }
    if code.startswith("*"):
        code = code[1:]
    if re.fullmatch(r"\d+(?:\.\d+)?", code):
        count = float(code)
        return {
            "raw": raw,
            "status": "satisfactory" if count < 1 else "unsatisfactory",
            "meaning": "Numeric bacteria count.",
            "count": count,
        }
    if re.fullmatch(r">\d+(?:\.\d+)?", code):
        return {
            "raw": raw,
            "status": "background_growth",
            "meaning": "Greater-than background bacteria count.",
        }
    if re.search(r"B(?:G)?\d+", code) or re.search(r"G(?:R|T|TR)?\d+(?:\.\d+)?", code):
        return {
            "raw": raw,
            "status": "background_growth",
            "meaning": "Number of non-coliform background bacteria colonies.",
        }
    if re.fullmatch(r"L\d+(?:\.\d+)?", code):
        return {
            "raw": raw,
            "status": "satisfactory",
            "meaning": "Less-than bacteria count.",
        }
    if re.match(r"EST(?:CT|HCD)\d+", code) or re.fullmatch(r"E\d+(?:\.\d+)?", code):
        return {
            "raw": raw,
            "status": "unsatisfactory",
            "meaning": "Estimated bacteria count; exceeds the <1 guideline.",
        }
    if "REJCT" in code or "REJECT" in code or code in {"NSR", "NRLABE"}:
        return {
            "raw": raw,
            "status": "rejected",
            "meaning": "Sample rejected or not tested; resample is likely required.",
        }
    if "OG" in code or "TNTC" in code:
        return {
            "raw": raw,
            "status": "unsatisfactory",
            "meaning": "Overgrowth or too numerous to count; unsatisfactory.",
        }
    match = BACTERIOLOGICAL_CODES.get(code)
    if match:
        return {"raw": raw, **match}
    return {"raw": raw, "status": "unknown", "meaning": ""}


def parse_chemical_result_value(value):
    raw = (value or "").strip()
    match = re.match(r"^(?P<qualifier>[A-Za-z]+)?(?P<number>-?\d+(?:\.\d+)?)(?:\s*(?P<unit>.*))?$", raw)
    if not match:
        return {"raw": raw, "qualifier": None, "value": None, "unit": None}
    return {
        "raw": raw,
        "qualifier": match.group("qualifier") or None,
        "value": float(match.group("number")),
        "unit": (match.group("unit") or "").strip() or None,
    }


def get_chemical_guideline(parameter):
    return CHEMICAL_GUIDELINES_BY_PARAMETER.get(normalize_parameter_name(parameter))


def get_water_reference():
    return {
        "bacteriological_definitions": BACTERIOLOGICAL_DEFINITIONS,
        "bacteriological_codes": BACTERIOLOGICAL_CODES,
        "bacteriological_guidelines": BACTERIOLOGICAL_GUIDELINES,
        "chemical_parameter_guidelines": CHEMICAL_PARAMETER_GUIDELINES,
        "sources": REFERENCE_SOURCES,
    }
