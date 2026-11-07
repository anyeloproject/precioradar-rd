import json
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130 Safari/537.36"
}

PRICE = re.compile(r"(?:RD\$|US\$|\$)\s?[\d,.]+")


def inspect_jumbo(store):
    print("\nTIENDA:", store["name"])

    response = requests.get(
        store["url"],
        headers=HEADERS,
        timeout=40
    )

    print("HTTP:", response.status_code)
    soup = BeautifulSoup(response.text, "lxml")

    boxes = soup.select("div.price-box")
    print("BLOQUES DE PRECIO:", len(boxes))

    for number, price_box in enumerate(boxes[:3], 1):
        print("\n" + "=" * 45)
        print("PRODUCTO DE MUESTRA:", number)

        current = price_box

        for level in range(1, 9):
            current = current.parent

            if not current:
                break

            classes = current.get("class", [])
            text = current.get_text(" ", strip=True)
            links = [
                a.get("href")
                for a in current.find_all("a", href=True)
            ]

            print("\nNIVEL:", level)
            print("ETIQUETA:", current.name)
            print("CLASES:", classes)
            print("TEXTO:", text[:500])
            print("ENLACES:", links[:5])


def main():
    print("PRECIO RADAR RD - INSPECCIÓN JUMBO")
    print("SUPABASE: DESACTIVADO")
    print("SOLO LECTURA")

    with open("stores.json", encoding="utf-8") as file:
        stores = json.load(file)

    for store in stores:
        if store.get("enabled") and store["name"].lower() == "jumbo":
            inspect_jumbo(store)

    print("\nFIN. NO SE GUARDÓ NINGÚN DATO.")


if __name__ == "__main__":
    main()
