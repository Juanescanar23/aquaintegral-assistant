from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException

from app.services.woocommerce import woocommerce_client

router = APIRouter(
    prefix="/woocommerce",
    tags=["woocommerce"],
)


@router.get("/inventory/sku/{sku}")
async def get_inventory_by_sku(sku: str) -> Dict[str, Any]:
    """
    Devuelve información básica de inventario para un SKU.

    Ejemplo de respuesta:
    {
      "id": 123,
      "name": "Producto X",
      "sku": "ABC123",
      "manage_stock": true,
      "stock_quantity": 5,
      "stock_status": "instock",
      "type": "simple"
    }
    """
    stock_info: Optional[Dict[str, Any]] = await woocommerce_client.get_stock_by_sku(sku)

    if stock_info is None:
        raise HTTPException(status_code=404, detail="Producto no encontrado para ese SKU")

    return stock_info
