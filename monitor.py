
import json
import re
import time
import os
from urllib.parse import urljoin, urlparse, parse_qs, urlencode, urlunparse

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
}

PRICE_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{2})?)")
MAX_PAGES = 10

SUPABASE_URL = os.environ.get("SUPABASE_URL", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")


def money(value):
    if not value:
        return None
    match = PRICE_RE.search(value.replace("\xa0", " "))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def clean_url(base_url, href):
    if not href:
        return None
    full_url = urljoin(base_url, href.strip())
    parsed = urlparse(full_url)
    path = re.sub(r"/{2,}", "/", parsed.path)
    return urlunparse((
        parsed.scheme, parsed.netloc, path,
        parsed.params, parsed.query, parsed.fragment
    ))


def get_store_id(url):
    match = re.search(r"(\d{6,})", url)
    return match.group(1) if match else None


def get_model(name):
    if not name:
        return None
    candidates = re.findall(
        r"(?<![A-Z0-9])[A-Z0-9]+(?:-[A-Z0-9]+)*(?![A-Z0-9])",
        name.upper()
    )
    for candidate in reversed(candidates):
        compact = candidate.replace("-", "")
        if (re.search(r"[A-Z]", compact)
                and re.search(r"\d", compact)
                and len(compact) >= 5):
            return candidate
    return None


def get_category(url):
    return (
        "TV y Tecnología"
        if "tv-y-tecnologia" in url.lower()
        else "Electro Hogar"
    )


def extract_casa_cuesta(card, base_url):
    title = card.select_one(
        ".product-item-link, .product.name a, a.product-item-link"
    )
    price = card.select_one(
        ".special-price .price, .price-final_price .price, .price-box .price"
    )
    if not title or not price:
        return None

    name = title.get_text(" ", strip=True)
    url = clean_url(base_url, title.get("href"))
    current = money(price.get_text(" ", strip=True))
    old_node = card.select_one(".old-price .price")
    old = money(old_node.get_text(" ", strip=True)) if old_node else None

    if not name or current is None or not url:
        return None

    return {
        "name": name,
        "current_price": current,
        "previous_price": old,
        "model": get_model(name),
        "store_product_id": get_store_id(url),
        "url": url
    }


def extract_jumbo(card, base_url):
    details = card.select_one(".product-item-details")
    if not details:
        return None

    link = details.select_one(
        "a.product-item-link, .product-item-name a"
    )
    if not link:
        link = card.select_one("a[href*='jumbo.com.do']")
    if not link:
        return None

    name = link.get_text(" ", strip=True)
    url = clean_url(base_url, link.get("href"))
    box = details.select_one(".price-box")
    if not box:
        return None

    current_node = box.select_one(
        ".special-price .price, .price-final_price .price"
    )
    old_node = box.select_one(".old-price .price")

    if current_node:
        current = money(current_node.get_text(" ", strip=True))
    else:
        prices = [
            money(n.get_text(" ", strip=True))
            for n in box.select(".price")
        ]
        prices = [p for p in prices if p is not None]
        current = prices[0] if prices else None

    old = money(old_node.get_text(" ", strip=True)) if old_node else None

    if not name or current is None or not url:
        return None

    return {
        "name": name,
        "current_price": current,
        "previous_price": old,
        "model": get_model(name),
        "store_product_id": get_store_id(url),
        "url": url
    }


def next_page_url(soup, current_url):
    node = soup.select_one(
        "a.action.next, li.pages-item-next a, a[rel='next']"
    )
    if node and node.get("href"):
        return clean_url(current_url, node["href"])

    parsed = urlparse(current_url)
    params = parse_qs(parsed.query)
    page = int(params.get("p", ["1"])[0])
    params["p"] = [str(page + 1)]
    next_url = urlunparse(
        parsed._replace(query=urlencode(params, doseq=True))
    )
    return clean_url(current_url, next_url)


def supabase_request(method, table, params=None, payload=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("Faltan los secretos de Supabase en GitHub.")

    url = f"{SUPABASE_URL}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=payload,
        timeout=40
    )

    if not response.ok:
        raise RuntimeError(
            f"Supabase {table}: HTTP {response.status_code} - "
            f"{response.text[:500]}"
        )

    if not response.text.strip():
        return []

    return response.json()


def find_or_create_store(name, store_url):
    parsed = urlparse(store_url)
    website_url = f"{parsed.scheme}://{parsed.netloc}"

    rows = supabase_request(
        "GET", "stores",
        params={
            "select": "id,website_url",
            "name": f"eq.{name}",
            "limit": "1"
        }
    )

    if rows:
        store_id = rows[0]["id"]

        if not rows[0].get("website_url"):
            supabase_request(
                "PATCH", "stores",
                params={"id": f"eq.{store_id}"},
                payload={"website_url": website_url}
            )

        return store_id

    rows = supabase_request(
        "POST", "stores",
        payload={
            "name": name,
            "website_url": website_url,
            "country": "DO",
            "active": True
        }
    )

    if not rows:
        raise RuntimeError(f"No se pudo crear la tienda {name}.")

    return rows[0]["id"]


def find_or_create_product(product):
    params = {
        "select": "id",
        "name": f"eq.{product['name']}",
        "category": f"eq.{product['category']}",
        "limit": "1"
    }
    rows = supabase_request("GET", "products", params=params)
    if rows:
        return rows[0]["id"]

    payload = {
        "name": product["name"],
        "model": product["model"],
        "category": product["category"]
    }
    rows = supabase_request("POST", "products", payload=payload)
    if not rows:
        raise RuntimeError("No se pudo crear el producto.")
    return rows[0]["id"]


def find_or_create_listing(product_id, store_id, product):
    rows = supabase_request(
        "GET", "listings",
        params={
            "select": "id",
            "store_id": f"eq.{store_id}",
            "product_url": f"eq.{product['url']}",
            "limit": "1"
        }
    )

    if rows:
        listing_id = rows[0]["id"]
        supabase_request(
            "PATCH", "listings",
            params={"id": f"eq.{listing_id}"},
            payload={
                "availability": True,
                "product_url": product["url"]
            }
        )
        return listing_id

    rows = supabase_request(
        "POST", "listings",
        payload={
            "product_id": product_id,
            "store_id": store_id,
            "product_url": product["url"],
            "availability": True
        }
    )
    if not rows:
        raise RuntimeError("No se pudo crear la publicación.")
    return rows[0]["id"]


def save_price(listing_id, product):
    latest = supabase_request(
        "GET", "price_history",
        params={
            "select": "price",
            "listing_id": f"eq.{listing_id}",
            "order": "captured_at.desc",
            "limit": "1"
        }
    )

    current = product["current_price"]

    if latest and float(latest[0]["price"]) == float(current):
        return False

    supabase_request(
        "POST", "price_history",
        payload={
            "listing_id": listing_id,
            "price": current,
            "original_price": product["previous_price"]
        }
    )
    return True


def save_product(store_name, store_url, product):
    store_id = find_or_create_store(store_name, store_url)
    product_id = find_or_create_product(product)
    listing_id = find_or_create_listing(
        product_id, store_id, product
    )
    return save_price(listing_id, product)


def scrape_store(store):
    name = store["name"]
    url = store["url"]
    category = get_category(url)
    products = {}
    visited = set()

    print(f"\nTIENDA: {name} | CATEGORÍA: {category}")

    for page in range(1, MAX_PAGES + 1):
        if url in visited:
            break
        visited.add(url)

        response = requests.get(url, headers=HEADERS, timeout=40)
        print(f"PÁGINA {page} | HTTP {response.status_code}")
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, "lxml")

        if name.lower() == "jumbo":
            cards = soup.select("li.product-item")
            extractor = extract_jumbo
        else:
            cards = soup.select(
                ".products-grid .product-item, "
                ".products.list .product-item"
            )
            extractor = extract_casa_cuesta

        for card in cards:
            item = extractor(card, url)
            if item:
                item["category"] = category
                products[item["url"]] = item

        next_url = next_page_url(soup, url)
        if not cards or next_url == url or next_url in visited:
            break

        url = next_url
        time.sleep(1)

    print(f"Productos extraídos: {len(products)}")

    saved = 0
    unchanged = 0
    errors = 0

    for product in products.values():
        try:
            if save_product(name, store["url"], product):
                saved += 1
            else:
                unchanged += 1
        except Exception as error:
            errors += 1
            print(
                "ERROR GUARDANDO:",
                product["name"],
                "|",
                str(error)[:400]
            )

    print(
        f"Precios nuevos: {saved} | Sin cambio: {unchanged} "
        f"| Errores: {errors}"
    )
    return len(products), saved, errors


def main():
    print("PRECIO RADAR RD - CAPTURA Y SUPABASE")

    with open("stores.json", encoding="utf-8") as file:
        stores = json.load(file)

    total = 0
    saved = 0
    errors = 0

    for store in stores:
        if store.get("enabled"):
            count, new_prices, failed = scrape_store(store)
            total += count
            saved += new_prices
            errors += failed

    print("\nRESUMEN")
    print("Productos extraídos:", total)
    print("Precios nuevos:", saved)
    print("Errores:", errors)

    if errors:
        raise RuntimeError(
            "La captura terminó con errores. Revisa los mensajes anteriores."
        )

    print("CAPTURA FINALIZADA.")


if __name__ == "__main__":
    main()
