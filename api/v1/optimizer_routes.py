from flask import request, jsonify
from data.metrics import get_latest_provider_snapshot
from fastapi import APIRouter

router = APIRouter()


providers = None
provider_dict = None
optimizer = None


async def init_routes(providers_list, provider_dict_map, optimizer_instance):
    global providers, provider_dict, optimizer
    providers = providers_list
    provider_dict = provider_dict_map
    optimizer = optimizer_instance


@router.post("/rpc/<provider_name>")
async def rpc_provider(provider_name):
    provider = provider_dict.get(provider_name.lower())
    if not provider:
        return jsonify({"error": f"Provider '{provider_name}' not found"}), 404

    payload = await request.json
    response = await provider.call(payload, all_providers=providers)

    print(
        f"[RPC {provider.name}] Score: {response['score']:.4f}, "
        f"Weights: L={response['weights']['Latency']:.3f}, P={response['weights']['Price']:.3f}, "
        f"Latency: {response['latency_ms']:.2f}ms, Price: ${response['price_usd']:.4f}"
    )

    return jsonify(response)


@router.post("/rpc/best")
async def rpc_best():
    payload = await request.json

    result = await optimizer.optimize_request(payload)

    return jsonify(result)


@router.get("/records")
async def records():
    try:
        method = await request.args.get("method")  # optional filter
        all_records = []

        for provider in providers:
            df = await provider.metrics.get_all_records(method)
            if not df.empty:
                all_records.extend(df.to_dict(orient="records"))

        return jsonify(
            {
                "method": method if method else "all",
                "records": all_records,
                "total_records": len(all_records),
            }
        )

    except Exception as e:
        return jsonify({"error": f"Failed to fetch records: {str(e)}"}), 500


@router.get("/analytics")
async def analytics():
    try:
        method = await request.args.get("method")
        if not method:
            return (
                jsonify(
                    {"error": "Please provide a method (e.g., ?method=eth_blockNumber)"}
                ),
                400,
            )

        latest_df = await get_latest_provider_snapshot(providers, method=method)

        analytics_data = {
            "method": method,
            "providers": [],
            "total_records": sum(
                len(p.metrics.get_all_records(method)) for p in providers
            ),
        }

        for _, row in latest_df.iterrows():
            provider_name = row["Provider"]
            provider_obj = provider_dict[provider_name.lower()]
            records = provider_obj.metrics.get_all_records(method)

            analytics_data["providers"].append(
                {
                    "name": provider_name,
                    "avg_latency_ms": float(row["Latency"]),
                    "avg_price_usd": float(row["Price"]),
                    "eligible": bool(row["Eligible"]),
                    "record_count": len(records),
                    "normalized_latency": float(row.get("Lnorm", 0)),
                    "normalized_price": float(row.get("Pnorm", 0)),
                }
            )

        return jsonify(analytics_data)

    except Exception as e:
        return jsonify({"error": f"Failed to generate analytics: {str(e)}"}), 500
