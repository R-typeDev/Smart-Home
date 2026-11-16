
from fastapi import APIRouter, HTTPException

from core.network.topology import build_network_topology


router = APIRouter()


@router.get("/api/network/topology")
def get_network_topology():
    try:
        topology = build_network_topology()
        return topology.to_json_data()

    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"Could not build network topology: {type(error).__name__}",
        ) from error
