
import json
import re
import time
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/130 Safari/537.36"
    )
}

PRICE_RE = re.compile(r"\$?\s*([\d,]+(?:\.\d{2})?)")
MAX_PAGES = 10


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


def get_sku(url, text=""):
    match = re.search(r"(\d{6,})", url)
    if match:
        return match.group(1)

    match = re.search(r"\b[A-Z0-9]{6,}\b", text.upper())
    return match.group(0) if match else None


def extract_casa_cuesta(card, base_url):
    text = card.get_text(" ", strip=True)

    title_node = card.select_one(
        ".product-item-link, .product.name a, a.product-item-link"
    )
    link_node = title_node or card.select_one("a[href]")

    price_node = card.select_one(
        ".price, .special-price .price, .price-final_price"
    )

    if not title_node or not link_node or not price_node:
        return None

    name = title_node.get_text(" ", strip=True)
    url = urljoin(base_url, link_node.get("href", ""))

    current = money(price_node.get_text(" ", strip=True))
    old = None

    old_node = card.select_one(
        ".old-price .price, .special-price .old-price"
    )
    if old_node:
        old = money(old_node.get_text(" ", strip=True))

    if not name or current is None:
        return None

    return {
        "store": "Casa Cuesta",
        "name": name,
        "current_price": current,
        "previous_price": old,
        "sku": get_sku(url, text),
        "url": url,
    }


def extract_jumbo(card, base_url):
    details = card.select_one(".product-item-details")
    if not details:
        return None

    text = details.get_text(" ", strip=True)

    link_node = details.select_one(
        "a.product-item-link, .product-item-name a"
    )
    if not link_node:
        link_node = card.select_one("a[href*='jumbo.com.do']")

    if not link_node:
        return None

    name = link_node.get_text(" ", strip=True)
    url = urljoin(base_url, link_node.get("href", ""))

    price_box = details.select_one(".price-box")
    if not price_box:
        return None

    current_node = price_box.select_one(
        ".special-price .price, .price-final_price .price"
    )
    old_node = price_box.select_one(".old-price .price")

    if current_node:
        current = money(current_node.get_text(" ", strip=True))
    else:
        prices = [
            money(node.get_text(" ", strip=True))
            for node in price_box.select(".price")
        ]
        prices = [p for p in prices if p is not None]
        current = prices[0] if prices else None

    old = money(old_node.get_text(" ", strip=True)) if old_node else None

    if not name or current is None:
        return None

    return {
        "store": "Jumbo",
        "name": name,
        "current_price": current,
        "previous_price": old,
        "sku": get_sku(url, text),
        "url": url,
    }


def next_page_url(soup, current_url):
    node = soup.select_one(
        "a.action.next, li.pages-item-next a, a[rel='next']"
    )
    if node and node.get("href"):
        return urljoin(current_url, node["href"])

    parsed = urlparse(current_url)
    params = parse_qs(parsed.query)

    page = int(params.get("p", ["1"])[0])
    params["p"] = [str(page + 1)]

    from urllib.parse import urlencode, urlunparse

    return urlunparse(
        parsed._replace(query=urlencode(params, doseq=True))
    )


def scrape_store(store):
    name = store["name"]
    url = store["url"]
    products = {}
    visited = set()

    print("\n" + "=" * 55)
    print("TIENDA:", name)

    for page in range(1, MAX_PAGES + 1):
        if url in visited:
            break
        visited.add(url)

        try:
            response = requests.get(
                url,
                headers=HEADERS,
                timeout=40
            )
            print("PÁGINA", page, "| HTTP:", response.status_code)

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

            before = len(products)

            for card in cards:
                product = extractor(card, url)
                if product:
                    key = product["url"] or (
                        product["name"] + str(product["current_price"])
                    )
                    products[key] = product

            added = len(products) - before
            print(
                "Tarjetas:", len(cards),
                "| Productos válidos nuevos:", added
            )

            next_url = next_page_url(soup, url)

            if next_url == url or not cards:
                break

            if next_url in visited:
                break

            url = next_url
            time.sleep(1)

        except Exception as error:
            print("ERROR:", str(error))
            break

    print("\nPRODUCTOS ÚNICOS EXTRAÍDOS:", len(products))

    for product in list(products.values())[:5]:
        print("\nPRODUCTO:", product["name"])
        print("PRECIO ACTUAL:", product["current_price"])
        print("PRECIO ANTERIOR:", product["previous_price"])
        print("SKU:", product["sku"])
        print("ENLACE:", product["url"])

    return list(products.values())


def main():
    print("PRECIO RADAR RD - EXTRACCIÓN DE PRODUCTOS")
    print("SUPABASE: DESACTIVADO")
    print("MODO: SOLO LECTURA")

    with open("stores.json", encoding="utf-8") as file:
        stores = json.load(file)

    total = 0

    for store in stores:
        if store.get("enabled"):
            products = scrape_store(store)
            total += len(products)

    print("\n" + "=" * 55)
    print("TOTAL DE PRODUCTOS EXTRAÍDOS:", total)
    print("NO SE GUARDÓ NINGÚN DATO.")
    print("FIN DE LA PRUEBA.")


if __name__ == "__main__":
    main()
