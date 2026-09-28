#!/usr/bin/env python3
"""
UCP Well-Known Profile Builder Server
Serves the web UI and provides API endpoints for schema metadata, validation, and profile generation.
"""

import json
import os
import re
import signal
import sys

# Ignore SIGHUP signal on subshell close
try:
    signal.signal(signal.SIGHUP, signal.SIG_IGN)
except Exception:
    pass
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

PORT = 8085
STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
SCHEMAS_DIR = "/usr/local/google/home/gcaroline/profile_github/Universal-Commerce-Protocol/ucp/source/schemas"

# Default supported UCP versions
UCP_VERSIONS = [
    {"version": "2026-08-25", "label": "2026-08-25", "is_latest": True},
    {"version": "2026-04-08", "label": "2026-04-08", "is_latest": False},
    {"version": "2026-01-23", "label": "2026-01-23", "is_latest": False},
    {"version": "2026-01-11", "label": "2026-01-11", "is_latest": False},
    {"version": "2026-01-01", "label": "2026-01-01", "is_latest": False},
]

# Capabilities database with metadata and config templates
CAPABILITIES = {
    "dev.ucp.shopping.cart": {
        "name": "dev.ucp.shopping.cart",
        "title": "Shopping Cart",
        "category": "Shopping",
        "min_version": "2026-01-01",
        "description": "Shopping cart capability with estimated pricing, item addition, and cart persistence.",
        "spec_path": "specification/shopping/cart/",
        "schema_path": "schemas/shopping/cart.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {
            "max_items": {"type": "number", "default": 100, "label": "Max Items per Cart"},
            "supports_guest": {"type": "boolean", "default": True, "label": "Supports Guest Cart"}
        }
    },
    "dev.ucp.shopping.checkout": {
        "name": "dev.ucp.shopping.checkout",
        "title": "Checkout",
        "category": "Shopping",
        "min_version": "2026-01-01",
        "description": "Base checkout capability supporting order line items, payment processing, and completion.",
        "spec_path": "specification/shopping/checkout/",
        "schema_path": "schemas/shopping/checkout.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {
            "payment_handlers": {
                "type": "array_string",
                "default": ["com.google.pay", "dev.shopify.shop_pay"],
                "label": "Supported Payment Handlers"
            },
            "allow_guest_checkout": {"type": "boolean", "default": True, "label": "Allow Guest Checkout"}
        }
    },
    "dev.ucp.shopping.order": {
        "name": "dev.ucp.shopping.order",
        "title": "Order Management",
        "category": "Shopping",
        "min_version": "2026-01-01",
        "description": "Order state tracking, post-purchase management, adjustments, and order confirmation.",
        "spec_path": "specification/shopping/order/",
        "schema_path": "schemas/shopping/order.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {
            "supports_cancellation": {"type": "boolean", "default": True, "label": "Supports Cancellation"},
            "supports_returns": {"type": "boolean", "default": True, "label": "Supports Returns"}
        }
    },
    "dev.ucp.shopping.catalog_lookup": {
        "name": "dev.ucp.shopping.catalog_lookup",
        "title": "Catalog Lookup",
        "category": "Shopping",
        "min_version": "2026-01-01",
        "description": "Product and variant lookup by unique identifier or batch retrieval.",
        "spec_path": "specification/shopping/catalog-lookup/",
        "schema_path": "schemas/shopping/catalog_lookup.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {}
    },
    "dev.ucp.shopping.fulfillment": {
        "name": "dev.ucp.shopping.fulfillment",
        "title": "Fulfillment Discovery",
        "category": "Shopping",
        "min_version": "2026-01-11",
        "description": "Extends Catalog with fulfillment options (shipping, pickup, local delivery) and rate estimates.",
        "spec_path": "specification/shopping/fulfillment/",
        "schema_path": "schemas/shopping/fulfillment.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {
            "fulfillment_methods": {
                "type": "array_select",
                "options": ["shipping", "pickup", "delivery"],
                "default": ["shipping", "pickup"],
                "label": "Supported Fulfillment Methods"
            }
        }
    },
    "dev.ucp.shopping.discount": {
        "name": "dev.ucp.shopping.discount",
        "title": "Discounts & Promotions",
        "category": "Shopping",
        "min_version": "2026-01-11",
        "description": "Extends Cart and Checkout with promo codes, automatic discounts, and price adjustments.",
        "spec_path": "specification/shopping/discount/",
        "schema_path": "schemas/shopping/discount.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {
            "supports_promo_codes": {"type": "boolean", "default": True, "label": "Supports Promo Codes"},
            "max_promo_codes": {"type": "number", "default": 1, "label": "Max Promo Codes Per Cart"}
        }
    },
    "dev.ucp.shopping.catalog_search": {
        "name": "dev.ucp.shopping.catalog_search",
        "title": "Catalog Search",
        "category": "Shopping",
        "min_version": "2026-01-23",
        "description": "Product catalog search capability supporting keyword query, filters, and pagination.",
        "spec_path": "specification/shopping/catalog-search/",
        "schema_path": "schemas/shopping/catalog_search.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {
            "max_page_size": {"type": "number", "default": 50, "label": "Max Search Page Size"}
        }
    },
    "dev.ucp.shopping.buyer_consent": {
        "name": "dev.ucp.shopping.buyer_consent",
        "title": "Buyer Consent",
        "category": "Shopping",
        "min_version": "2026-01-23",
        "description": "Extends buyer objects with per-purpose marketing and communication consents.",
        "spec_path": "specification/shopping/buyer-consent/",
        "schema_path": "schemas/shopping/buyer_consent.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {}
    },
    "dev.ucp.common.identity_linking": {
        "name": "dev.ucp.common.identity_linking",
        "title": "Identity Linking (OAuth)",
        "category": "Common",
        "min_version": "2026-01-23",
        "description": "OAuth 2.0 account linking and scope authorization for user-bound operations.",
        "spec_path": "specification/common/identity-linking/",
        "schema_path": "schemas/common/identity_linking.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {
            "scopes": {
                "type": "scopes_map",
                "default": {
                    "dev.ucp.shopping.order:read": {},
                    "dev.ucp.shopping.order:manage": {}
                },
                "label": "Gated Scopes Map"
            }
        }
    },
    "dev.ucp.shopping.permalink": {
        "name": "dev.ucp.shopping.permalink",
        "title": "Permalink Intent",
        "category": "Shopping",
        "min_version": "2026-04-08",
        "description": "Browser-addressable shopping intent capability for deep linking and shareable carts.",
        "spec_path": "specification/shopping/permalink/",
        "schema_path": "schemas/shopping/permalink.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {}
    },
    "dev.ucp.common.location_search": {
        "name": "dev.ucp.common.location_search",
        "title": "Location Search",
        "category": "Common",
        "min_version": "2026-04-08",
        "description": "Search physical store locations by address, geo-coordinates, or amenities.",
        "spec_path": "specification/common/location/search/",
        "schema_path": "schemas/common/location_search.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {}
    },
    "dev.ucp.common.location_lookup": {
        "name": "dev.ucp.common.location_lookup",
        "title": "Location Lookup",
        "category": "Common",
        "min_version": "2026-04-08",
        "description": "Lookup store location details, opening hours, and available services by location ID.",
        "spec_path": "specification/common/location/lookup/",
        "schema_path": "schemas/common/location_lookup.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {}
    },
    "dev.ucp.common.loyalty": {
        "name": "dev.ucp.common.loyalty",
        "title": "Loyalty Program",
        "category": "Common",
        "min_version": "2026-04-08",
        "description": "Loyalty program integration for earning and redeeming rewards during checkout.",
        "spec_path": "specification/common/loyalty/",
        "schema_path": "schemas/common/loyalty.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {
            "program_id": {"type": "string", "default": "rewards_vip", "label": "Loyalty Program ID"}
        }
    },
    "dev.ucp.common.payment_terms": {
        "name": "dev.ucp.common.payment_terms",
        "title": "Payment Terms / BNPL",
        "category": "Common",
        "min_version": "2026-08-25",
        "description": "Buy-Now-Pay-Later (BNPL) and installment payment schedule terms.",
        "spec_path": "specification/common/payment-terms/",
        "schema_path": "schemas/common/payment_terms.json",
        "required_fields": ["version", "spec", "schema"],
        "config_fields": {}
    }
}

# Sample preset profiles
PRESETS = {
    "legacy_core": {
        "name": "Core UCP v2026-01-01 Profile",
        "description": "Legacy core UCP specification profile with standard cart and checkout capabilities.",
        "profile": {
            "ucp": {
                "version": "2026-01-01",
                "services": {
                    "dev.ucp.shopping": [
                        {
                            "version": "2026-01-01",
                            "spec": "https://ucp.dev/2026-01-01/specification/overview",
                            "transport": "rest",
                            "schema": "https://ucp.dev/2026-01-01/services/shopping/rest.openapi.json",
                            "endpoint": "https://merchant.example.com/ucp/v1"
                        }
                    ]
                },
                "capabilities": {
                    "dev.ucp.shopping.cart": [
                        {
                            "version": "2026-01-01",
                            "spec": "https://ucp.dev/2026-01-01/specification/shopping/cart/",
                            "schema": "https://ucp.dev/2026-01-01/schemas/shopping/cart.json"
                        }
                    ],
                    "dev.ucp.shopping.checkout": [
                        {
                            "version": "2026-01-01",
                            "spec": "https://ucp.dev/2026-01-01/specification/shopping/checkout/",
                            "schema": "https://ucp.dev/2026-01-01/schemas/shopping/checkout.json"
                        }
                    ]
                },
                "payment_handlers": {
                    "com.google.pay": [
                        {
                            "id": "gpay",
                            "version": "2026-01-01",
                            "spec": "https://payments.google.com/gpay/specification",
                            "schema": "https://payments.google.com/gpay/schema.json"
                        }
                    ]
                }
            }
        }
    },
    "b2c_retailer": {
        "name": "B2C Retailer (Standard Merchant)",
        "description": "Public catalog, guest cart, checkout with Google Pay and Shop Pay, order history gated by OAuth.",
        "profile": {
            "ucp": {
                "version": "2026-08-25",
                "services": {
                    "dev.ucp.shopping": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/overview",
                            "transport": "rest",
                            "schema": "https://ucp.dev/2026-08-25/services/shopping/rest.openapi.json",
                            "endpoint": "https://merchant.example.com/ucp/v1"
                        }
                    ]
                },
                "capabilities": {
                    "dev.ucp.shopping.cart": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/shopping/cart/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/shopping/cart.json"
                        }
                    ],
                    "dev.ucp.shopping.checkout": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/shopping/checkout/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/shopping/checkout.json"
                        }
                    ],
                    "dev.ucp.shopping.fulfillment": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/shopping/fulfillment/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/shopping/fulfillment.json",
                            "config": {
                                "fulfillment_methods": ["shipping", "pickup"]
                            }
                        }
                    ],
                    "dev.ucp.common.identity_linking": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/common/identity-linking/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/common/identity_linking.json",
                            "config": {
                                "scopes": {
                                    "dev.ucp.shopping.order:read": {},
                                    "dev.ucp.shopping.order:manage": {}
                                }
                            }
                        }
                    ]
                },
                "payment_handlers": {
                    "com.google.pay": [
                        {
                            "id": "gpay",
                            "version": "2026-08-25",
                            "spec": "https://payments.google.com/gpay/specification",
                            "schema": "https://payments.google.com/gpay/schema.json"
                        }
                    ],
                    "dev.shopify.shop_pay": [
                        {
                            "id": "shop_pay",
                            "version": "2026-08-25",
                            "spec": "https://shopify.dev/ucp/shop-pay",
                            "schema": "https://shopify.dev/ucp/shop-pay.json"
                        }
                    ]
                },
                "map_order": {
                    "payment_handlers": ["com.google.pay", "dev.shopify.shop_pay"]
                }
            },
            "keys": [
                {
                    "kid": "key_2026_01",
                    "kty": "EC",
                    "crv": "P-256",
                    "x": "WbbXwVYGdJoP4Xm3qCkGvBRcRvKtEfXDbWvPzpPS8LA",
                    "y": "sP4jHHxYqC89HBo8TjrtVOAGHfJDflYxw7MFMxuFMPY",
                    "use": "sig",
                    "alg": "ES256"
                }
            ]
        }
    },
    "minimal_checkout": {
        "name": "Minimal Shopping Checkout",
        "description": "Lightweight profile exposing only cart, checkout, and Google Pay.",
        "profile": {
            "ucp": {
                "version": "2026-08-25",
                "services": {
                    "dev.ucp.shopping": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/overview",
                            "transport": "rest",
                            "schema": "https://ucp.dev/2026-08-25/services/shopping/rest.openapi.json",
                            "endpoint": "https://checkout.example.com/api"
                        }
                    ]
                },
                "capabilities": {
                    "dev.ucp.shopping.cart": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/shopping/cart/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/shopping/cart.json"
                        }
                    ],
                    "dev.ucp.shopping.checkout": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/shopping/checkout/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/shopping/checkout.json"
                        }
                    ]
                },
                "payment_handlers": {
                    "com.google.pay": [
                        {
                            "id": "gpay",
                            "version": "2026-08-25",
                            "spec": "https://payments.google.com/gpay/specification",
                            "schema": "https://payments.google.com/gpay/schema.json"
                        }
                    ]
                }
            }
        }
    },
    "full_platform": {
        "name": "Platform Profile (Aggregator / Host)",
        "description": "Platform profile hosting full capabilities, location search, loyalty, and signing keys.",
        "profile": {
            "ucp": {
                "version": "2026-08-25",
                "services": {
                    "dev.ucp.shopping": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/overview",
                            "transport": "rest",
                            "schema": "https://ucp.dev/2026-08-25/services/shopping/rest.openapi.json",
                            "endpoint": "https://platform.example.com/ucp/v1"
                        }
                    ]
                },
                "capabilities": {
                    "dev.ucp.shopping.catalog_search": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/shopping/catalog-search/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/shopping/catalog_search.json"
                        }
                    ],
                    "dev.ucp.shopping.checkout": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/shopping/checkout/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/shopping/checkout.json"
                        }
                    ],
                    "dev.ucp.common.location_search": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/common/location/search/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/common/location_search.json"
                        }
                    ],
                    "dev.ucp.common.loyalty": [
                        {
                            "version": "2026-08-25",
                            "spec": "https://ucp.dev/2026-08-25/specification/common/loyalty/",
                            "schema": "https://ucp.dev/2026-08-25/schemas/common/loyalty.json"
                        }
                    ]
                },
                "payment_handlers": {
                    "com.google.pay": [
                        {
                            "id": "gpay",
                            "version": "2026-08-25",
                            "spec": "https://payments.google.com/gpay/specification",
                            "schema": "https://payments.google.com/gpay/schema.json"
                        }
                    ]
                }
            },
            "keys": [
                {
                    "kid": "platform_key_1",
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "x": "O2lhFcC1-1D9YyWq-v2RkX8y-9N1f9k8v7w6e5d4c3b",
                    "use": "sig",
                    "alg": "EdDSA"
                }
            ]
        }
    }
}


def validate_profile_dict(doc):
    """
    Validates a UCP profile document according to UCP schema rules.
    Returns (is_valid, errors, warnings).
    """
    errors = []
    warnings = []

    if not isinstance(doc, dict):
        return False, ["Root document must be a JSON object."], []

    if "ucp" not in doc:
        errors.append("Missing required root member 'ucp'.")
        return False, errors, warnings

    ucp = doc.get("ucp")
    if not isinstance(ucp, dict):
        errors.append("Member 'ucp' must be an object.")
        return False, errors, warnings

    # Validate version
    version = ucp.get("version")
    if not version:
        errors.append("Missing required field 'ucp.version'.")
    elif not re.match(r"^\d{4}-\d{2}-\d{2}$", str(version)):
        errors.append(f"Invalid 'ucp.version' format: '{version}'. Must be YYYY-MM-DD.")

    # Validate services
    services = ucp.get("services")
    if services is not None:
        if not isinstance(services, dict):
            errors.append("'ucp.services' must be an object keyed by reverse domain name.")
        else:
            for sname, slist in services.items():
                if not isinstance(slist, list):
                    errors.append(f"Service '{sname}' must be an array of service declarations.")
                else:
                    for i, sitem in enumerate(slist):
                        if not isinstance(sitem, dict):
                            errors.append(f"Service '{sname}[{i}]' must be an object.")
                            continue
                        if "version" not in sitem:
                            errors.append(f"Service '{sname}[{i}]' missing required 'version'.")
                        if "endpoint" not in sitem:
                            warnings.append(f"Service '{sname}[{i}]' is missing an 'endpoint' URL.")

    # Validate capabilities
    capabilities = ucp.get("capabilities")
    if capabilities is not None:
        if not isinstance(capabilities, dict):
            errors.append("'ucp.capabilities' must be an object keyed by capability name.")
        else:
            for cname, clist in capabilities.items():
                if not isinstance(clist, list):
                    errors.append(f"Capability '{cname}' must be an array of capability declarations.")
                else:
                    for i, citem in enumerate(clist):
                        if not isinstance(citem, dict):
                            errors.append(f"Capability '{cname}[{i}]' must be an object.")
                            continue
                        if "version" not in citem:
                            errors.append(f"Capability '{cname}[{i}]' missing required 'version'.")
                        if "schema" not in citem:
                            warnings.append(f"Capability '{cname}[{i}]' missing recommended 'schema' URL.")
                        if "spec" not in citem:
                            warnings.append(f"Capability '{cname}[{i}]' missing recommended 'spec' URL.")

                        cap_meta = CAPABILITIES.get(cname)
                        if cap_meta and version and re.match(r"^\d{4}-\d{2}-\d{2}$", str(version)):
                            min_ver = cap_meta.get("min_version")
                            if min_ver and str(version) < min_ver:
                                errors.append(
                                    f"Capability '{cname}' is not supported in UCP version '{version}'. "
                                    f"Requires version {min_ver} or higher."
                                )

    # Validate payment_handlers
    payment_handlers = ucp.get("payment_handlers")
    if payment_handlers is not None:
        if not isinstance(payment_handlers, dict):
            errors.append("'ucp.payment_handlers' must be an object.")
        else:
            for pname, plist in payment_handlers.items():
                if not isinstance(plist, list):
                    errors.append(f"Payment handler '{pname}' must be an array.")
                else:
                    for i, pitem in enumerate(plist):
                        if not isinstance(pitem, dict):
                            errors.append(f"Payment handler '{pname}[{i}]' must be an object.")
                            continue
                        if "id" not in pitem:
                            errors.append(f"Payment handler '{pname}[{i}]' missing required 'id'.")

    # Validate JWK keys
    keys = doc.get("keys")
    if keys is not None:
        if not isinstance(keys, list):
            errors.append("'keys' must be an array of JWK key objects.")
        else:
            for i, key in enumerate(keys):
                if not isinstance(key, dict):
                    errors.append(f"Key[{i}] must be an object.")
                    continue
                if "kid" not in key:
                    errors.append(f"Key[{i}] missing required 'kid'.")
                if "kty" not in key:
                    errors.append(f"Key[{i}] missing required 'kty'.")
                kty = key.get("kty")
                if kty == "EC":
                    for req in ["crv", "x", "y"]:
                        if req not in key:
                            errors.append(f"EC key[{i}] missing required field '{req}'.")
                elif kty == "OKP":
                    for req in ["crv", "x"]:
                        if req not in key:
                            errors.append(f"OKP key[{i}] missing required field '{req}'.")

    is_valid = (len(errors) == 0)
    return is_valid, errors, warnings


class ProfileBuilderRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/versions":
            self.send_json_response(UCP_VERSIONS)
        elif path == "/api/capabilities":
            self.send_json_response(CAPABILITIES)
        elif path == "/api/presets":
            self.send_json_response(PRESETS)
        else:
            super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/validate":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            try:
                doc = json.loads(body.decode("utf-8"))
                is_valid, errors, warnings = validate_profile_dict(doc)
                self.send_json_response({
                    "valid": is_valid,
                    "errors": errors,
                    "warnings": warnings
                })
            except json.JSONDecodeError as e:
                self.send_json_response({
                    "valid": False,
                    "errors": [f"JSON Syntax Error: {str(e)}"],
                    "warnings": []
                }, status=400)
        else:
            self.send_error(404, "Endpoint not found")

    def send_json_response(self, data, status=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True


def run_server():
    port = 8085
    try:
        import subprocess, time
        subprocess.run(["fuser", "-k", "-9", f"{port}/tcp"], check=False)
        time.sleep(0.5)
    except Exception:
        pass

    server_address = ("0.0.0.0", port)
    httpd = ReusableHTTPServer(server_address, ProfileBuilderRequestHandler)

    port_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_port.txt")
    with open(port_file, "w") as f:
        f.write(str(port))

    info_file = os.path.join(STATIC_DIR, "server_info.json")
    with open(info_file, "w") as f:
        json.dump({"port": port, "url": f"http://gcarolinetest.c.googlers.com:{port}/"}, f)

    print(f"UCP Profile Builder web server running on http://gcarolinetest.c.googlers.com:{port}/", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server.", flush=True)
        httpd.server_close()


if __name__ == "__main__":
    run_server()
