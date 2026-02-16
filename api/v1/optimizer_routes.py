from data.metrics import get_latest_provider_snapshot
from fastapi import APIRouter, Request
from data.schemas.rpc import RPCRequest

router = APIRouter()


providers = None
provider_dict = None
optimizer = None


def init_routes(providers_list, provider_dict_map, optimizer_instance):
    global providers, provider_dict, optimizer
    providers = providers_list
    provider_dict = provider_dict_map
    optimizer = optimizer_instance


@router.post("/rpc/best")
async def rpc_best(rpc_request: RPCRequest):
    payload = rpc_request.model_dump()

    result = await optimizer.optimize_request(payload)

    return result


@router.post("/rpc/{provider_name}")
async def rpc_provider(provider_name: str, rpc_request: RPCRequest):
    provider = provider_dict.get(provider_name.lower())
    if not provider:
        return {"error": f"Provider '{provider_name}' not found", "code": 404}

    payload = rpc_request.model_dump()
    response = await provider.call(payload, all_providers=providers)

    print(
        f"[RPC {provider.name}] Latency: {response['latency_ms']:.2f}ms, Price: ${response['price_usd']:.4f}"
    )

    return response


@router.get("/records")
async def records(request: Request):
    try:
        method = request.query_params.get("method")
        all_records = []

        for provider in providers:
            # Skip "Best" pseudo-provider to avoid double counting
            if provider.name.lower() == "best":
                continue
            df = provider.metrics.get_all_records(method)
            if not df.empty:
                all_records.extend(df.to_dict(orient="records"))

        return {
            "method": method if method else "all",
            "records": all_records,
            "total_records": len(all_records),
        }

    except Exception as e:
        return {"error": f"Failed to fetch records: {str(e)}", "code": 500}


@router.get("/analytics")
async def analytics(request: Request):
    try:
        method = request.query_params.get("method")
        if not method:
            return {
                "error": "Please provide a method (e.g., ?method=eth_blockNumber)",
                "code": 400,
            }

        latest_df = get_latest_provider_snapshot(providers, method=method)

        analytics_data = {
            "method": method,
            "providers": [],
            "total_records": sum(
                len(p.metrics.get_all_records(method)) for p in providers if p.name.lower() != "best"
            ),
        }

        for _, row in latest_df.iterrows():
            provider_name = row["Provider"]
            # Skip "Best" pseudo-provider to avoid double counting
            if provider_name.lower() == "best":
                continue
            provider_obj = provider_dict[provider_name.lower()]
            records = provider_obj.metrics.get_all_records(method)

            analytics_data["providers"].append(
                {
                    "name": provider_name,
                    "avg_latency_ms": float(row["Latency"]),
                    "avg_price_usd": float(row["Price"]),
                    "record_count": len(records),
                }
            )

        return analytics_data

    except Exception as e:
        return {"error": f"Failed to generate analytics: {str(e)}", "code": 500}
