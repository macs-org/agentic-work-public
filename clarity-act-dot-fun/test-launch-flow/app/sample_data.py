
DEMO_TOKEN = {
    "address": "0xDemo",
    "name": "DeRegulation Demo Token",
    "symbol": "DEMO",
    "description": "A simulated token page that links buyer-visible CLARITY Act public forms before any purchase decision.",
}

PUBLIC_STATUS = {
    "confidential_ownership": "Confidential ownership list completed; not public by default.",
}

# Deterministic private/export-only sample object. It is deliberately not linked or rendered on buyer/public pages.
PRIVATE_CONFIDENTIAL_OWNERSHIP = {
    "visibility": "private_export_only",
    "requirement_id": "R-050",
    "entries": [
        {"name": "Confidential Founder Wallet", "wallet": "0xConfidential", "rights_percent": "6.2%", "source": "issuer-derived demo grant"}
    ],
}

LAUNCH_MECHANICS = {
    "adapter": "Bankr structured deploy endpoint demo",
    "simulateOnly": True,
    "chain": "base-demo",
    "tokenName": DEMO_TOKEN["name"],
    "tokenSymbol": DEMO_TOKEN["symbol"],
    "feeRecipient": "wallet:0xDemoCreator",
    "pairedAsset": "DEMO-QUOTE",
    "predictedTokenAddress": "0xDemo",
    "notice": "Smart-contract launch requirement — not a CLARITY Act requirement",
}
