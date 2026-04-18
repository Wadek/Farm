"""
AI discovery and agent card endpoints.

/.well-known/ai-plugin.json  — service manifest (OpenAI plugin format)
/.well-known/mcp.json        — MCP server hint for future registry discovery
GET /me/agent-card           — personalized markdown block for AI project instructions
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import Node
from app.models.user import User
from app.dependencies import get_current_user

router = APIRouter(tags=["agent"])

NETWORK_NAME = "Farm Network"
NETWORK_DESCRIPTION = (
    "A hyperlocal food exchange connecting farmers and buyers within 20 km. "
    "Farmers list what they grow; buyers browse by location. "
    "Every exchange earns MYC tokens based on CO₂ saved and food energy value."
)


@router.get("/.well-known/ai-plugin.json", include_in_schema=False)
def ai_plugin_manifest(request: Request):
    base = str(request.base_url).rstrip("/")
    return JSONResponse({
        "schema_version": "v1",
        "name_for_human": NETWORK_NAME,
        "name_for_model": "farm_network",
        "description_for_human": NETWORK_DESCRIPTION,
        "description_for_model": (
            "Use this plugin to interact with Farm Network — a hyperlocal food exchange. "
            "You can register a new user, log in to get an API key, add farm nodes, "
            "list what a node grows, create listings for buyers, browse the local market "
            "by GPS coordinates, and sync sensor data from Ruuvi and Ajax devices. "
            "Always obtain an API key via POST /auth/api-keys after login and include it "
            "as the X-API-Key header in all subsequent requests."
        ),
        "auth": {
            "type": "user_http",
            "authorization_type": "custom",
            "custom_auth_header": "X-API-Key",
        },
        "api": {
            "type": "openapi",
            "url": f"{base}/openapi.json",
        },
        "contact_email": "github.com/Wadek/Farm",
        "legal_info_url": f"{base}/",
    })


@router.get("/.well-known/mcp.json", include_in_schema=False)
def mcp_manifest(request: Request):
    base = str(request.base_url).rstrip("/")
    return JSONResponse({
        "name": "farm_network",
        "display_name": NETWORK_NAME,
        "description": NETWORK_DESCRIPTION,
        "version": "0.1.0",
        "endpoint": base,
        "openapi": f"{base}/openapi.json",
        "auth": "X-API-Key",
        "onboarding": (
            f"To join: POST {base}/auth/register with name, email, password, role ('farmer' or 'buyer'). "
            f"Then POST {base}/auth/token to get a JWT, then POST {base}/auth/api-keys to get a permanent API key."
        ),
    })


@router.get("/me/agent-card")
def agent_card(request: Request, current_user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    """Returns a ready-to-paste markdown block for Claude Projects / ChatGPT instructions."""
    base = str(request.base_url).rstrip("/")
    nodes = db.query(Node).filter(Node.owner_id == current_user.id).all()

    node_lines = "\n".join(
        f"- {n.name} (id: `{n.id}`) — {n.type}, {n.lat}, {n.lng}, {n.area_m2} m²"
        for n in nodes
    ) or "  *(no nodes yet — ask me to create one)*"

    card = f"""## Farm Network — AI Agent Card

Paste this block into your AI assistant's project instructions or system prompt.
Create an API key first: POST /auth/api-keys (requires login), then replace the placeholder below.

---

You are connected to **Farm Network** — a hyperlocal food exchange.

**API base:** `{base}`
**My API key:** `REPLACE_WITH_YOUR_KEY`  ← replace this after running: POST {base}/auth/api-keys

**My account:** {current_user.name} ({current_user.role})

**My nodes:**
{node_lines}

**What you can do for me:**

| Action | Method | Path |
|--------|--------|------|
| List my nodes | GET | /nodes |
| Add a node | POST | /nodes |
| Add produce to a node | POST | /nodes/{{node_id}}/produce |
| List produce | GET | /nodes/{{node_id}}/produce |
| Create a listing | POST | /nodes/{{node_id}}/produce/{{produce_id}}/listings |
| Browse local market | GET | /listings?lat={{lat}}&lng={{lng}}&radius_km=20 |
| Update listing status | PATCH | /listings/{{id}}/status?status=reserved |
| Sync sensors | POST | /nodes/{{node_id}}/sync |
| View sensor data | GET | /nodes/{{node_id}}/sensors |
| My token ledger | GET | /transactions/node/{{node_id}} |
| Daily farming tips | POST | /tips/daily?lat={{lat}}&lng={{lng}} |

**Auth:** include `X-API-Key: <your_key>` header on every request.

**Example — add tomatoes to my first node:**
```
POST {base}/nodes/{nodes[0].id if nodes else '{{node_id}}'}/produce
X-API-Key: <your_key>
Content-Type: application/json

{{"name": "Tomatoes", "category": "vegetable", "quantity_kg": 10, "kcal_per_kg": 180, "co2_kg_per_kg": 0.5}}
```

When I say things like "add 5kg of carrots" or "what's available near me", translate that into the appropriate API call and confirm the result.

---
*Generated by Farm Network · {base}*
"""
    return {"card": card, "base_url": base}
