"""
PrecioRadar RD
Motor inicial de monitoreo automático.

Modo seguro: no registra ni modifica datos en Supabase.
"""

from datetime import datetime, timezone
import logging
import os
import sys

PROJECT = "PrecioRadar RD"
VERSION = "0.1.0"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

def main():
    print("=" * 45)
    print(f"{PROJECT} - Monitor v{VERSION}")
    print("=" * 45)

    now = datetime.now(timezone.utc)
    logging.info("Inicio del proceso: %s", now.isoformat())

    # Protección: las escrituras permanecen desactivadas.
    dry_run = os.getenv("PRICERADAR_DRY_RUN", "true").lower()

    if dry_run != "true":
        logging.error("El modo seguro debe permanecer activado.")
        sys.exit(1)

    logging.info("Modo seguro activado.")
    logging.info("Escrituras en Supabase: DESACTIVADAS.")
    logging.info("Tiendas pendientes de configurar: 124.")
    logging.info("Captura de precios: pendiente de implementación.")
    logging.info("Proceso finalizado correctamente.")

if __name__ == "__main__":
    main()
