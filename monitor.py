
import json
import logging
import requests

from bs4 import BeautifulSoup
from urllib.parse import urljoin

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(message)s"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; PrecioRadarRD/0.1; "
        "+https://github.com/anyeloproject/precioradar-rd)"
    )
}


def find_products(data, results):
    if isinstance(data, list):
        for item in data:
            find_products(item, results)

    elif isinstance(data, dict):
        types = data.get("@type", [])
        if isinstance(types, str):
            types = [types]

        if "Product" in types:
            offers = data.get("offers", {})
            if isinstance(offers, list):
                offers = offers[0] if offers else {}

            if isinstance(offers, dict):
                price = offers.get("price")
                currency = offers.get("priceCurrency")
                availability = offers.get("availability")
            else:
                price = currency = availability = None

            results.append({
                "name": data.get("name"),
                "sku": data.get("sku"),
                "price": price,
                "currency": currency,
                "availability": availability,
                "url": data.get("url")
            })

        for value in data.values():
            if isinstance(value, (dict, list)):
                find_products(value, results)


def inspect_store(store):
    name = store["name"]
    url = store["url"]

    print("\n" + "=" * 50)
    print(f"TIENDA: {name}")
    print(f"URL: {url}")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        print(f"HTTP: {response.status_code}")

        if response.status_code != 200:
            print("No se pudo leer la página.")
            return

        soup = BeautifulSoup(response.text, "lxml")
        print(f"TÍTULO: {soup.title.get_text(strip=True) if soup.title else 'No encontrado'}")

        products = []

        for script in soup.find_all(
            "script",
            type="application/ld+json"
        ):
            try:
                data = json.loads(script.string or script.get_text())
                find_products(data, products)
            except (json.JSONDecodeError, TypeError):
                continue

        # Evitar repetir productos idénticos.
        unique = {}
        for product in products:
            key = (
                product.get("sku"),
                product.get("name"),
                product.get("price")
            )
            unique[key] = product

        products = list(unique.values())

        print(f"PRODUCTOS DETECTADOS: {len(products)}")

        for product in products[:10]:
            print(
                f"- {product.get('name')} | "
                f"Precio: {product.get('price')} "
                f"{product.get('currency') or ''} | "
                f"SKU: {product.get('sku') or 'No disponible'}"
            )

        if not products:
            print(
                "No se detectaron productos estructurados. "
                "Puede que la tienda cargue su catálogo con JavaScript."
            )

    except requests.RequestException as error:
        print(f"ERROR DE CONEXIÓN: {error}")


def main():
    print("PREC IORADAR RD - PRUEBA DE LECTURA")
    print("Supabase: DESACTIVADO")
    print("No se guardarán datos.")

    with open("stores.json", "r", encoding="utf-8") as file:
        stores = json.load(file)

    for store in stores:
        if store.get("enabled", False):
            inspect_store(store)

    print("\nPRUEBA FINALIZADA. No se modificó Supabase.")


if __name__ == "__main__":
    main()
