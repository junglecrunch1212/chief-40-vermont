"""Project templates: standard phase structures for common project types."""

PROJECT_TEMPLATES = {
    "find_service_provider": {
        "description": "Find and hire a service provider (teacher, plumber, tutor, etc.)",
        "phases": [
            {
                "title": "Research Candidates",
                "default_gate": "none",
                "tools_needed": ["web_search"],
            },
            {
                "title": "Outreach",
                "default_gate": "inform",
                "tools_needed": ["gmail_send", "twilio_call"],
            },
            {
                "title": "Compare & Shortlist",
                "default_gate": "confirm",
                "tools_needed": ["compile"],
            },
            {
                "title": "Schedule Trial / Consultation",
                "default_gate": "none",
                "tools_needed": ["gmail_send", "calendar_read"],
            },
            {
                "title": "Evaluate & Recommend",
                "default_gate": "approve",
                "tools_needed": ["compile"],
            },
            {
                "title": "Book & Close Out",
                "default_gate": "confirm",
                "tools_needed": ["gmail_send"],
            },
        ],
    },
    "construction_project": {
        "description": "Construction, renovation, or major home improvement",
        "phases": [
            {
                "title": "Zoning & Code Research",
                "default_gate": "inform",
                "tools_needed": ["web_search"],
            },
            {
                "title": "Find Professionals",
                "default_gate": "none",
                "tools_needed": ["web_search", "gmail_send"],
            },
            {
                "title": "Get Proposals & Quotes",
                "default_gate": "none",
                "tools_needed": ["gmail_send", "twilio_call"],
            },
            {
                "title": "Select Professional",
                "default_gate": "approve",
                "tools_needed": ["compile"],
            },
            {
                "title": "Contract & Permits",
                "default_gate": "approve",
                "tools_needed": ["gmail_send"],
            },
            {
                "title": "Design Review & Close Out",
                "default_gate": "confirm",
                "tools_needed": ["compile"],
            },
        ],
    },
    "administrative_cleanup": {
        "description": "Administrative task requiring research and execution (data broker removal, insurance shopping, utility switch, etc.)",
        "phases": [
            {
                "title": "Research & Plan",
                "default_gate": "none",
                "tools_needed": ["web_search"],
            },
            {
                "title": "Execute",
                "default_gate": "inform",
                "tools_needed": ["web_search", "gmail_send"],
            },
            {
                "title": "Follow Up",
                "default_gate": "none",
                "tools_needed": ["gmail_send"],
            },
            {
                "title": "Final Report & Close Out",
                "default_gate": "inform",
                "tools_needed": ["compile"],
            },
        ],
    },
    "book_travel": {
        "description": "Plan and book a trip or vacation",
        "phases": [
            {
                "title": "Research Destinations & Options",
                "default_gate": "none",
                "tools_needed": ["web_search"],
            },
            {
                "title": "Present Options",
                "default_gate": "approve",
                "tools_needed": ["compile"],
            },
            {
                "title": "Book Flights & Accommodation",
                "default_gate": "confirm",
                "tools_needed": ["web_search", "gmail_send"],
            },
            {
                "title": "Book Activities",
                "default_gate": "confirm",
                "tools_needed": ["web_search", "gmail_send"],
            },
            {
                "title": "Pre-Trip Logistics & Close Out",
                "default_gate": "none",
                "tools_needed": ["compile"],
            },
        ],
    },
    "enrollment_deadline": {
        "description": "Research and register for a program, camp, class, or activity",
        "phases": [
            {
                "title": "Research Options",
                "default_gate": "none",
                "tools_needed": ["web_search"],
            },
            {
                "title": "Present Options",
                "default_gate": "approve",
                "tools_needed": ["compile"],
            },
            {
                "title": "Register & Pay",
                "default_gate": "confirm",
                "tools_needed": ["gmail_send"],
            },
            {
                "title": "Calendar & Logistics & Close Out",
                "default_gate": "none",
                "tools_needed": ["calendar_read"],
            },
        ],
    },
    "emergency_repair": {
        "description": "Urgent repair: find an available provider ASAP",
        "phases": [
            {
                "title": "Find Available Provider NOW",
                "default_gate": "none",
                "tools_needed": ["web_search", "twilio_call"],
            },
            {
                "title": "Select & Confirm",
                "default_gate": "approve",
                "tools_needed": ["compile"],
            },
            {
                "title": "Coordinate Arrival",
                "default_gate": "none",
                "tools_needed": ["gmail_send", "twilio_sms"],
            },
            {
                "title": "Payment & Close Out",
                "default_gate": "confirm",
                "tools_needed": [],
            },
        ],
    },
}
